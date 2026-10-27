"""Contraseñas y fichas de sesión, solo con la biblioteca estándar.

CONTRASEÑAS: nunca se guardan tal cual. Se guarda un "resumen" calculado con PBKDF2-SHA256
(hashlib.pbkdf2_hmac) y una sal aleatoria. Formato guardado:
    pbkdf2_sha256$<iteraciones>$<sal>$<resumen>

FICHAS DE SESIÓN (tokens): se usa el formato JWT con firma HMAC-SHA256 (hmac + hashlib):
    <encabezado>.<datos>.<firma>   (cada parte en base64url)
Si alguien cambia los datos, la firma deja de coincidir y la ficha se rechaza.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

import configuracion

ITERACIONES = 240_000


# ------------------------------------------------------------------ contraseñas
def resumir_password(password):
    sal = secrets.token_bytes(16)
    resumen = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), sal, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${_b64(sal)}${_b64(resumen)}"


def verificar_password(password, guardado):
    try:
        algoritmo, iteraciones, sal, resumen = guardado.split('$')
        if algoritmo != 'pbkdf2_sha256':
            return False
        calculado = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), _desb64(sal), int(iteraciones))
        return hmac.compare_digest(calculado, _desb64(resumen))  # comparación en tiempo constante
    except (ValueError, AttributeError):
        return False


def resumen_sha256(texto):
    """Resumen simple para guardar tokens de recuperación (no para contraseñas)."""
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


# ------------------------------------------------------------------ fichas firmadas (JWT HS256)
def _b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode('ascii')


def _desb64(texto):
    return base64.urlsafe_b64decode(texto + '=' * (-len(texto) % 4))


def _firma(mensaje):
    return _b64(hmac.new(configuracion.JWT_SECRETO.encode('utf-8'), mensaje.encode('ascii'), hashlib.sha256).digest())


def crear_ficha(datos, segundos):
    """Crea una ficha firmada que vence en 'segundos'."""
    encabezado = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    contenido = _b64(json.dumps({**datos, 'exp': int(time.time()) + segundos}, separators=(',', ':')).encode())
    return f"{encabezado}.{contenido}.{_firma(encabezado + '.' + contenido)}"


def leer_ficha(ficha):
    """Devuelve los datos si la firma es válida y no ha vencido; si no, None."""
    try:
        encabezado, contenido, firma = (ficha or '').split('.')
        if not hmac.compare_digest(firma, _firma(encabezado + '.' + contenido)):
            return None
        datos = json.loads(_desb64(contenido))
        if datos.get('exp', 0) < time.time():
            return None
        return datos
    except (ValueError, json.JSONDecodeError):
        return None


# Resumen ficticio: el tiempo de respuesta no revela si un usuario existe
RESUMEN_FICTICIO = resumir_password('contrasena-ficticia')
