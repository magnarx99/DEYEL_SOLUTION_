"""Gestión de usuarios del sistema (solo administrador)."""
import sqlite3

from nucleo import bd, claves, tiempo
from servicios.autenticacion import MENSAJE_PASSWORD
from utilidades.errores import ErrorApp
from utilidades.validaciones import CORREO_RE, PASSWORD_RE, coincide, texto

ROLES = ['CIUDADANO', 'FUNCIONARIO', 'ADMIN']


def listar(rol=None, q=None):
    cond, params = [], []
    if rol in ROLES:
        cond.append('u.rol = ?'); params.append(rol)
    if q:
        patron = f'%{str(q)[:80]}%'
        cond.append('(u.nombre LIKE ? OR u.correo LIKE ? OR c.cedula LIKE ?)'); params += [patron] * 3
    return bd.consultar(f"""SELECT u.id_usuario, u.nombre, u.correo, u.rol, u.activo, u.id_dependencia, d.nombre AS dependencia,
                                   c.cedula, u.fecha_creacion, u.debe_cambiar_password,
                                   (u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > ?) AS bloqueado
                              FROM usuario u
                              LEFT JOIN dependencia d ON d.id_dependencia = u.id_dependencia
                              LEFT JOIN ciudadano c ON c.id_ciudadano = u.id_ciudadano
                              {('WHERE ' + ' AND '.join(cond)) if cond else ''}
                             ORDER BY u.rol, u.nombre LIMIT 500""", [tiempo.ahora()] + params)


def funcionarios():
    """Lista corta de funcionarios activos para asignar casos."""
    return bd.consultar("""SELECT u.id_usuario, u.nombre, u.id_dependencia, d.nombre AS dependencia FROM usuario u
                             LEFT JOIN dependencia d ON d.id_dependencia = u.id_dependencia
                            WHERE u.rol IN ('FUNCIONARIO','ADMIN') AND u.activo = 1 ORDER BY u.nombre""")


def crear_personal(entrada):
    """Crea un funcionario o administrador con contraseña temporal (debe cambiarla al entrar)."""
    dep = entrada.get('id_dependencia')
    d = {'nombre': texto(entrada.get('nombre')), 'correo': texto(entrada.get('correo')).lower(), 'rol': entrada.get('rol'),
         'id_dependencia': int(dep) if str(dep or '').isdigit() else None, 'password': entrada.get('password') or ''}
    e = {}
    if len(d['nombre']) < 3:
        e['nombre'] = 'Escriba el nombre completo.'
    if not coincide(CORREO_RE, d['correo']):
        e['correo'] = 'Correo no válido.'
    if d['rol'] not in ('FUNCIONARIO', 'ADMIN'):
        e['rol'] = 'Seleccione Funcionario o Administrador.'
    if d['rol'] == 'FUNCIONARIO' and not d['id_dependencia']:
        e['id_dependencia'] = 'Seleccione la dependencia del funcionario.'
    if not coincide(PASSWORD_RE, d['password']):
        e['password'] = MENSAJE_PASSWORD
    if e:
        raise ErrorApp(400, 'Revise los campos marcados.', e)
    try:
        nuevo = bd.insertar("""INSERT INTO usuario (nombre, correo, password_hash, rol, id_dependencia, debe_cambiar_password, fecha_creacion)
                               VALUES (?, ?, ?, ?, ?, 1, ?)""",
                            (d['nombre'], d['correo'], claves.resumir_password(d['password']), d['rol'], d['id_dependencia'], tiempo.ahora()))
    except sqlite3.IntegrityError as err:
        if 'usuario.correo' in str(err):
            raise ErrorApp(409, 'Ya existe un usuario con ese correo.', {'correo': 'Correo en uso.'}) from err
        raise
    return {'id_usuario': nuevo}


def actualizar(id_usuario, cambios, quien):
    """Activa o desactiva, cambia rol o dependencia, o desbloquea una cuenta."""
    u = bd.uno('SELECT * FROM usuario WHERE id_usuario = ?', (id_usuario,))
    if not u:
        raise ErrorApp(404, 'Usuario no encontrado.')
    if u['id_usuario'] == quien['id_usuario'] and (cambios.get('activo') is False or (cambios.get('rol') and cambios['rol'] != 'ADMIN')):
        raise ErrorApp(400, 'No puede desactivarse ni quitarse el rol de administrador a sí mismo.')
    rol = cambios.get('rol') or u['rol']
    if rol not in ROLES:
        raise ErrorApp(400, 'Rol no válido.')
    if rol == 'CIUDADANO' and not u['id_ciudadano']:
        raise ErrorApp(400, 'Este usuario no tiene ficha de ciudadano; no puede tener rol Ciudadano.')
    id_dependencia = u['id_dependencia']
    if 'id_dependencia' in cambios:
        id_dependencia = int(cambios['id_dependencia']) if str(cambios['id_dependencia'] or '').isdigit() else None
    if rol == 'FUNCIONARIO' and not id_dependencia:
        raise ErrorApp(400, 'Un funcionario debe pertenecer a una dependencia.')
    activo = cambios['activo'] if isinstance(cambios.get('activo'), bool) else u['activo']
    desbloquear = cambios.get('desbloquear') is True
    bd.ejecutar("""UPDATE usuario SET rol = ?, id_dependencia = ?, activo = ?,
                          intentos_fallidos = CASE WHEN ? THEN 0 ELSE intentos_fallidos END,
                          bloqueado_hasta = CASE WHEN ? THEN NULL ELSE bloqueado_hasta END
                    WHERE id_usuario = ?""", (rol, id_dependencia, activo, desbloquear, desbloquear, id_usuario))
    return {'id_usuario': id_usuario, 'rol': rol, 'activo': activo, 'id_dependencia': id_dependencia, 'nombre': u['nombre']}
