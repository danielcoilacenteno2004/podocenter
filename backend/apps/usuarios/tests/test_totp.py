"""Pruebas del algoritmo TOTP (RFC 6238) que usa el segundo factor (RF18).

El algoritmo se escribió sin biblioteca; estas pruebas son las que
garantizan que una aplicación autenticadora cualquiera genera los mismos
códigos que el servidor.
"""
import pytest

from apps.usuarios import totp

# Secreto de los vectores de prueba del RFC 6238 (apéndice B): el texto
# ASCII «12345678901234567890» en base32. No es una credencial.
SECRETO_DEL_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # nosec B105


@pytest.mark.parametrize(("instante", "esperado"), [
    (59, "287082"),
    (1111111109, "081804"),
    (1111111111, "050471"),
    (1234567890, "005924"),
    (2000000000, "279037"),
])
def test_coincide_con_los_vectores_de_prueba_del_rfc_6238(instante, esperado):
    # Los vectores del apéndice B del RFC (SHA-1) tienen ocho dígitos; con
    # seis, que es lo que muestran las aplicaciones, quedan sus seis últimos.
    # Si esta prueba falla, ningún teléfono generaría un código aceptado.
    assert totp.codigo_del_paso(SECRETO_DEL_RFC, totp.paso_en(instante)) == esperado


def test_acepta_el_intervalo_anterior_y_el_siguiente_y_no_mas():
    # La tolerancia de un intervalo cubre el reloj desfasado del teléfono; dos
    # intervalos ya es un código vencido, que no debe abrir la sesión.
    ahora = 1_700_000_000
    paso = totp.paso_en(ahora)

    def vale(desfase):
        codigo = totp.codigo_del_paso(SECRETO_DEL_RFC, paso + desfase)
        return totp.paso_del_codigo(SECRETO_DEL_RFC, codigo, momento=ahora)

    assert vale(-1) == paso - 1
    assert vale(1) == paso + 1
    assert vale(-2) is None
    assert vale(2) is None


@pytest.mark.parametrize("codigo", ["", "12345", "1234567", "abcdef", None])
def test_un_codigo_mal_formado_no_vale(codigo):
    # Solo seis dígitos: cualquier otra cosa se rechaza sin calcular nada.
    assert totp.paso_del_codigo(SECRETO_DEL_RFC, codigo) is None


def test_el_secreto_generado_tiene_160_bits_y_es_distinto_cada_vez():
    # 32 caracteres base32 son 160 bits, lo que recomienda el RFC 4226. Dos
    # altas no pueden compartir secreto.
    primero, segundo = totp.generar_secreto(), totp.generar_secreto()

    assert len(primero) == 32
    assert primero != segundo


def test_el_enlace_lleva_el_secreto_y_el_emisor_que_lee_la_aplicacion():
    # Es lo que codifica el QR. Sin el emisor, la aplicación mostraría una
    # entrada sin nombre y la administradora no sabría de qué sistema es.
    enlace = totp.enlace_otpauth(SECRETO_DEL_RFC, cuenta="ana@centro.pe", emisor="PodoCenter")

    assert enlace.startswith("otpauth://totp/PodoCenter%3Aana%40centro.pe?")
    assert f"secret={SECRETO_DEL_RFC}" in enlace
    assert "issuer=PodoCenter" in enlace
