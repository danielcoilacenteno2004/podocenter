"""Endpoints de inicio y cierre de sesión (RF02, CU02) y del segundo factor (RF18).

La autenticación es por sesión de Django sobre cookie, no por token en el
navegador: así la credencial queda fuera del alcance de JavaScript y el
CSRF lo cubre el propio framework (Práctica N.° 5, RNF01).

Con el segundo factor activo, el ingreso tiene dos pasos. El primero valida
la contraseña y solo anota en la sesión anónima quién la pasó; la sesión
autenticada (`login`) se abre en el segundo, con el código. Así no existe en
ningún momento una sesión válida que no haya pasado los dos factores.
"""
import time

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.auditoria import registrar
from apps.core.contexto import fijar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.errores import ReglaDeNegocio
from apps.core.vistas import ContextoDeCentro

from . import bloqueo_de_ingreso, segundo_factor
from .models import Usuario
from .servicios import cambiar_contrasena

# Lo que dura el primer paso aprobado mientras se espera el código.
VIGENCIA_DEL_PRIMER_PASO_SEGUNDOS = 300
_PRIMER_PASO = "segundo_factor_pendiente"


def _datos_de(usuario) -> dict:
    return {
        "id": usuario.pk,
        "correo": usuario.correo,
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "nombre_completo": usuario.nombre_completo,
        "rol": usuario.rol,
        "rol_descripcion": usuario.get_rol_display(),
        "centro": usuario.centro_id,
        "centro_nombre": usuario.centro.razon_social if usuario.centro_id else None,
        "segundo_factor_activo": usuario.segundo_factor_activo,
        "requiere_segundo_factor": usuario.requiere_segundo_factor,
        # Rol administrativo sin factor todavía: la interfaz lo lleva al alta y
        # el servidor no le deja hacer nada más (ContextoDeCentro).
        "debe_activar_segundo_factor": (usuario.requiere_segundo_factor
                                        and not usuario.segundo_factor_activo),
        "ultimo_acceso_en": usuario.ultimo_acceso_en,
        "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
    }


@method_decorator(ensure_csrf_cookie, name="get")
class EstadoDeSesion(APIView):
    """Devuelve quién está conectado y, de paso, entrega la cookie CSRF."""

    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"autenticado": False, "usuario": None})
        return Response({"autenticado": True, "usuario": _datos_de(request.user)})


class IniciarSesion(APIView):
    """CU02 — valida credenciales y abre la sesión."""

    permission_classes = [AllowAny]

    def post(self, request):
        correo = (request.data.get("correo") or "").strip().lower()
        contrasena = request.data.get("contrasena") or ""
        if not correo or not contrasena:
            raise ReglaDeNegocio(
                "credenciales-incompletas", "Indique el correo y la contraseña."
            )

        # Una cuenta bloqueada no entra ni con la contraseña correcta: por eso
        # se mira antes de comprobarla (Tabla 35 del Informe).
        bloqueo_de_ingreso.comprobar(correo)
        # `authenticate` ya descarta al usuario desactivado, porque `is_active`
        # refleja `esta_activo`: una cuenta dada de baja cae en esta misma rama
        # y recibe el mensaje genérico, sin revelar que el correo existe.
        usuario = authenticate(request, username=correo, password=contrasena)
        if usuario is None:
            # Al quinto fallo seguido levanta el error de cuenta bloqueada.
            bloqueo_de_ingreso.anotar_fallo(correo)
            # Mismo mensaje para usuario inexistente y contraseña errada: no se
            # confirma qué correos existen (OWASP, enumeración de cuentas).
            return Response(
                {
                    "type": "about:blank",
                    "title": "Credenciales inválidas",
                    "status": 401,
                    "detail": "El correo o la contraseña no son correctos.",
                    "codigo": "credenciales-invalidas",
                },
                status=status.HTTP_401_UNAUTHORIZED,
                content_type="application/problem+json",
            )
        # La contraseña fue correcta: los fallos anteriores ya no cuentan.
        bloqueo_de_ingreso.levantar(usuario)
        centro = usuario.centro
        if centro is not None and not centro.esta_operativo:
            # Tabla 31: un centro suspendido no puede iniciar sesión. Las
            # credenciales eran válidas, así que se puede decir por qué; el
            # motivo de la suspensión queda para la plataforma.
            fijar_centro_en_la_sesion(centro.pk)
            fijar_contexto(centro_id=centro.pk, usuario_id=usuario.pk)
            registrar("ACCESO_DENEGADO", "sesion", usuario.pk, {"motivo": "centro-suspendido"})
            raise ReglaDeNegocio(
                "centro-suspendido",
                f"El acceso de {centro.nombre_comercial or centro.razon_social} está "
                "suspendido. Consulte con el proveedor del sistema.",
            )
        if usuario.segundo_factor_activo:
            # Primer paso aprobado: todavía no hay sesión, solo la marca de
            # quién la pidió y hasta cuándo puede escribir el código.
            request.session.cycle_key()
            request.session[_PRIMER_PASO] = {
                "usuario": usuario.pk,
                "expira": time.time() + VIGENCIA_DEL_PRIMER_PASO_SEGUNDOS,
            }
            return Response({"autenticado": False, "segundo_factor_requerido": True,
                             "usuario": None})
        return _abrir_sesion(request, usuario, {"correo": usuario.correo})


def _abrir_sesion(request, usuario, datos_de_auditoria: dict) -> Response:
    # El usuario puede llegar del segundo paso, sin pasar por authenticate().
    login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
    usuario.ultimo_acceso_en = timezone.now()
    usuario.save(update_fields=["ultimo_acceso_en"])
    # La petición llegó sin usuario: hay que fijar su centro también en la
    # base, o el registro de auditoría choca con la política RLS.
    fijar_centro_en_la_sesion(usuario.centro_id)
    fijar_contexto(centro_id=usuario.centro_id, usuario_id=usuario.pk)
    registrar("ACCESO", "sesion", usuario.pk, datos_de_auditoria)
    return Response({"autenticado": True, "usuario": _datos_de(usuario)})


class VerificarSegundoFactor(APIView):
    """P02 — segundo paso del ingreso: código de la aplicación o de recuperación."""

    permission_classes = [AllowAny]

    def post(self, request):
        pendiente = request.session.get(_PRIMER_PASO)
        if not pendiente or pendiente.get("expira", 0) < time.time():
            request.session.pop(_PRIMER_PASO, None)
            raise ReglaDeNegocio(
                "segundo-factor-sin-primer-paso",
                "Vuelva a escribir su correo y contraseña.",
            )
        # Entre los dos pasos pudieron desactivar la cuenta o suspender el
        # centro: se vuelve a comprobar con los mismos criterios del primero.
        usuario = Usuario.objects.select_related("centro").filter(
            pk=pendiente["usuario"], esta_activo=True).first()
        if usuario is None or (usuario.centro is not None and not usuario.centro.esta_operativo):
            request.session.pop(_PRIMER_PASO, None)
            raise ReglaDeNegocio(
                "segundo-factor-sin-primer-paso",
                "Vuelva a escribir su correo y contraseña.",
            )
        metodo = segundo_factor.verificar_en_el_ingreso(
            usuario,
            codigo=str(request.data.get("codigo") or ""),
            codigo_recuperacion=str(request.data.get("codigo_recuperacion") or ""),
        )
        request.session.pop(_PRIMER_PASO, None)
        datos = {"correo": usuario.correo, "segundo_factor": metodo}
        if metodo == "recuperacion":
            datos["codigos_de_recuperacion_vigentes"] = (
                segundo_factor.codigos_de_recuperacion_vigentes(usuario))
        return _abrir_sesion(request, usuario, datos)


class AltaDeSegundoFactor(ContextoDeCentro, APIView):
    """P02 (alta) — genera el secreto y su QR para la aplicación autenticadora."""

    permite_segundo_factor_pendiente = True

    def post(self, request):
        return Response(segundo_factor.iniciar_alta(request.user))


class ConfirmarSegundoFactor(ContextoDeCentro, APIView):
    """P02 (alta) — activa el factor con el primer código y entrega los de recuperación."""

    permite_segundo_factor_pendiente = True

    def post(self, request):
        codigos = segundo_factor.confirmar_alta(request.user,
                                                str(request.data.get("codigo") or ""))
        request.user.refresh_from_db()
        return Response({"usuario": _datos_de(request.user), "codigos_recuperacion": codigos})


class CerrarSesion(APIView):
    """CU02 — cierra la sesión del usuario en curso."""

    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            fijar_contexto(centro_id=request.user.centro_id, usuario_id=request.user.pk)
            registrar("SALIDA", "sesion", request.user.pk)
        logout(request)
        return Response({"autenticado": False})


class CambiarContrasena(ContextoDeCentro, APIView):
    """P20 — el usuario conectado cambia su propia contraseña.

    Al guardar, Django cambia el hash de sesión: las demás sesiones abiertas
    de la cuenta dejan de valer (lo que pide la Tabla 33), y
    `update_session_auth_hash` mantiene abierta solo la actual.
    """

    permite_contrasena_pendiente = True
    permite_segundo_factor_pendiente = True

    def post(self, request):
        datos = request.data
        cambiar_contrasena(
            request.user,
            actual=datos.get("contrasena_actual") or "",
            nueva=datos.get("contrasena_nueva") or "",
            confirmacion=datos.get("confirmacion") or "",
        )
        update_session_auth_hash(request, request.user)
        return Response({"cambiada": True})

