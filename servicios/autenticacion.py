"""Registro, inicio de sesión, bloqueo por intentos fallidos y recuperación de contraseña."""
import math
import secrets
from datetime import datetime

import configuracion
from nucleo import bd, claves, tiempo
from servicios import ciudadanos
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


def iniciar_sesion(identificador, password):
    """Ingreso con correo o cédula. Bloquea la cuenta 15 minutos tras 5 intentos fallidos."""
    ident = str(identificador or '').strip().lower()
    if not ident or not password:
        raise ErrorApp(400, 'Escriba su usuario y contraseña.')
    # El nombre de la columna sale de una lista fija; el dato del usuario va como parámetro ?
    campo = 'c.cedula' if coincide(CEDULA_RE, ident) else 'u.correo'
    u = bd.uno(f'SELECT u.* FROM usuario u LEFT JOIN ciudadano c ON c.id_ciudadano = u.id_ciudadano WHERE {campo} = ?', (ident,))

    if u and u['bloqueado_hasta'] and u['bloqueado_hasta'] > tiempo.ahora():
        faltan = datetime.fromisoformat(u['bloqueado_hasta']) - datetime.now(configuracion.ZONA_COLOMBIA)
        minutos = max(1, math.ceil(faltan.total_seconds() / 60))
        raise ErrorApp(429, f'Cuenta bloqueada temporalmente por intentos fallidos. Intente de nuevo en {minutos} minuto(s).')

    valida = claves.verificar_password(password, u['password_hash'] if u else claves.RESUMEN_FICTICIO)
    if not u or not valida or not u['activo']:
        if u and not valida:
            intentos = u['intentos_fallidos'] + 1
            if intentos >= MAX_INTENTOS:
                bd.ejecutar('UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = ? WHERE id_usuario = ?',
                            (tiempo.dentro_de(minutos=MINUTOS_BLOQUEO), u['id_usuario']))
                raise ErrorApp(429, f'Superó {MAX_INTENTOS} intentos fallidos. Su cuenta quedó bloqueada {MINUTOS_BLOQUEO} minutos.')
            bd.ejecutar('UPDATE usuario SET intentos_fallidos = ? WHERE id_usuario = ?', (intentos, u['id_usuario']))
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
