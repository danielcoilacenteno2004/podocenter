"""Carga un centro de demostración con datos realistas.

Sirve para la sustentación y para que cualquier integrante levante el
proyecto y vea el sistema con contenido, sin tener que teclear datos.
No se usa en producción: borra y rehace el centro de demostración.

    python manage.py cargar_demo
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.atenciones.models import Atencion
from apps.catalogo.models import Servicio, ServicioInsumo
from apps.citas.models import Cita
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.contexto import fijar_contexto, limpiar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.errores import ReglaDeNegocio
from apps.core.models import Centro
from apps.inventario.models import MovimientoInventario, Producto, Stock
from apps.inventario.servicios import registrar_movimiento
from apps.pacientes.models import Consentimiento, Paciente
from apps.sedes.models import HorarioSede, Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol

CLAVE = "Podocenter2026"
CORREO_PLATAFORMA = "plataforma@podocenter.pe"
SUBDOMINIO = "piessanos"

SERVICIOS = [
    ("Quiropodia general",
     "Corte y fresado de uñas, eliminación de durezas y callosidades.", 45, "60.00"),
    ("Tratamiento de onicocriptosis",
     "Uña encarnada: liberación del borde y curación.", 60, "90.00"),
    ("Tratamiento de onicomicosis",
     "Hongos en la uña: fresado y aplicación del tratamiento tópico.", 30, "70.00"),
    ("Reflexología podal",
     "Masaje terapéutico de la planta del pie.", 40, "55.00"),
    ("Evaluación biomecánica",
     "Estudio de la pisada y recomendación de soporte plantar.", 50, "120.00"),
    ("Pie diabético — control",
     "Control periódico del pie en paciente diabético.", 45, "80.00"),
]

PACIENTES = [
    ("12345678", "María Elena", "Quispe Mamani",
     "1968-03-14", "959874123", "Av. Ejército 512, Yanahuara"),
    ("40218765", "Juan Carlos", "Ticona Flores",
     "1985-07-02", "984221750", "Calle Mercaderes 210, Cercado"),
    ("29654321", "Rosa Amelia", "Huamán Ccora",
     "1957-11-23", "958112430", "Urb. La Negrita F-12, Miraflores"),
    ("45872130", "Luis Alberto", "Paredes Rivera",
     "1991-01-30", "996540218", "Av. Dolores 1180, J.L.B. y Rivero"),
    ("31122540", "Carmen Julia", "Vilca Apaza",
     "1962-05-18", "954330287", "Calle Puente Grau 345, Cercado"),
    ("70451238", "Diego Martín", "Salas Benavides",
     "1999-09-08", "921874506", "Av. Lambramani 220, Paucarpata"),
    ("28976541", "Teresa", "Chura Condori",
     "1954-02-11", "958220147", "Calle San Juan de Dios 118, Cercado"),
    ("42876109", "Víctor Hugo", "Gutiérrez Linares",
     "1988-12-05", "974510832", "Av. Kennedy 905, Paucarpata"),
    ("33415678", "Sonia Beatriz", "Arenas Delgado",
     "1970-06-27", "959043217", "Urb. Casa Blanca D-4, Sachaca"),
    ("48213097", "Renzo Alonso", "Cáceres Zevallos",
     "1996-04-19", "982117460", "Av. Independencia 702, Cercado"),
    ("30987612", "Gladys", "Mamani Larico",
     "1959-08-03", "953880412", "Calle Zela 430, Cercado"),
    ("41560982", "Patricia", "Núñez Choque",
     "1983-10-16", "976320188", "Av. Estados Unidos 1420, J.L.B. y Rivero"),
]

ANTECEDENTES = {
    "12345678":
        "Diabetes mellitus tipo 2 en control. Sensibilidad disminuida en el antepié derecho.",
    "29654321":
        "Hipertensión arterial. Uso de anticoagulante oral: extremar cuidado con el sangrado.",
    "28976541":
        "Diabetes mellitus tipo 2. Antecedente de úlcera plantar cicatrizada en 2023.",
    "42876109":
        "Hiperhidrosis plantar. Alergia declarada al esparadrapo de tela.",
}


class Command(BaseCommand):
    help = "Carga el centro de demostración con sedes, usuarios, pacientes y agenda."

    def add_arguments(self, parser):
        parser.add_argument(
            "--conservar",
            action="store_true",
            help="No borra el centro de demostración si ya existe; solo informa y termina.",
        )
        parser.add_argument(
            "--en-produccion",
            action="store_true",
            help="Permite correrlo con la configuración de producción (p. ej. un servidor "
                 "solo para la exposición).",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        # Crea un administrador de plataforma con una contraseña publicada en
        # CLAUDE.md: en un servidor con centros reales sería una puerta abierta.
        if settings.ES_PRODUCCION and not opciones["en_produccion"]:
            raise CommandError(
                "cargar_demo no se ejecuta con la configuración de producción: crea cuentas "
                "con una contraseña pública. Si el servidor es solo para la exposición, "
                "use --en-produccion."
            )
        existente = Centro.objects.filter(subdominio=SUBDOMINIO).first()
        if existente and opciones["conservar"]:
            self.stdout.write(self.style.WARNING(
                "El centro de demostración ya existe. No se hizo nada (--conservar)."))
            return
        if existente:
            self.stdout.write("Borrando el centro de demostración anterior…")
            # El RLS filtra por `app.centro_id`; sin fijarlo, ni se ve ni se borra.
            fijar_centro_en_la_sesion(existente.pk)
            fijar_contexto(centro_id=existente.pk)
            # Los movimientos y el stock protegen producto, sede y usuario.
            MovimientoInventario.objects.filter(centro=existente).delete()
            Stock.objects.filter(centro=existente).delete()
            ServicioInsumo.objects.filter(centro=existente).delete()
            Producto.objects.filter(centro=existente).delete()
            # La atención protege su cita (PROTECT): va antes que las citas.
            Atencion.objects.filter(centro=existente).delete()
            Cita.objects.filter(centro=existente).delete()
            Consentimiento.objects.filter(paciente__centro=existente).delete()
            Paciente.objects.filter(centro=existente).delete()
            Servicio.objects.filter(centro=existente).delete()
            AsignacionSede.objects.filter(usuario__centro=existente).delete()
            Usuario.objects.filter(centro=existente).delete()
            # El administrador de plataforma no pertenece a ningún centro, así
            # que hay que borrarlo por correo o el alta siguiente choca.
            Usuario.objects.filter(correo=CORREO_PLATAFORMA).delete()
            HorarioSede.objects.filter(sede__centro=existente).delete()
            Sede.objects.filter(centro=existente).delete()
            existente.auditoria.all().delete()
            existente.delete()

        centro = Centro.objects.create(
            razon_social="Centro de Podología Pies Sanos E.I.R.L.",
            nombre_comercial="Pies Sanos",
            correo_contacto="gerencia@piessanos.pe",
            ruc="20601234567",
            subdominio=SUBDOMINIO,
        )
        fijar_centro_en_la_sesion(centro.pk)
        fijar_contexto(centro_id=centro.pk)
        try:
            self._poblar(centro)
        finally:
            limpiar_contexto()

    # ------------------------------------------------------------------ datos
    def _poblar(self, centro):
        sedes = self._sedes(centro)
        admin_centro, podologas = self._usuarios(centro, sedes)
        fijar_contexto(centro_id=centro.pk, usuario_id=admin_centro.pk)
        servicios = self._servicios(centro)
        pacientes = self._pacientes(centro, admin_centro)
        creadas = self._agenda(centro, sedes, podologas, servicios, pacientes, admin_centro)
        self._variar_estados(centro)
        # Después de variar los estados, para que no se marquen como atendidas.
        creadas += self._citas_en_curso(centro, sedes, podologas, servicios, pacientes,
                                        admin_centro)
        self._inventario(centro, sedes, admin_centro)
        self._resumen(centro, sedes, pacientes, creadas)

    def _inventario(self, centro, sedes, usuario):
        """Productos del wireframe de P12 con existencias en las dos sedes.

        Entran como movimientos de entrada, igual que en la realidad: el stock
        no se escribe nunca directamente. Algunos quedan bajo el mínimo para
        que el filtro de P12 tenga algo que mostrar.
        """
        # (código, nombre, unidad, mínimo, existencia en cada sede)
        guion = [
            ("INS-004", "Crema urea 10 %", "unidad", 4, (1, 8)),
            ("INS-011", "Apósito hidrocoloide", "caja", 5, (3, 6)),
            ("INS-001", "Fresa de pulido desechable", "unidad", 10, (12, 15)),
            ("INS-007", "Solución antiséptica", "unidad", 6, (9, 2)),
            ("INS-015", "Gasa estéril", "paquete", 8, (20, 11)),
            ("INS-020", "Guantes de nitrilo", "caja", 3, (4, 5)),
        ]
        for codigo, nombre, unidad, minimo, existencias in guion:
            producto = Producto.objects.create(centro=centro, codigo=codigo, nombre=nombre,
                                               unidad=unidad)
            for sede, cantidad in zip(sedes, existencias, strict=True):
                registrar_movimiento(centro=centro, usuario=usuario, sede_id=sede.pk,
                                     producto_id=producto.pk, tipo="ENTRADA", cantidad=cantidad,
                                     motivo="Inventario inicial de la demostración")
            Stock.objects.filter(producto=producto).update(minimo=minimo)

        # Insumos habituales (CC-14), para que P11 los precargue. Son datos de
        # la demostración, no una indicación clínica.
        habituales = {
            "Quiropodia general": [("INS-001", 1), ("INS-015", 1)],
            "Tratamiento de onicomicosis": [("INS-001", 1)],
            "Tratamiento de onicocriptosis": [("INS-015", 1), ("INS-011", 1)],
        }
        productos = {p.codigo: p for p in Producto.objects.filter(centro=centro)}
        for servicio in Servicio.objects.filter(centro=centro, nombre__in=habituales):
            for codigo, cantidad in habituales[servicio.nombre]:
                ServicioInsumo.objects.create(centro=centro, servicio=servicio,
                                              producto=productos[codigo], cantidad=cantidad)

    def _citas_en_curso(self, centro, sedes, podologas, servicios, pacientes, usuario):
        """Siembra una cita por podóloga que empezó hace 10 minutos.

        Desde que no se puede registrar la atención de una cita que todavía no
        llega (cita-aun-no-llega), una demostración recién cargada no tenía
        ninguna cita atendible: el resto de la agenda empieza en el futuro.
        Estas se crean directamente y no con programar_cita, que exige 15
        minutos de anticipación; por eso solo existen en la demostración.

        Usan el servicio más corto: terminan antes de que empiece la primera
        cita del guion de hoy, que va al menos 20 minutos por delante. Si aun
        así chocaran, la restricción EXCLUDE lo impide y la cita se omite.
        Fuera del horario de la sede (por ejemplo, de noche) se crean igual:
        sirven para atender, no para mostrar una agenda realista.
        """
        corto = min(servicios, key=lambda s: s.duracion_minutos)
        con_antecedentes = [p for p in pacientes if p.antecedentes] or pacientes
        inicio = timezone.localtime().replace(second=0, microsecond=0) - timedelta(minutes=10)
        creadas = 0
        # Lucía en Cercado y Karina en Bustamante: cada una en una sede que tiene.
        for indice, (podologa, sede) in enumerate(zip(podologas, sedes, strict=False)):
            paciente = con_antecedentes[indice % len(con_antecedentes)]
            try:
                with transaction.atomic():
                    Cita.objects.create(
                        centro=centro, sede=sede, paciente=paciente, profesional=podologa,
                        servicio=corto, inicio=inicio,
                        fin=inicio + timedelta(minutes=corto.duracion_minutos),
                        creada_por=usuario,
                    )
                creadas += 1
            except IntegrityError:
                self.stdout.write(self.style.WARNING(
                    f"  cita en curso omitida para {podologa.nombre_completo}: se solapaba."))
        if creadas:
            self.stdout.write(f"  {creadas} cita(s) en curso desde las {inicio:%H:%M}, "
                              "lista(s) para registrar la atención.")
        return creadas

    def _variar_estados(self, centro):
        """Deja la jornada con estados variados.

        Un panel donde todo está «Programada» no deja ver los segmentos de
        ingreso confirmado ni de ingreso no concretado, ni sirve para probar
        el filtro por estado de la agenda.
        """
        del_dia = list(
            Cita.objects.filter(centro=centro, inicio__date=timezone.localdate())
            .order_by("inicio")
        )
        if len(del_dia) >= 2:
            atendida = del_dia[0]
            atendida.estado = Cita.Estado.ATENDIDA
            atendida.save(update_fields=["estado", "periodo", "actualizado_en"])
        if len(del_dia) >= 4:
            cancelar_cita(cita=del_dia[-1], motivo="El paciente avisó que no podrá asistir.")

    def _sedes(self, centro):
        datos = [
            ("Sede Cercado", "Calle Santa Marta 215, Cercado, Arequipa", "054-281940"),
            ("Sede Bustamante", "Av. Dolores 320, José Luis Bustamante y Rivero", "054-427315"),
        ]
        sedes = []
        for nombre, direccion, telefono in datos:
            sede = Sede.objects.create(
                centro=centro, nombre=nombre, direccion=direccion, telefono=telefono
            )
            for dia in range(0, 6):  # lunes a sábado
                HorarioSede.objects.create(
                    sede=sede,
                    dia_semana=dia,
                    hora_apertura=time(8, 0),
                    hora_cierre=time(19, 0) if dia < 5 else time(13, 0),
                )
            sedes.append(sede)
        return sedes

    def _usuarios(self, centro, sedes):
        plataforma = Usuario.objects.create_superuser(
            correo=CORREO_PLATAFORMA,
            password=CLAVE,
            nombres="Soporte",
            apellidos="Podocenter",
            rol=Rol.ADMIN_PLATAFORMA,
        )
        plataforma.segundo_factor_activo = True
        plataforma.save(update_fields=["segundo_factor_activo"])

        admin_centro = Usuario.objects.create_user(
            correo="gerencia@piessanos.pe", password=CLAVE, nombres="Elsa",
            apellidos="Rodríguez Paredes", rol=Rol.ADMIN_CENTRO, centro=centro,
        )
        admin_centro.is_staff = True
        admin_centro.segundo_factor_activo = True
        admin_centro.save(update_fields=["is_staff", "segundo_factor_activo"])
        for indice, sede in enumerate(sedes):
            AsignacionSede.objects.create(
                usuario=admin_centro, sede=sede, es_predeterminada=(indice == 0)
            )

        podologas = []
        for correo, nombres, apellidos, sedes_asignadas in [
            ("podologa@piessanos.pe", "Lucía", "Fernández Alarcón", sedes),
            ("k.zapata@piessanos.pe", "Karina", "Zapata Mendoza", [sedes[1]]),
        ]:
            usuario = Usuario.objects.create_user(
                correo=correo, password=CLAVE, nombres=nombres, apellidos=apellidos,
                rol=Rol.PODOLOGA, centro=centro,
            )
            for indice, sede in enumerate(sedes_asignadas):
                AsignacionSede.objects.create(
                    usuario=usuario, sede=sede, es_predeterminada=(indice == 0)
                )
            podologas.append(usuario)
        return admin_centro, podologas

    def _servicios(self, centro):
        return [
            Servicio.objects.create(
                centro=centro, nombre=nombre, descripcion=descripcion,
                duracion_minutos=duracion, precio=Decimal(precio),
            )
            for nombre, descripcion, duracion, precio in SERVICIOS
        ]

    def _pacientes(self, centro, usuario):
        creados = []
        for documento, nombres, apellidos, nacimiento, telefono, domicilio in PACIENTES:
            paciente = Paciente.objects.create(
                centro=centro, tipo_documento=Paciente.TipoDocumento.DNI,
                documento=documento, nombres=nombres, apellidos=apellidos,
                fecha_nacimiento=date.fromisoformat(nacimiento), telefono=telefono,
                correo="", domicilio=domicilio,
                antecedentes=ANTECEDENTES.get(documento, ""),
            )
            Consentimiento.objects.create(
                paciente=paciente, version_texto="v1.0",
                acepta_tratamiento_datos=True,
                acepta_recordatorios=documento not in {"70451238", "30987612"},
                canal=Consentimiento.Canal.PRESENCIAL, registrado_por=usuario,
            )
            creados.append(paciente)
        return creados

    def _agenda(self, centro, sedes, podologas, servicios, pacientes, usuario):
        """Siembra citas respetando las reglas reales de horario y solapamiento.

        El día en curso se arma a partir de la hora en que se ejecuta el
        comando, para que la agenda de hoy nunca aparezca vacía en una
        demostración; los días siguientes usan un guion fijo.
        """
        zona = timezone.get_current_timezone()
        hoy = timezone.localdate()
        ahora = timezone.localtime()

        # --- hoy: a partir del siguiente bloque de media hora
        minuto = 0 if ahora.minute < 25 else (30 if ahora.minute < 55 else 60)
        arranque = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(
            minutes=minuto + 30
        )
        plan = []
        if hoy.weekday() != 6 and arranque.hour < 17:
            # Desplazamientos en minutos desde el arranque. Para una misma
            # profesional se separan lo suficiente como para que ninguna cita
            # se solape con la anterior, que es lo que exige la regla CU08.
            guion_de_hoy = [
                (0, 0, 0, 0, 0),      # (desfase, sede, podóloga, servicio, paciente)
                (0, 1, 1, 2, 3),
                (60, 0, 0, 1, 1),
                (60, 1, 1, 0, 7),
                (135, 0, 0, 3, 6),
                (135, 1, 1, 5, 10),
                (195, 0, 0, 2, 11),
            ]
            for desfase, i_sede, i_pod, i_serv, i_pac in guion_de_hoy:
                momento = arranque + timedelta(minutes=desfase)
                if momento.hour >= 18:
                    continue
                plan.append((momento.date(), momento.hour, momento.minute,
                             i_sede, i_pod, i_serv, i_pac))

        # --- próximos días: guion fijo
        fijas = [
            (1, 8, 30, 0, 0, 0, 4), (1, 10, 0, 0, 0, 4, 8), (1, 15, 0, 0, 0, 1, 5),
            (1, 9, 0, 1, 1, 3, 9), (1, 11, 30, 1, 1, 0, 10),
            (2, 9, 0, 0, 0, 5, 0), (2, 10, 30, 0, 0, 0, 11), (2, 17, 0, 0, 0, 2, 1),
            (3, 9, 30, 1, 1, 1, 2), (3, 11, 0, 1, 1, 0, 6),
            (4, 10, 0, 0, 0, 4, 3), (4, 16, 30, 0, 0, 0, 9),
        ]
        for dias, hora, minutos, i_sede, i_pod, i_serv, i_pac in fijas:
            dia = hoy + timedelta(days=dias)
            while dia.weekday() == 6:  # la sede cierra los domingos
                dia += timedelta(days=1)
            plan.append((dia, hora, minutos, i_sede, i_pod, i_serv, i_pac))

        creadas, omitidas = 0, 0
        for dia, hora, minutos, i_sede, i_pod, i_serv, i_pac in plan:
            inicio = timezone.make_aware(datetime.combine(dia, time(hora, minutos)), zona)
            if inicio < timezone.now() + timedelta(minutes=20):
                omitidas += 1
                continue
            try:
                programar_cita(
                    centro=centro, usuario=usuario, sede=sedes[i_sede],
                    paciente=pacientes[i_pac], profesional=podologas[i_pod],
                    servicio=servicios[i_serv], inicio=inicio,
                )
                creadas += 1
            except ReglaDeNegocio as problema:
                omitidas += 1
                self.stdout.write(self.style.WARNING(
                    f"  cita omitida ({dia} {hora:02d}:{minutos:02d}): {problema.detalle}"))
        if omitidas:
            self.stdout.write(
                f"  {omitidas} cita(s) del guion no se crearon "
                "(hora ya pasada, sede cerrada o solapamiento)."
            )
        return creadas

    def _resumen(self, centro, sedes, pacientes, citas):
        linea = self.style.SUCCESS
        self.stdout.write("")
        self.stdout.write(linea(f"Centro de demostración listo: {centro.razon_social}"))
        self.stdout.write(f"  Sedes          : {len(sedes)}")
        self.stdout.write(f"  Servicios      : {Servicio.objects.filter(centro=centro).count()}")
        self.stdout.write(f"  Pacientes      : {len(pacientes)}")
        self.stdout.write(f"  Citas en agenda: {citas}")
        self.stdout.write(f"  Productos      : {Producto.objects.filter(centro=centro).count()}")
        self.stdout.write("")
        self.stdout.write("Cuentas de acceso (todas con la contraseña " + CLAVE + "):")
        for usuario in Usuario.objects.filter(
            correo__in=[CORREO_PLATAFORMA, "gerencia@piessanos.pe",
                        "podologa@piessanos.pe", "k.zapata@piessanos.pe"]
        ).order_by("rol", "correo"):
            sedes_txt = ", ".join(a.sede.nombre for a in usuario.asignaciones.all()) or "—"
            self.stdout.write(
                f"  {usuario.correo:<28} {usuario.get_rol_display():<28} sedes: {sedes_txt}"
            )
