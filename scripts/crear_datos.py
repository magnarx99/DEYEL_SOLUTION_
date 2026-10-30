"""Crea la base de datos desde cero.

Uso (desde la carpeta del proyecto):
    python scripts/crear_datos.py           base con datos de prueba FICTICIOS (para estudiar y hacer pruebas)
    python scripts/crear_datos.py --vacia   base limpia: solo catálogos y el administrador (para datos reales)

¡Atención! Borra y vuelve a crear todas las tablas. Si ya hay datos, primero
hace una copia de seguridad en database/respaldos/ y pide confirmación.
(Agregue --si para no preguntar; lo usan las pruebas automáticas.)
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # para importar los módulos del proyecto

import configuracion  # noqa: E402
from nucleo import bd, claves  # noqa: E402
from servicios.fechas import sumar_dias_habiles  # noqa: E402
from scripts.respaldar import contar_registros, respaldar  # noqa: E402

VACIA = '--vacia' in sys.argv
SIN_PREGUNTAR = '--si' in sys.argv

azar = random.Random(20261026)   # semilla fija: los datos de prueba son siempre los mismos

FUNCIONARIOS = [   # nombre, correo, dependencia (también los usa scripts/crear_funcionarios.py)
    ('Carolina Mesa Ruiz', 'funcionario.ciudadania@antioquia.example', 'Atención a la Ciudadanía'),
    ('Santiago Herrera Gil', 'funcionario.salud@antioquia.example', 'Secretaría de Salud y Protección Social'),
    ('Paula Andrea Duque', 'funcionario.educacion@antioquia.example', 'Secretaría de Educación'),
]
CLAVE_FUNCIONARIOS = 'Funcionario2026*'

CIUDADANOS = [
    # cédula, nombres, apellidos, municipio, barrio, celular, correo, sexo, grupo
    ('1017234567', 'María Fernanda', 'Restrepo Gómez', 'Medellín', 'Laureles', '3001234521', 'maria.restrepo@correo.example', 'FEMENINO', 'NINGUNO'),
    ('43512876', 'Luz Dary', 'Cardona Arango', 'Bello', 'Niquía', '3104567890', 'luzdary.cardona@correo.example', 'FEMENINO', 'ADULTO_MAYOR'),
    ('71654321', 'Jorge Iván', 'Zapata Ospina', 'Rionegro', 'San Antonio', '3157778899', 'jorge.zapata@correo.example', 'MASCULINO', 'NINGUNO'),
    ('1036987654', 'Andrés Felipe', 'Mejía Londoño', 'Envigado', 'El Dorado', '3012223344', 'andres.mejia@correo.example', 'MASCULINO', 'NINGUNO'),
    ('1152443322', 'Valentina', 'Ríos Henao', 'Itagüí', 'Santa María', '3205556677', 'valentina.rios@correo.example', 'FEMENINO', 'NINGUNO'),
    ('8345612', 'Gilberto', 'Úsuga Durango', 'Apartadó', 'Ortiz', '3118889900', None, 'MASCULINO', 'VICTIMA_CONFLICTO'),
    ('39456123', 'Rosa Elena', 'Palacios Mosquera', 'Turbo', 'El Bosque', '3126665544', 'rosa.palacios@correo.example', 'FEMENINO', 'AFRODESCENDIENTE'),
    ('1040765432', 'Camilo', 'Agudelo Vélez', 'Marinilla', 'La Primavera', '3001112233', 'camilo.agudelo@correo.example', 'MASCULINO', 'NINGUNO'),
    ('1001234987', 'Daniela', 'Osorio Castaño', 'Caucasia', 'El Palmar', '3148887766', 'daniela.osorio@correo.example', 'FEMENINO', 'NINGUNO'),
    ('15432198', 'Hernán Darío', 'Montoya Correa', 'Santa Fe de Antioquia', 'Centro', '3176543210', None, 'MASCULINO', 'PERSONA_CON_DISCAPACIDAD'),
    ('1128765409', 'Sara', 'Bedoya Quintero', 'Sabaneta', 'Las Vegas', '3019998877', 'sara.bedoya@correo.example', 'FEMENINO', 'NINGUNO'),
    ('70123456', 'Luis Alberto', 'Gallego Muñoz', 'Yarumal', 'El Llano', '3137776655', 'luis.gallego@correo.example', 'MASCULINO', 'ADULTO_MAYOR'),
    ('1214723456', 'Juliana', 'Tobón Arias', 'La Ceja', 'Payuco', '3162224466', 'juliana.tobon@correo.example', 'FEMENINO', 'NINGUNO'),
    ('98765432', 'Óscar Mauricio', 'Pérez Holguín', 'Puerto Berrío', 'Pueblo Nuevo', '3183335577', 'oscar.perez@correo.example', 'MASCULINO', 'NINGUNO'),
    ('1037612345', 'Natalia', 'Vargas Echeverri', 'Sonsón', 'Centro', '3114446688', 'natalia.vargas@correo.example', 'FEMENINO', 'INDIGENA'),
]

CASOS = {
    'PETICION': [('Solicitud de mantenimiento de vía terciaria', 'Solicito el mantenimiento de la vía que comunica la vereda con la cabecera municipal; con las lluvias está intransitable y los niños no pueden llegar a la escuela.'),
                 ('Certificado laboral como exfuncionario', 'Trabajé en la Gobernación entre 2015 y 2019 y necesito un certificado laboral con funciones y salario para un trámite de pensión.'),
                 ('Inclusión en programa de vivienda rural', 'Solicito información y la inclusión de mi familia en el programa de mejoramiento de vivienda rural del departamento.')],
    'QUEJA': [('Trato irrespetuoso en ventanilla', 'El día de ayer fui atendida en la ventanilla de pasaportes y el funcionario me habló de forma grosera y se negó a recibir mis documentos sin explicación.'),
              ('Funcionario no cumplió la cita acordada', 'Tenía una cita agendada para asesoría y el funcionario no se presentó ni avisó. Perdí el día de trabajo para asistir.')],
    'RECLAMO': [('Sin respuesta a solicitud de hace dos meses', 'Radiqué una solicitud de subsidio de transporte escolar hace más de dos meses y no he recibido ninguna respuesta de la entidad.'),
                ('Error en liquidación de impuesto vehicular', 'La liquidación del impuesto vehicular de mi moto tiene un avalúo que no corresponde al modelo. Solicito la corrección.')],
    'SUGERENCIA': [('Ampliar horario de atención los sábados', 'Sugiero habilitar atención los sábados en la sede de la Alpujarra para quienes trabajamos entre semana.'),
                   ('Atención móvil en veredas', 'Propongo jornadas de atención móvil en las veredas alejadas para que los adultos mayores puedan hacer sus trámites.')],
    'FELICITACION': [('Excelente atención en la Secretaría de Salud', 'Quiero felicitar a la funcionaria que me orientó con la afiliación de mi madre; fue muy amable, clara y resolvió todo el mismo día.')],
    'DENUNCIA': [('Posible cobro por trámite gratuito', 'En el municipio una persona está cobrando dinero por ayudar a inscribirse en un programa que es gratuito, diciendo que trabaja con la Gobernación.')],
    'INFORMACION': [('Presupuesto del programa de alimentación escolar', 'Solicito información sobre el presupuesto asignado y ejecutado del programa de alimentación escolar en mi municipio durante este año.'),
                    ('Copia de contrato de obra del puente', 'Solicito copia del contrato y el cronograma de la obra del puente vehicular que se está construyendo en la vereda.')],
    'DATOS_PERSONALES': [('Actualización de dirección en base de datos', 'Solicito actualizar mi dirección de residencia en las bases de datos de la Secretaría de Educación, porque me llegan las notificaciones a la dirección anterior.')],
    'CITA': [('Asesoría para trámite de licencia', 'Necesito una cita para recibir asesoría sobre los requisitos de la licencia de funcionamiento de un establecimiento educativo.')],
}

RESPUESTAS = [
    'Cordial saludo. Su solicitud fue revisada y remitida al equipo técnico. Se programó la atención para las próximas semanas; le informaremos la fecha exacta.',
    'Cordial saludo. Adjuntamos la información solicitada. Para cualquier inquietud adicional puede radicar una nueva solicitud citando este radicado.',
    'Cordial saludo. Lamentamos lo ocurrido. Se inició el proceso correspondiente y se reforzó la capacitación en atención a la ciudadanía.',
    'Cordial saludo. Agradecemos su mensaje; fue compartido con el equipo para reconocer su labor.',
]
COMENTARIOS = {'EN_TRAMITE': 'Asignada para gestión.', 'TRASLADADA': 'Trasladada por competencia.',
               'RESPONDIDA': 'Se registró respuesta al ciudadano.', 'CERRADA': 'Caso cerrado.'}
PASOS = {'EN_TRAMITE': ['EN_TRAMITE'], 'TRASLADADA': ['EN_TRAMITE', 'TRASLADADA'],
         'RESPONDIDA': ['EN_TRAMITE', 'RESPONDIDA'], 'CERRADA': ['EN_TRAMITE', 'RESPONDIDA', 'CERRADA']}


def iso(momento):
    return momento.isoformat(timespec='seconds')


def confirmar_borrado():
    """Si la base ya tiene información, hace una copia de seguridad y pide confirmación antes de borrar."""
    totales = contar_registros()
    if not totales or not any(totales.values()):
        return
    copia = respaldar('antes_de_borrar')
    print('La base de datos actual tiene información:')
    print(f"  {totales['ciudadano']} ciudadanos, {totales['pqrds']} PQRDS y {totales['usuario']} usuarios.")
    print(f'Por seguridad se guardó una copia en: {copia.relative_to(configuracion.RAIZ)}')
    if SIN_PREGUNTAR:
        return
    respuesta = input('Este comando BORRA todo y empieza de cero. Para continuar escriba BORRAR y pulse Enter: ')
    if respuesta.strip().upper() != 'BORRAR':
        print('Cancelado. No se borró nada.')
        sys.exit(0)


def main():
    zona = configuracion.ZONA_COLOMBIA
    ahora = datetime.now(zona).replace(microsecond=0)
    texto_ahora = iso(ahora)
    confirmar_borrado()

    print('1/5 Creando tablas...')
    configuracion.CARPETA_BD.mkdir(exist_ok=True)
    bd.ejecutar_script((configuracion.CARPETA_BD / 'schema.sql').read_text(encoding='utf-8'))
    print('2/5 Cargando catálogos (municipios, dependencias, tipos, festivos, preguntas frecuentes)...')
    bd.ejecutar_script((configuracion.CARPETA_BD / 'datos_iniciales.sql').read_text(encoding='utf-8'))
    bd.migrar()

    with bd.transaccion():
        deps = {d['nombre']: d['id_dependencia'] for d in bd.consultar('SELECT id_dependencia, nombre FROM dependencia')}
        tipos = {t['codigo']: t for t in bd.consultar('SELECT * FROM tipo_solicitud')}

        print('3/5 Creando el administrador' + ('...' if VACIA else ' y los funcionarios de prueba...'))
        id_admin = bd.insertar("""INSERT INTO usuario (nombre, correo, password_hash, rol, debe_cambiar_password, fecha_creacion)
                                  VALUES (?, ?, ?, 'ADMIN', 1, ?)""",
                               (configuracion.ADMIN_NOMBRE, configuracion.ADMIN_CORREO.lower(),
                                claves.resumir_password(configuracion.ADMIN_PASSWORD), texto_ahora))
        if VACIA:
            print('4/5 y 5/5 Sin datos de prueba (opción --vacia).')
            print('\nBase de datos VACÍA lista en database/pqrds.db, para empezar a cargar información real.')
            print(f'  Administrador: {configuracion.ADMIN_CORREO} / {configuracion.ADMIN_PASSWORD} (se pide cambiarla al entrar)')
            print('  Los funcionarios se crean desde el panel: Usuarios > Nuevo usuario.')
            print('  (O agregue los funcionarios de prueba sin borrar nada: python scripts/crear_funcionarios.py)')
            return
        clave_funcionario = claves.resumir_password(CLAVE_FUNCIONARIOS)
        funcionarios = []
        for nombre, correo, dependencia in FUNCIONARIOS:
            id_f = bd.insertar("""INSERT INTO usuario (nombre, correo, password_hash, rol, id_dependencia, fecha_creacion)
                                  VALUES (?, ?, ?, 'FUNCIONARIO', ?, ?)""", (nombre, correo, clave_funcionario, deps[dependencia], texto_ahora))
            funcionarios.append({'id_usuario': id_f, 'id_dependencia': deps[dependencia]})

        print('4/5 Creando 15 ciudadanos de prueba...')
        ciudadanos = []
        for i, c in enumerate(CIUDADANOS):
            anio_nacimiento = 1950 + azar.randrange(55)
            mes, dia = 1 + i % 9, 10 + i % 9
            id_c = bd.insertar(
                """INSERT INTO ciudadano (tipo_documento, cedula, fecha_expedicion, nombres, apellidos, fecha_nacimiento, sexo,
                     grupo_poblacional, municipio, barrio, direccion, telefono, correo, notificacion_preferida,
                     acepta_tratamiento_datos, fecha_creacion, fecha_actualizacion)
                   VALUES ('CC',?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (c[0], f'{anio_nacimiento + 18}-{mes:02d}-{dia:02d}', c[1], c[2], f'{anio_nacimiento}-{mes:02d}-{dia:02d}',
                 c[7], c[8], c[3], c[4], f'Calle {10 + i} # {20 + i}-{30 + i}', c[5], c[6], 'CORREO' if c[6] else 'SMS',
                 iso(ahora - timedelta(days=200)), iso(ahora - timedelta(days=200))))
            ciudadanos.append({'id': id_c, 'correo': c[6]})
        # Tres ciudadanos con cuenta para probar "Mis solicitudes"
        clave_ciudadano = claves.resumir_password('Ciudadano2026*')
        for idx in (0, 1, 3):
            c = CIUDADANOS[idx]
            bd.insertar("""INSERT INTO usuario (id_ciudadano, nombre, correo, password_hash, rol, fecha_creacion)
                           VALUES (?, ?, ?, ?, 'CIUDADANO', ?)""", (ciudadanos[idx]['id'], f'{c[1]} {c[2]}', c[6], clave_ciudadano, texto_ahora))

        print('5/5 Radicando 40 PQRDS de prueba en distintos estados...')
        municipios = [m['nombre'] for m in bd.consultar('SELECT nombre FROM municipio')]
        lista_deps = list(deps.values())
        codigos = list(CASOS)
        momentos = sorted(ahora - timedelta(days=150 - i * 3.7 - azar.random() * 2) for i in range(40))
        consecutivo = {}
        for i, momento in enumerate(momentos):
            codigo = codigos[i] if i < len(codigos) else azar.choice(codigos)
            tipo = tipos[codigo]
            asunto, descripcion = azar.choice(CASOS[codigo])
            anonima = codigo == 'DENUNCIA' and i % 2 == 0
            ciudadano = None if anonima else (ciudadanos[0] if i < 6 else azar.choice(ciudadanos))
            fecha = momento.date().isoformat()
            consecutivo[momento.year] = consecutivo.get(momento.year, 0) + 1
            radicado = f'PQRDS-{momento.year}-{consecutivo[momento.year]:06d}'
            dias = (ahora - momento).days
            estado = 'RADICADA'                      # estados más avanzados para las solicitudes más antiguas
            if dias > 60:
                estado = azar.choice(['RESPONDIDA', 'CERRADA', 'CERRADA', 'EN_TRAMITE'])
            elif dias > 20:
                estado = azar.choice(['EN_TRAMITE', 'RESPONDIDA', 'RADICADA', 'TRASLADADA'])
            elif dias > 5:
                estado = azar.choice(['EN_TRAMITE', 'RADICADA'])
            asignada = estado != 'RADICADA' or azar.random() > 0.5
            dependencia = azar.choice(lista_deps) if asignada else None
            funcionario = next((f for f in funcionarios if f['id_dependencia'] == dependencia), None)
            respondida = estado in ('RESPONDIDA', 'CERRADA')
            medio = 'NINGUNO' if anonima else ('CORREO' if ciudadano['correo'] else 'FISICO')
            # La cita va después del plazo de respuesta (día hábil siguiente), igual que en el portal
            cita = sumar_dias_habiles(fecha, tipo['dias_habiles_respuesta'] + 1) if codigo == 'CITA' else None
            id_p = bd.insertar(
                """INSERT INTO pqrds (radicado, id_ciudadano, id_tipo, id_dependencia, id_funcionario_asignado, canal, municipio_hecho,
                     asunto, descripcion, medio_respuesta, fecha_cita_preferida, modalidad_cita, estado, es_anonima, codigo_anonimo,
                     fecha_radicacion, fecha_limite, fecha_respuesta, respuesta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (radicado, ciudadano['id'] if ciudadano else None, tipo['id_tipo'], dependencia,
                 funcionario['id_usuario'] if funcionario else None, azar.choice(['WEB', 'WEB', 'WEB', 'PRESENCIAL', 'TELEFONICO']),
                 azar.choice(municipios), asunto, descripcion, medio, cita, 'PRESENCIAL' if cita else None, estado, anonima,
                 f'DEMO{i:04d}' if anonima else None, iso(momento), sumar_dias_habiles(fecha, tipo['dias_habiles_respuesta']),
                 iso(momento + timedelta(days=9)) if respondida else None, azar.choice(RESPUESTAS) if respondida else None))
            bd.insertar("""INSERT INTO pqrds_historial (id_pqrds, estado_anterior, estado_nuevo, comentario, fecha)
                           VALUES (?, NULL, 'RADICADA', 'Solicitud radicada.', ?)""", (id_p, iso(momento)))
            anterior = 'RADICADA'
            for k, paso in enumerate(PASOS.get(estado, [])):
                bd.insertar("""INSERT INTO pqrds_historial (id_pqrds, estado_anterior, estado_nuevo, id_usuario, comentario, fecha)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (id_p, anterior, paso, funcionario['id_usuario'] if funcionario else id_admin, COMENTARIOS[paso],
                             iso(momento + timedelta(days=(k + 1) * 3))))
                anterior = paso
        for anio, ultimo in consecutivo.items():
            bd.insertar('INSERT INTO consecutivo_radicado (anio, ultimo) VALUES (?, ?)', (anio, ultimo))

    bd.cerrar()
    print('\nBase de datos lista en database/pqrds.db. Usuarios de prueba:')
    print(f'  Administrador: {configuracion.ADMIN_CORREO} / {configuracion.ADMIN_PASSWORD} (se pide cambiarla al entrar)')
    print(f'  Funcionario:   funcionario.ciudadania@antioquia.example / {CLAVE_FUNCIONARIOS}')
    print('  Ciudadana:     cédula 1017234567 o maria.restrepo@correo.example / Ciudadano2026*')


if __name__ == '__main__':
    main()
