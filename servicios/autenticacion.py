"""Registro, inicio de sesión, bloqueo por intentos fallidos y recuperación de contraseña."""
import math
import secrets
from datetime import datetime

import configuracion
from nucleo import bd, claves, tiempo
from servicios import auditoria, ciudadanos
from utilidades.errores import ErrorApp
from utilidades.validaciones import CEDULA_RE, CORREO_RE, PASSWORD_RE, coincide, validar_ciudadano

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
MENSAJE_PASSWORD = 'La contraseña debe tener mínimo 8 caracteres, una mayúscula, un número y un símbolo.'


def registrar(entrada):
    """Registro de ciudadano + cuenta. Si la cédula ya existe porque la persona radicó antes
    sin cuenta, se vincula la cuenta a su ficha cuando la fecha de expedición coincide."""
    d, errores = validar_ciudadano(entrada)
    if not d['correo']:
        errores['correo'] = 'El correo es obligatorio para crear la cuenta.'
    if not coincide(PASSWORD_RE, entrada.get('password')):
        errores['password'] = MENSAJE_PASSWORD
    if entrada.get('password') != entrada.get('confirmar_password'):
        errores['confirmar_password'] = 'Las contraseñas no coinciden.'
    if d['municipio'] and not ciudadanos.validar_municipio(d['municipio']):
        errores['municipio'] = 'Seleccione un municipio de la lista.'
    if errores:
        raise ErrorApp(400, 'Revise los campos marcados.', errores)

    resumen = claves.resumir_password(entrada['password'])
    with bd.transaccion():
        if bd.uno('SELECT 1 AS ok FROM usuario WHERE correo = ?', (d['correo'],)):
            raise ErrorApp(409, 'Ese correo ya está registrado. Inicie sesión o use otro correo.', {'correo': 'Correo en uso.'})
        existente = ciudadanos.buscar_por_cedula(d['cedula'])
        if existente:
            if existente['tiene_cuenta']:
                raise ErrorApp(409, 'Esta cédula ya tiene una cuenta. Inicie sesión o recupere su contraseña.')
            if existente['fecha_expedicion'] != d['fecha_expedicion']:
                raise ErrorApp(409, 'La cédula ya está registrada y la fecha de expedición no coincide con nuestros registros.')
            id_ciudadano = existente['id_ciudadano']
            ciudadanos.actualizar(id_ciudadano, d)       # se actualiza con los datos más recientes
        else:
            id_ciudadano = ciudadanos.crear(d)
        id_usuario = bd.insertar(
            """INSERT INTO usuario (id_ciudadano, nombre, correo, password_hash, rol, fecha_creacion)
               VALUES (?, ?, ?, ?, 'CIUDADANO', ?)""",
            (id_ciudadano, f"{d['nombres']} {d['apellidos']}", d['correo'], resumen, tiempo.ahora()))
    return {'id_usuario': id_usuario, 'rol': 'CIUDADANO', 'vinculado': bool(existente)}


def _revisar_bloqueo(u):
    if u['bloqueado_hasta'] and u['bloqueado_hasta'] > tiempo.ahora():
        faltan = datetime.fromisoformat(u['bloqueado_hasta']) - datetime.now(configuracion.ZONA_COLOMBIA)
        minutos = max(1, math.ceil(faltan.total_seconds() / 60))
        raise ErrorApp(429, f'Cuenta bloqueada temporalmente por intentos fallidos. Intente de nuevo en {minutos} minuto(s).')


def _contar_fallo(u):
    """Suma un intento fallido; al llegar a MAX_INTENTOS bloquea la cuenta MINUTOS_BLOQUEO minutos."""
    intentos = u['intentos_fallidos'] + 1
    if intentos >= MAX_INTENTOS:
        bd.ejecutar('UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = ? WHERE id_usuario = ?',
                    (tiempo.dentro_de(minutos=MINUTOS_BLOQUEO), u['id_usuario']))
        raise ErrorApp(429, f'Superó {MAX_INTENTOS} intentos fallidos. Su cuenta quedó bloqueada {MINUTOS_BLOQUEO} minutos.')
    bd.ejecutar('UPDATE usuario SET intentos_fallidos = ? WHERE id_usuario = ?', (intentos, u['id_usuario']))


def iniciar_sesion(identificador, password):
    """Ingreso con correo o cédula. Bloquea la cuenta 15 minutos tras 5 intentos fallidos."""
    ident = str(identificador or '').strip().lower()
    if not ident or not password:
        raise ErrorApp(400, 'Escriba su usuario y contraseña.')
    # El nombre de la columna sale de una lista fija; el dato del usuario va como parámetro ?
    campo = 'c.cedula' if coincide(CEDULA_RE, ident) else 'u.correo'
    u = bd.uno(f'SELECT u.* FROM usuario u LEFT JOIN ciudadano c ON c.id_ciudadano = u.id_ciudadano WHERE {campo} = ?', (ident,))

    if u:
        _revisar_bloqueo(u)

    valida = claves.verificar_password(password, u['password_hash'] if u else claves.RESUMEN_FICTICIO)
    if not u or not valida or not u['activo']:
        if u and not valida:
            _contar_fallo(u)
        if u and valida and not u['activo']:
            raise ErrorApp(403, 'Su cuenta está desactivada. Comuníquese con la entidad.')
        raise ErrorApp(401, 'Usuario o contraseña incorrectos.')

    bd.ejecutar('UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = ?', (u['id_usuario'],))
    return u


def solicitar_recuperacion(correo, origen):
    """Genera un enlace para crear una contraseña nueva. En desarrollo se muestra en la terminal."""
    c = str(correo or '').strip().lower()
    if not coincide(CORREO_RE, c):
        raise ErrorApp(400, 'Escriba un correo válido.')
    token = secrets.token_hex(32)
    cambios = bd.ejecutar('UPDATE usuario SET reset_token_hash = ?, reset_expira = ? WHERE correo = ? AND activo = 1',
                          (claves.resumen_sha256(token), tiempo.dentro_de(minutos=30), c))
    if cambios:  # en producción aquí se enviaría un correo electrónico
        print(f'\n[RECUPERACIÓN DE CONTRASEÑA] Enlace para {c} (válido 30 min):\n{origen}/restablecer.html?token={token}\n', flush=True)
    # Siempre la misma respuesta: no se revela si el correo existe


def restablecer(token, password):
    if not coincide(PASSWORD_RE, password):
        raise ErrorApp(400, MENSAJE_PASSWORD)
    cambios = bd.ejecutar(
        """UPDATE usuario SET password_hash = ?, reset_token_hash = NULL, reset_expira = NULL,
                  intentos_fallidos = 0, bloqueado_hasta = NULL, debe_cambiar_password = 0
            WHERE reset_token_hash = ? AND reset_expira > ?""",
        (claves.resumir_password(password), claves.resumen_sha256(str(token or '')), tiempo.ahora()))
    if not cambios:
        raise ErrorApp(400, 'El enlace no es válido o ya venció. Solicite uno nuevo.')


def confirmar_password(id_usuario, password):
    """Pide de nuevo la contraseña antes de una acción delicada (eliminar la cuenta, corregir el documento).
    Los errores cuentan igual que en el inicio de sesión: 5 seguidos bloquean la cuenta 15 minutos."""
    u = bd.uno('SELECT id_usuario, password_hash, intentos_fallidos, bloqueado_hasta FROM usuario WHERE id_usuario = ?', (id_usuario,))
    if not u:
        raise ErrorApp(401, 'Debe iniciar sesión para continuar.')
    _revisar_bloqueo(u)
    if not claves.verificar_password(password or '', u['password_hash']):
        _contar_fallo(u)
        raise ErrorApp(400, 'La contraseña no es correcta.', {'password': 'La contraseña no es correcta.'})
    bd.ejecutar('UPDATE usuario SET intentos_fallidos = 0 WHERE id_usuario = ?', (id_usuario,))


def eliminar_cuenta(usuario, password, confirmacion):
    """El ciudadano se desvincula del portal: se borra su cuenta (usuario y contraseña).
    - Si nunca radicó solicitudes, también se borran sus datos personales.
    - Si tiene solicitudes, su ficha se conserva: la entidad debe responderlas y archivarlas por ley
      (Ley 1755 de 2015 y Ley 594 de 2000). Las puede seguir consultando con el radicado y su cédula,
      y si vuelve a registrarse con la misma cédula y fecha de expedición, se le vinculan de nuevo."""
    if usuario['rol'] != 'CIUDADANO':
        raise ErrorApp(403, 'Las cuentas de funcionarios y administradores las desactiva el administrador desde el panel.')
    if str(confirmacion or '').strip().upper() != 'ELIMINAR':
        raise ErrorApp(400, 'Escriba ELIMINAR para confirmar.', {'confirmacion': 'Escriba ELIMINAR para confirmar.'})
    confirmar_password(usuario['id_usuario'], password)

    id_usuario, id_ciudadano = usuario['id_usuario'], usuario['id_ciudadano']
    with bd.transaccion():
        # Las acciones de esta persona quedan en el historial, pero ya sin enlace a una cuenta que no existe
        bd.ejecutar('UPDATE pqrds SET id_usuario_radicador = NULL WHERE id_usuario_radicador = ?', (id_usuario,))
        bd.ejecutar('UPDATE pqrds_historial SET id_usuario = NULL WHERE id_usuario = ?', (id_usuario,))
        bd.ejecutar('UPDATE auditoria SET id_usuario = NULL WHERE id_usuario = ?', (id_usuario,))
        bd.ejecutar('DELETE FROM usuario WHERE id_usuario = ?', (id_usuario,))
        solicitudes = bd.uno('SELECT COUNT(*) AS n FROM pqrds WHERE id_ciudadano = ?', (id_ciudadano,))['n']
        if not solicitudes:
            bd.ejecutar('DELETE FROM ciudadano WHERE id_ciudadano = ?', (id_ciudadano,))
        auditoria.registrar('ELIMINAR_CUENTA', f'Ciudadano #{id_ciudadano} eliminó su cuenta. '
                            + (f'Datos conservados por {solicitudes} solicitud(es) radicada(s).' if solicitudes
                               else 'Sin solicitudes: se borraron también sus datos personales.'), sin_usuario=True)
    return {'datos_conservados': bool(solicitudes), 'solicitudes': solicitudes}


def cambiar_password(id_usuario, actual, nueva):
    if not coincide(PASSWORD_RE, nueva):
        raise ErrorApp(400, MENSAJE_PASSWORD)
    if actual == nueva:
        raise ErrorApp(400, 'La nueva contraseña debe ser diferente a la actual.')
    fila = bd.uno('SELECT password_hash FROM usuario WHERE id_usuario = ?', (id_usuario,))
    if not fila or not claves.verificar_password(actual or '', fila['password_hash']):
        raise ErrorApp(400, 'La contraseña actual no es correcta.')
    bd.ejecutar('UPDATE usuario SET password_hash = ?, debe_cambiar_password = 0 WHERE id_usuario = ?',
                (claves.resumir_password(nueva), id_usuario))
