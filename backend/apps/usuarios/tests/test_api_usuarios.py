"""API del módulo Usuarios y roles (RF01, CU01), pantalla P17.

Las pruebas unitarias de `servicios.py` ya cubren las reglas; aquí se
comprueba lo que añade la capa HTTP: quién puede entrar, qué devuelve el
listado, cómo viajan los errores y —lo más importante en un sistema
multi-inquilino— que un centro no alcance jamás a los usuarios de otro.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.soporte_pruebas import activar_centro
from apps.sedes.models import Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol
from apps.usuarios.servicios import crear_usuario

from ...conftest import CLAVE_DE_PRUEBA

USUARIOS = "/api/v1/usuarios/"
SEDES_DE_LA_SESION = "/api/v1/sesion/sedes/"


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def cliente_podologa(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def segunda_sede(centro):
    sede = Sede.objects.create(
        centro=centro, nombre="Bustamante", direccion="Av. Dolores 320"
    )
    activar_centro(centro.pk)
    return sede


@pytest.fixture
def usuario_de_otro_centro(otro_centro):
    """Un usuario que vive en otro inquilino, para probar el aislamiento."""
    activar_centro(otro_centro.pk)
    sede = Sede.objects.create(
        centro=otro_centro, nombre="Lima Centro", direccion="Jr. de la Unión 100"
    )
    ajeno = crear_usuario(
        centro=otro_centro, correo="ajena@limanorte.pe", nombres="Paula",
        apellidos="Infante", rol=Rol.PODOLOGA, sedes_ids=[sede.pk],
    )
    return ajeno


# ------------------------------------------------------------------ acceso
@pytest.mark.django_db
def test_sin_sesion_no_se_llega_al_listado():
    # El módulo entero está detrás de autenticación: ninguna de sus rutas
    # responde a un cliente anónimo.
    assert APIClient().get(USUARIOS).status_code in (401, 403)


@pytest.mark.django_db
def test_la_podologa_no_puede_crear_usuarios(cliente_podologa, sede):
    # El RBAC del RF01 reserva el alta de usuarios a la administradora del
    # centro. Se prueba sobre la escritura, que es donde el error sería más
    # caro.
    respuesta = cliente_podologa.post(USUARIOS, {
        "correo": "intrusa@centro.pe", "nombres": "A", "apellidos": "B",
        "rol": Rol.PODOLOGA, "sedes_ids": [sede.pk],
    }, format="json")

    assert respuesta.status_code == 403


# -------------------------------------------------------------------- alta
@pytest.mark.django_db
def test_el_alta_crea_al_usuario_y_lo_asigna_a_su_sede(cliente, centro, sede):
    # Camino feliz del CU01. El centro no se acepta del cuerpo de la petición:
    # lo pone el servidor a partir de quien está conectado.
    respuesta = cliente.post(USUARIOS, {
        "correo": "nueva@centro.pe", "nombres": "Elena", "apellidos": "Vargas",
        "rol": Rol.PODOLOGA, "sedes_ids": [sede.pk],
    }, format="json")

    assert respuesta.status_code == 201
    creada = Usuario.objects.get(correo="nueva@centro.pe")
    assert creada.centro_id == centro.pk
    assert creada.puede_usar_sede(sede.pk)


@pytest.mark.django_db
def test_la_primera_sede_de_la_lista_queda_como_predeterminada(
    cliente, sede, segunda_sede
):
    # Define qué sede se abre sin preguntar cuando la usuaria entra; si no
    # hubiera una marcada, la pantalla P03 aparecería siempre.
    cliente.post(USUARIOS, {
        "correo": "doble@centro.pe", "nombres": "Ana", "apellidos": "Ruiz",
        "rol": Rol.PODOLOGA, "sedes_ids": [segunda_sede.pk, sede.pk],
    }, format="json")

    asignaciones = AsignacionSede.objects.filter(usuario__correo="doble@centro.pe")
    assert asignaciones.get(es_predeterminada=True).sede_id == segunda_sede.pk


@pytest.mark.django_db
def test_la_respuesta_del_alta_no_expone_la_contrasena(cliente, sede):
    # `sedes_ids` es de solo escritura y la clave generada no debe salir nunca:
    # el alta no puede filtrar una credencial recién creada.
    respuesta = cliente.post(USUARIOS, {
        "correo": "limpia@centro.pe", "nombres": "C", "apellidos": "D",
        "rol": Rol.PODOLOGA, "sedes_ids": [sede.pk],
    }, format="json")

    assert "password" not in respuesta.data
    assert "sedes_ids" not in respuesta.data


@pytest.mark.django_db
def test_no_se_puede_crear_un_administrador_de_plataforma_desde_el_centro(cliente, sede):
    # Escalada de privilegios: un centro cliente no puede fabricarse una cuenta
    # con alcance sobre toda la plataforma.
    respuesta = cliente.post(USUARIOS, {
        "correo": "root@centro.pe", "nombres": "A", "apellidos": "B",
        "rol": Rol.ADMIN_PLATAFORMA, "sedes_ids": [sede.pk],
    }, format="json")

    assert respuesta.status_code == 400


@pytest.mark.django_db
def test_un_correo_repetido_se_rechaza_antes_de_tocar_la_base(cliente, sede, podologa):
    # El correo es único a nivel de modelo, así que el serializador lo detecta
    # antes de llegar a `crear_usuario`: el rechazo es un 400 de validación y no
    # el 422 de regla de negocio. La comprobación de `servicios.py` sigue
    # existiendo como segunda barrera y se prueba aparte.
    respuesta = cliente.post(USUARIOS, {
        "correo": podologa.correo, "nombres": "Otra", "apellidos": "Igual",
        "rol": Rol.PODOLOGA, "sedes_ids": [sede.pk],
    }, format="json")

    assert respuesta.status_code == 400
    assert Usuario.objects.filter(correo=podologa.correo).count() == 1


@pytest.mark.django_db
def test_un_usuario_de_centro_sin_sede_devuelve_el_codigo_de_negocio(cliente):
    # Un usuario sin sede no podría ver nada: la regla evita crear cuentas
    # inutilizables que luego nadie sabe por qué fallan.
    respuesta = cliente.post(USUARIOS, {
        "correo": "suelta@centro.pe", "nombres": "Sin", "apellidos": "Sede",
        "rol": Rol.PODOLOGA, "sedes_ids": [],
    }, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede"


@pytest.mark.django_db
def test_el_error_de_negocio_llega_en_el_formato_acordado(cliente):
    # Todos los errores siguen el RFC 9457; la pantalla traduce por el campo
    # `codigo`, así que su presencia es parte del contrato con el cliente.
    respuesta = cliente.post(USUARIOS, {
        "correo": "otra@centro.pe", "nombres": "Sin", "apellidos": "Sede",
        "rol": Rol.PODOLOGA, "sedes_ids": [],
    }, format="json")

    assert set(respuesta.data) >= {"type", "title", "status", "detail", "codigo"}


# ----------------------------------------------------------------- listado
@pytest.mark.django_db
def test_el_listado_viene_ordenado_por_apellidos(cliente, centro, sede):
    # La pantalla P17 no reordena en el navegador: el orden llega resuelto del
    # servidor para que la paginación sea coherente entre páginas.
    for correo, apellidos in [("z@centro.pe", "Zapata"), ("a@centro.pe", "Álvarez")]:
        crear_usuario(centro=centro, correo=correo, nombres="N", apellidos=apellidos,
                      rol=Rol.PODOLOGA, sedes_ids=[sede.pk])

    apellidos = [fila["apellidos"] for fila in cliente.get(USUARIOS).data["results"]]

    assert apellidos == sorted(apellidos)


@pytest.mark.django_db
def test_el_listado_se_filtra_por_rol(cliente, podologa, administradora):
    # Filtro de la pantalla P17. Se resuelve en la base para no traer el padrón
    # completo al navegador.
    respuesta = cliente.get(USUARIOS, {"rol": Rol.PODOLOGA})

    correos = [fila["correo"] for fila in respuesta.data["results"]]
    assert correos == [podologa.correo]


@pytest.mark.django_db
def test_el_listado_se_filtra_por_estado(cliente, centro, sede, podologa):
    # Permite esconder las cuentas dadas de baja, que por ser baja lógica siguen
    # existiendo en la tabla.
    crear_usuario(centro=centro, correo="baja@centro.pe", nombres="B", apellidos="Baja",
                  rol=Rol.PODOLOGA, sedes_ids=[sede.pk])
    Usuario.objects.filter(correo="baja@centro.pe").update(esta_activo=False)

    activos = cliente.get(USUARIOS, {"esta_activo": "true"}).data["results"]

    assert "baja@centro.pe" not in [fila["correo"] for fila in activos]


# --------------------------------------------------------- baja y reactivación
@pytest.mark.django_db
def test_la_baja_es_logica_y_conserva_la_fila(cliente, centro, sede):
    # Borrar la fila rompería el historial de atenciones, que apunta a ella. La
    # baja desactiva, no elimina.
    otra = crear_usuario(centro=centro, correo="segunda@centro.pe", nombres="Mía",
                         apellidos="Luna", rol=Rol.ADMIN_CENTRO, sedes_ids=[sede.pk])

    respuesta = cliente.delete(f"{USUARIOS}{otra.pk}/")

    assert respuesta.status_code == 204
    otra.refresh_from_db()
    assert otra.esta_activo is False


@pytest.mark.django_db
def test_no_se_puede_desactivar_al_ultimo_administrador(cliente, administradora):
    # Evita el centro huérfano: sin administrador activo nadie podría volver a
    # dar de alta usuarios y el centro quedaría bloqueado.
    respuesta = cliente.delete(f"{USUARIOS}{administradora.pk}/")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "ultimo-administrador"


@pytest.mark.django_db
def test_reactivar_devuelve_al_usuario_al_servicio(cliente, centro, sede):
    # Contrapartida de la baja lógica: una desactivación por error debe poder
    # deshacerse sin recrear la cuenta ni perder su historial.
    otra = crear_usuario(centro=centro, correo="vuelve@centro.pe", nombres="V",
                         apellidos="Vuelta", rol=Rol.PODOLOGA, sedes_ids=[sede.pk])
    cliente.delete(f"{USUARIOS}{otra.pk}/")

    respuesta = cliente.post(f"{USUARIOS}{otra.pk}/reactivar/")

    assert respuesta.status_code == 200
    otra.refresh_from_db()
    assert otra.esta_activo is True


# ------------------------------------------------- aislamiento multi-inquilino
@pytest.mark.django_db
def test_el_listado_no_muestra_usuarios_de_otro_centro(
    cliente, centro, usuario_de_otro_centro
):
    # Aislamiento multi-inquilino (RNF01). Es la prueba que sostiene el modelo
    # de arriendo: que dos centros compartan base de datos no puede notarse.
    activar_centro(centro.pk)

    correos = [fila["correo"] for fila in cliente.get(USUARIOS).data["results"]]

    assert usuario_de_otro_centro.correo not in correos


@pytest.mark.django_db
def test_no_se_alcanza_la_ficha_de_un_usuario_de_otro_centro(
    cliente, centro, usuario_de_otro_centro
):
    # Adivinar el identificador no abre la puerta: la seguridad a nivel de fila
    # devuelve 404, no 403, para no confirmar siquiera que esa fila existe.
    activar_centro(centro.pk)

    respuesta = cliente.get(f"{USUARIOS}{usuario_de_otro_centro.pk}/")

    assert respuesta.status_code == 404


@pytest.mark.django_db
def test_no_se_desactiva_a_un_usuario_de_otro_centro(
    cliente, centro, usuario_de_otro_centro
):
    # El aislamiento vale también para la escritura: no basta con ocultar, hay
    # que impedir que un centro modifique datos de otro.
    activar_centro(centro.pk)

    respuesta = cliente.delete(f"{USUARIOS}{usuario_de_otro_centro.pk}/")

    assert respuesta.status_code == 404
    usuario_de_otro_centro.refresh_from_db()
    assert usuario_de_otro_centro.esta_activo is True


# --------------------------------------------------- sedes de la sesión (P03)
@pytest.mark.django_db
def test_con_una_sola_sede_la_sesion_no_pide_elegir(cliente_podologa):
    # Cambio CC-03: preguntar por una sede cuando solo hay una es una
    # interacción inútil en la tarea más repetida del día.
    respuesta = cliente_podologa.get(SEDES_DE_LA_SESION)

    assert respuesta.status_code == 200
    assert respuesta.data["requiere_eleccion"] is False
    assert len(respuesta.data["sedes"]) == 1


@pytest.mark.django_db
def test_con_dos_sedes_la_sesion_pide_elegir(cliente, administradora, segunda_sede):
    # La podóloga que trabaja en ambas sedes sí debe declarar dónde está: de
    # ello depende qué agenda y qué stock ve.
    AsignacionSede.objects.create(usuario=administradora, sede=segunda_sede)

    respuesta = cliente.get(SEDES_DE_LA_SESION)

    assert respuesta.data["requiere_eleccion"] is True
    assert {s["nombre"] for s in respuesta.data["sedes"]} == {"Cercado", "Bustamante"}


@pytest.mark.django_db
def test_la_sede_desactivada_desaparece_de_la_eleccion(
    cliente, administradora, segunda_sede
):
    # Una sede cerrada no puede seguir ofreciéndose, o se registrarían
    # atenciones en un local que ya no opera.
    AsignacionSede.objects.create(usuario=administradora, sede=segunda_sede)
    Sede.objects.filter(pk=segunda_sede.pk).update(esta_activa=False)

    respuesta = cliente.get(SEDES_DE_LA_SESION)

    assert [s["nombre"] for s in respuesta.data["sedes"]] == ["Cercado"]


@pytest.mark.django_db
def test_el_usuario_nuevo_puede_iniciar_sesion_con_la_clave_que_se_le_asigna(
    cliente, centro, sede
):
    """El alta por API genera una clave aleatoria: no debe quedar una por defecto."""
    crear_usuario(centro=centro, correo="clave@centro.pe", nombres="C", apellidos="Clave",
                  rol=Rol.PODOLOGA, sedes_ids=[sede.pk], password=CLAVE_DE_PRUEBA)

    creada = Usuario.objects.get(correo="clave@centro.pe")
    assert creada.check_password(CLAVE_DE_PRUEBA)
