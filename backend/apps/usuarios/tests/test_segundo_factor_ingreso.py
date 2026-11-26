"""Pruebas del ingreso en dos pasos (RF18, P02).

Lo que se garantiza: que la contraseña sola no abre la sesión de una cuenta
con factor, que un código vencido, reutilizado o adivinado no la abre, y
que los intentos fallidos acaban en un bloqueo temporal.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.errores import ReglaDeNegocio
from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.usuarios import segundo_factor, totp
from apps.usuarios.models import Usuario

from ...conftest import CLAVE_DE_PRUEBA

INGRESAR = "/api/v1/sesion/ingresar/"
VERIFICAR = "/api/v1/sesion/segundo-factor/verificar/"
ACTUAL = "/api/v1/sesion/actual/"
USUARIOS = "/api/v1/usuarios/"


def _codigo(usuario, desfase=0, ahora=None):
    momento = (ahora or timezone.now()).timestamp()
    return totp.codigo_del_paso(usuario.secreto_totp, totp.paso_en(momento) + desfase)


def _primer_paso(cliente, usuario):
    return cliente.post(INGRESAR, {"correo": usuario.correo, "contrasena": CLAVE_DE_PRUEBA},
                        format="json")


def _verificar(usuario, codigo="", recuperacion="", ahora=None):
    return segundo_factor.verificar_en_el_ingreso(
        Usuario.objects.get(pk=usuario.pk), codigo=codigo,
        codigo_recuperacion=recuperacion, ahora=ahora)


@pytest.mark.django_db
def test_la_contrasena_sola_no_abre_la_sesion_de_una_cuenta_con_factor(administradora):
    # El primer paso no puede dejar una sesión utilizable: si la dejara, el
    # segundo factor sería un trámite que se puede saltar llamando a la API.
    cliente = APIClient()

    respuesta = _primer_paso(cliente, administradora)

    assert respuesta.status_code == 200
    assert respuesta.data["segundo_factor_requerido"] is True
    assert respuesta.data["autenticado"] is False
    assert cliente.get(ACTUAL).data["autenticado"] is False
    assert cliente.get(USUARIOS).status_code == 403


@pytest.mark.django_db
def test_un_codigo_valido_completa_el_ingreso_y_queda_en_la_auditoria(administradora, centro):
    # Camino feliz de P02. La bitácora registra con qué método se entró, para
    # distinguir después un ingreso con código de recuperación.
    cliente = APIClient()
    _primer_paso(cliente, administradora)

    respuesta = cliente.post(VERIFICAR, {"codigo": _codigo(administradora)}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["autenticado"] is True
    assert cliente.get(USUARIOS).status_code == 200
    activar_centro(centro.pk)
    acceso = RegistroAuditoria.objects.filter(accion="ACCESO", entidad_id=str(administradora.pk))
    assert acceso.get().datos["segundo_factor"] == "totp"


@pytest.mark.django_db
def test_sin_primer_paso_el_codigo_no_sirve(administradora):
    # El código solo vale después de la contraseña: con él solo no se entra,
    # aunque sea el correcto.
    respuesta = APIClient().post(VERIFICAR, {"codigo": _codigo(administradora)}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "segundo-factor-sin-primer-paso"


@pytest.mark.django_db
def test_un_codigo_vencido_se_rechaza(administradora):
    # Dos intervalos atrás (más de 30 segundos fuera de la tolerancia): un
    # código anotado o fotografiado hace un minuto ya no sirve.
    ahora = timezone.now()

    with pytest.raises(ReglaDeNegocio) as error:
        _verificar(administradora, codigo=_codigo(administradora, -2, ahora), ahora=ahora)

    assert error.value.codigo == "codigo-incorrecto"


@pytest.mark.django_db
@pytest.mark.parametrize("desfase", [-1, 1])
def test_un_codigo_desfasado_un_intervalo_se_acepta(administradora, desfase):
    # El reloj del teléfono rara vez coincide al segundo con el del servidor;
    # rechazar el código del intervalo vecino dejaría fuera a la
    # administradora sin motivo.
    ahora = timezone.now()

    metodo = _verificar(administradora, codigo=_codigo(administradora, desfase, ahora),
                        ahora=ahora)

    assert metodo == "totp"


@pytest.mark.django_db
def test_un_codigo_ya_usado_no_vale_otra_vez(administradora):
    # El código sigue dentro de su ventana unos segundos más; quien lo vio por
    # encima del hombro no puede reutilizarlo (RFC 6238, sección 5.2).
    ahora = timezone.now()
    codigo = _codigo(administradora, 0, ahora)
    _verificar(administradora, codigo=codigo, ahora=ahora)

    with pytest.raises(ReglaDeNegocio) as error:
        _verificar(administradora, codigo=codigo, ahora=ahora + timedelta(seconds=5))

    assert error.value.codigo == "codigo-incorrecto"


@pytest.mark.django_db
def test_un_codigo_anterior_al_ultimo_aceptado_tampoco_vale(administradora):
    # Aceptado el del intervalo siguiente, el del actual ya no debe valer: si
    # valiera, alguien podría usar el código que la persona dejó de lado.
    ahora = timezone.now()
    _verificar(administradora, codigo=_codigo(administradora, 1, ahora), ahora=ahora)

    with pytest.raises(ReglaDeNegocio):
        _verificar(administradora, codigo=_codigo(administradora, 0, ahora), ahora=ahora)


@pytest.mark.django_db
def test_un_codigo_de_recuperacion_vale_una_sola_vez(administradora):
    # Es el camino de quien perdió el teléfono. Si un código de recuperación
    # sirviera dos veces, uno copiado de un papel valdría para siempre.
    codigos = segundo_factor._renovar_codigos_de_recuperacion(administradora)

    assert _verificar(administradora, recuperacion=codigos[0]) == "recuperacion"
    with pytest.raises(ReglaDeNegocio) as error:
        _verificar(administradora, recuperacion=codigos[0])

    assert error.value.codigo == "codigo-recuperacion-incorrecto"
    assert segundo_factor.codigos_de_recuperacion_vigentes(administradora) == 9


@pytest.mark.django_db
def test_el_codigo_de_recuperacion_se_acepta_sin_guion_y_en_minusculas(administradora):
    # Se copia a mano desde un papel; el formato no puede ser el obstáculo.
    codigo = segundo_factor._renovar_codigos_de_recuperacion(administradora)[3]

    assert _verificar(administradora, recuperacion=codigo.replace("-", "").lower()) == \
        "recuperacion"


@pytest.mark.django_db
def test_cinco_codigos_incorrectos_bloquean_la_cuenta_quince_minutos(administradora, centro):
    # Con un millón de combinaciones y tres códigos válidos a la vez, sin
    # límite un programa adivinaría el código en horas. Durante el bloqueo,
    # ni el código correcto abre la sesión; pasado, sí.
    ahora = timezone.now()
    for _ in range(segundo_factor.MAXIMO_DE_INTENTOS_FALLIDOS - 1):
        with pytest.raises(ReglaDeNegocio) as error:
            _verificar(administradora, codigo="000000", ahora=ahora)
        assert error.value.codigo == "codigo-incorrecto"

    with pytest.raises(ReglaDeNegocio) as error:
        _verificar(administradora, codigo="000000", ahora=ahora)
    assert error.value.codigo == "segundo-factor-bloqueado"

    with pytest.raises(ReglaDeNegocio) as error:
        _verificar(administradora, codigo=_codigo(administradora, 0, ahora), ahora=ahora)
    assert error.value.codigo == "segundo-factor-bloqueado"

    despues = ahora + segundo_factor.DURACION_DEL_BLOQUEO + timedelta(seconds=1)
    assert _verificar(administradora, codigo=_codigo(administradora, 0, despues),
                      ahora=despues) == "totp"
    activar_centro(centro.pk)
    assert RegistroAuditoria.objects.filter(
        accion="ACCESO_DENEGADO", datos__motivo="segundo-factor-bloqueado").exists()


@pytest.mark.django_db
def test_los_intentos_fallidos_se_cuentan_aunque_cada_peticion_falle(administradora):
    # El contador se guarda antes de responder el error. Si se deshiciera con
    # el error, como cualquier otra escritura de una operación fallida, el
    # bloqueo no llegaría nunca a actuar por la API.
    cliente = APIClient()
    _primer_paso(cliente, administradora)

    for _ in range(segundo_factor.MAXIMO_DE_INTENTOS_FALLIDOS):
        respuesta = cliente.post(VERIFICAR, {"codigo": "000000"}, format="json")

    assert respuesta.data["codigo"] == "segundo-factor-bloqueado"
    administradora.refresh_from_db()
    assert administradora.segundo_factor_bloqueado_hasta is not None


@pytest.mark.django_db
def test_una_cuenta_desactivada_entre_los_dos_pasos_no_entra(administradora):
    # La contraseña se validó con la cuenta activa; si la dan de baja antes de
    # escribir el código, el código ya no la puede abrir.
    cliente = APIClient()
    _primer_paso(cliente, administradora)
    Usuario.objects.filter(pk=administradora.pk).update(esta_activo=False)

    respuesta = cliente.post(VERIFICAR, {"codigo": _codigo(administradora)}, format="json")

    assert respuesta.data["codigo"] == "segundo-factor-sin-primer-paso"


@pytest.mark.django_db
def test_el_primer_paso_vence_a_los_cinco_minutos(administradora, monkeypatch):
    # Una contraseña validada en un equipo abandonado no puede quedar
    # esperando el código indefinidamente.
    from apps.usuarios import sesion

    monkeypatch.setattr(sesion, "VIGENCIA_DEL_PRIMER_PASO_SEGUNDOS", -1)  # ya vencido
    cliente = APIClient()
    _primer_paso(cliente, administradora)

    respuesta = cliente.post(VERIFICAR, {"codigo": _codigo(administradora)}, format="json")

    assert respuesta.data["codigo"] == "segundo-factor-sin-primer-paso"


@pytest.mark.django_db
def test_la_podologa_sin_factor_entra_solo_con_la_contrasena(podologa):
    # Para la podóloga el factor es opcional: exigirlo cambiaría su rutina sin
    # que el requerimiento lo pida.
    cliente = APIClient()

    respuesta = _primer_paso(cliente, podologa)

    assert respuesta.data["autenticado"] is True
    assert respuesta.data["usuario"]["debe_activar_segundo_factor"] is False
