"""Ciudadano: captura única de datos y reconocimiento por cédula (principio de una sola vez)."""
import sqlite3

from nucleo import bd, claves, tiempo, web
from utilidades.enmascarar import ciudadano_enmascarado
from utilidades.errores import ErrorApp
from utilidades.validaciones import validar_ciudadano

COLUMNAS = """c.id_ciudadano, c.tipo_documento, c.cedula, c.fecha_expedicion, c.nombres, c.apellidos,
  c.fecha_nacimiento, c.sexo, c.grupo_poblacional, c.municipio, c.barrio, c.direccion, c.telefono,
  c.telefono_fijo, c.correo, c.notificacion_preferida, c.fecha_creacion, c.fecha_actualizacion"""


def buscar_por_cedula(cedula):
    """Busca por cédula (columna única con índice). Incluye si la persona ya tiene cuenta."""
    return bd.uno(f"""SELECT {COLUMNAS}, (u.id_usuario IS NOT NULL) AS tiene_cuenta
                        FROM ciudadano c LEFT JOIN usuario u ON u.id_ciudadano = c.id_ciudadano
                       WHERE c.cedula = ?""", (cedula,))


def buscar_por_id(id_ciudadano):
    return bd.uno(f'SELECT {COLUMNAS} FROM ciudadano c WHERE c.id_ciudadano = ?', (id_ciudadano,))


def puede_ver_completo(usuario, ciudadano):
    """Funcionarios, administradores y el propio titular ven los datos completos."""
    return web.es_personal(usuario) or (usuario is not None and usuario['id_ciudadano'] == ciudadano['id_ciudadano'])


def presentar(usuario, ciudadano):
    """Respuesta del reconocimiento por cédula según quién consulta."""
    if puede_ver_completo(usuario, ciudadano):
        datos = {k: v for k, v in ciudadano.items() if k != 'tiene_cuenta'}
        return {'encontrado': True, 'completo': True, 'tiene_cuenta': ciudadano['tiene_cuenta'], 'ciudadano': datos}
    return {'encontrado': True, 'completo': False, 'requiereVerificacion': True, 'ciudadano': ciudadano_enmascarado(ciudadano)}


def validar_municipio(nombre):
    return bd.uno('SELECT 1 AS ok FROM municipio WHERE nombre = ?', (nombre,)) is not None


def crear(entrada):
    """Valida y registra a un ciudadano por primera vez. Error 409 si la cédula ya existe."""
    d, errores = validar_ciudadano(entrada)
    if d['municipio'] and not validar_municipio(d['municipio']):
        errores['municipio'] = 'Seleccione un municipio de la lista.'
    if errores:
        raise ErrorApp(400, 'Revise los datos personales marcados.', errores)
    ahora = tiempo.ahora()
    try:
        return bd.insertar(
            """INSERT INTO ciudadano (tipo_documento, cedula, fecha_expedicion, nombres, apellidos, fecha_nacimiento,
                 sexo, grupo_poblacional, municipio, barrio, direccion, telefono, telefono_fijo, correo,
                 notificacion_preferida, acepta_tratamiento_datos, fecha_creacion, fecha_actualizacion)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d['tipo_documento'], d['cedula'], d['fecha_expedicion'], d['nombres'], d['apellidos'], d['fecha_nacimiento'],
             d['sexo'], d['grupo_poblacional'], d['municipio'], d['barrio'], d['direccion'], d['telefono'],
             d['telefono_fijo'], d['correo'], d['notificacion_preferida'], d['acepta_tratamiento_datos'], ahora, ahora))
    except sqlite3.IntegrityError as err:
        if 'ciudadano.cedula' in str(err):
            raise ErrorApp(409, 'La cédula ya está registrada.') from err
        raise


def actualizar(id_ciudadano, entrada):
    """Actualiza datos personales y de contacto (la cédula y la fecha de expedición no cambian)."""
    d, errores = validar_ciudadano(entrada, parcial=True)
    if d['municipio'] and not validar_municipio(d['municipio']):
        errores['municipio'] = 'Seleccione un municipio de la lista.'
    if errores:
        raise ErrorApp(400, 'Revise los datos marcados.', errores)
    cambios = bd.ejecutar(
        """UPDATE ciudadano SET nombres=?, apellidos=?, fecha_nacimiento=?, sexo=?, grupo_poblacional=?, municipio=?,
                  barrio=?, direccion=?, telefono=?, telefono_fijo=?, correo=?, notificacion_preferida=?, fecha_actualizacion=?
            WHERE id_ciudadano=?""",
        (d['nombres'], d['apellidos'], d['fecha_nacimiento'], d['sexo'], d['grupo_poblacional'], d['municipio'],
         d['barrio'], d['direccion'], d['telefono'], d['telefono_fijo'], d['correo'], d['notificacion_preferida'],
         tiempo.ahora(), id_ciudadano))
    if not cambios:
        raise ErrorApp(404, 'Ciudadano no encontrado.')


def emitir_token_verificacion(id_ciudadano):
    """Ficha temporal (30 min) que permite radicar sin volver a digitar los datos."""
    return claves.crear_ficha({'tipo': 'verificacion', 'idc': id_ciudadano}, 30 * 60)


def leer_token_verificacion(token):
    datos = claves.leer_ficha(token)
    return datos.get('idc') if datos and datos.get('tipo') == 'verificacion' else None


def verificar_identidad(cedula, entrada):
    """Un visitante confirma su identidad con la fecha de expedición o el correo registrado."""
    c = buscar_por_cedula(cedula)
    if not c:
        raise ErrorApp(404, 'No encontramos esa cédula.')
    fecha = entrada.get('fecha_expedicion')
    correo = entrada.get('correo')
    coincide_fecha = bool(fecha) and fecha == c['fecha_expedicion']
    coincide_correo = bool(correo) and bool(c['correo']) and str(correo).strip().lower() == c['correo']
    if not coincide_fecha and not coincide_correo:
        raise ErrorApp(400, 'El dato no coincide con nuestros registros. Verifique e intente de nuevo.')
    return {'token': emitir_token_verificacion(c['id_ciudadano']), 'ciudadano': ciudadano_enmascarado(c)}
