"""Endpoints de inicio y cierre de sesión (RF02, CU02).

La autenticación es por sesión de Django sobre cookie, no por token en el
navegador: así la credencial queda fuera del alcance de JavaScript y el
CSRF lo cubre el propio framework (Práctica N.° 5, RNF01).
"""
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

from .servicios import cambiar_contrasena


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

        # `authenticate` ya descarta al usuario desactivado, porque `is_active`
        # refleja `esta_activo`: una cuenta dada de baja cae en esta misma rama
        # y recibe el mensaje genérico, sin revelar que el correo existe.
        usuario = authenticate(request, username=correo, password=contrasena)
        if usuario is None:
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
        login(request, usuario)
        usuario.ultimo_acceso_en = timezone.now()
        usuario.save(update_fields=["ultimo_acceso_en"])
        # La petición llegó sin usuario: hay que fijar su centro también en la
        # base, o el registro de auditoría choca con la política RLS.
        fijar_centro_en_la_sesion(usuario.centro_id)
        fijar_contexto(centro_id=usuario.centro_id, usuario_id=usuario.pk)
        registrar("ACCESO", "sesion", usuario.pk, {"correo": usuario.correo})
        return Response({"autenticado": True, "usuario": _datos_de(usuario)})


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

