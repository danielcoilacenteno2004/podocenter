"""API de sedes con su horario (P18/P28, RF03, CC-15).

Antes no había forma de escribir el horario: una sede nueva nacía cerrada
todos los días y no admitía citas. Tampoco se controlaban el nombre repetido
ni el borrado, que respondían 500.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.sedes.models import HorarioSede, Sede

SEDES = "/api/v1/sedes/"
SEMANA = [{"dia_semana": d, "hora_apertura": "09:00", "hora_cierre": "18:00"} for d in range(5)]


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


def _alta(cliente, nombre="Yanahuara", horario=SEMANA):
    return cliente.post(SEDES, {"nombre": nombre, "direccion": "Av. Ejército 900",
                                "horario": horario}, format="json")


@pytest.mark.django_db
def test_la_sede_nueva_nace_con_su_horario_y_admite_citas_ese_dia(cliente):
    # Garantiza que una sede recién creada se puede usar: la agenda solo
    # acepta citas dentro del horario, así que sin él la sede no servía.
    respuesta = _alta(cliente)

    sede = Sede.objects.get(pk=respuesta.data["id"])
    assert respuesta.status_code == 201
    assert sede.horario_de(0).hora_apertura.strftime("%H:%M") == "09:00"
    assert sede.horario_de(5) is None  # el sábado no vino: queda cerrado
    assert len(respuesta.data["horarios"]) == 5


@pytest.mark.django_db
def test_editar_el_horario_reemplaza_la_semana(cliente, sede):
    # Garantiza que el horario se puede corregir: lo que se envía es la semana
    # completa y el día que no viene queda cerrado, sin restos del anterior.
    respuesta = cliente.patch(f"{SEDES}{sede.pk}/", {"horario": [
        {"dia_semana": 0, "hora_apertura": "07:30", "hora_cierre": "13:00"},
    ]}, format="json")

    assert respuesta.status_code == 200
    assert HorarioSede.objects.filter(sede=sede).count() == 1
    assert sede.horario_de(0).hora_cierre.strftime("%H:%M") == "13:00"
    assert sede.horario_de(1) is None


@pytest.mark.django_db
def test_editar_otros_datos_no_toca_el_horario(cliente, sede):
    # Garantiza que cambiar el teléfono no borra el horario por omisión: solo
    # se reemplaza cuando la petición lo trae.
    antes = HorarioSede.objects.filter(sede=sede).count()

    cliente.patch(f"{SEDES}{sede.pk}/", {"telefono": "054-111222"}, format="json")

    assert HorarioSede.objects.filter(sede=sede).count() == antes


@pytest.mark.django_db
def test_un_cierre_anterior_a_la_apertura_se_rechaza_sin_crear_la_sede(cliente):
    # Garantiza el error de negocio en vez del 500 de la restricción de la
    # base, y que el alta es una sola transacción: no queda una sede a medias.
    respuesta = _alta(cliente, horario=[
        {"dia_semana": 2, "hora_apertura": "18:00", "hora_cierre": "09:00"},
    ])

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "horario-invalido"
    assert "miércoles" in respuesta.data["detail"]
    assert not Sede.objects.filter(nombre="Yanahuara").exists()


@pytest.mark.django_db
def test_un_dia_repetido_se_rechaza(cliente):
    # Garantiza que no se mandan dos horarios para el mismo día, que la base
    # rechazaría con un 500 por la restricción única.
    respuesta = _alta(cliente, horario=[SEMANA[0], SEMANA[0]])

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "dia-repetido"


@pytest.mark.django_db
def test_un_nombre_repetido_es_error_de_negocio_y_no_500(cliente, sede):
    # Garantiza que el nombre repetido, con otras mayúsculas o al editar,
    # llega como error con código y no como error del servidor.
    otra = _alta(cliente, nombre="Bustamante").data

    al_crear = _alta(cliente, nombre=sede.nombre.upper())
    al_editar = cliente.patch(f"{SEDES}{otra['id']}/", {"nombre": sede.nombre}, format="json")

    assert (al_crear.status_code, al_crear.data["codigo"]) == (422, "sede-duplicada")
    assert (al_editar.status_code, al_editar.data["codigo"]) == (422, "sede-duplicada")


@pytest.mark.django_db
def test_una_sede_no_se_borra(cliente, sede):
    # Garantiza que no se pierde la historia de una sede (citas, atenciones,
    # stock): la baja es desmarcarla como activa. El DELETE respondía 500.
    respuesta = cliente.delete(f"{SEDES}{sede.pk}/")

    assert respuesta.status_code == 405
    assert Sede.objects.filter(pk=sede.pk).exists()


@pytest.mark.django_db
def test_el_cambio_de_horario_queda_en_la_bitacora(cliente, sede):
    # Garantiza que se sabe quién cambió el horario y a qué: decide qué citas
    # se pueden dar, así que es un cambio que hay que poder reconstruir.
    cliente.patch(f"{SEDES}{sede.pk}/", {"horario": SEMANA[:1]}, format="json")

    registro = RegistroAuditoria.objects.filter(entidad="sede", entidad_id=sede.pk).last()

    assert registro.datos["horario"] == {"lunes": "09:00-18:00"}


@pytest.mark.django_db
def test_la_podologa_no_cambia_el_horario(podologa, sede):
    # Garantiza que el horario es de la administradora (Tabla 29).
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))

    respuesta = cliente.patch(f"{SEDES}{sede.pk}/", {"horario": SEMANA}, format="json")

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_no_se_edita_la_sede_de_otro_centro(cliente, centro, otro_centro):
    # Garantiza el aislamiento: una administradora no puede cerrar ni abrir
    # una sede de otro centro.
    activar_centro(otro_centro.pk)
    ajena = Sede.objects.create(centro=otro_centro, nombre="Lima", direccion="Jr. Unión 1")
    activar_centro(centro.pk)

    respuesta = cliente.patch(f"{SEDES}{ajena.pk}/", {"horario": SEMANA}, format="json")

    assert respuesta.status_code == 404
