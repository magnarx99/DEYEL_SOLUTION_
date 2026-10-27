"""Configuración del portal.

Lee el archivo .env de la carpeta del proyecto (líneas NOMBRE=valor). Si el archivo no existe,
lo crea automáticamente la primera vez con una clave secreta aleatoria, para que el
proyecto funcione sin configurar nada. Solo usa la biblioteca estándar de Python.
"""
import os
import secrets
from datetime import timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent            # carpeta del proyecto
ARCHIVO_ENV = RAIZ / '.env'

PLANTILLA_ENV = """# Configuración del Portal PQRDS (se creó automáticamente; puede editarla)
# Puerto donde se abre el portal: http://localhost:8000
PORT=8000
# desarrollo o produccion
MODO=desarrollo
# Clave secreta para firmar las sesiones. No la comparta.
JWT_SECRET={secreto}
# Horas que dura la sesión
SESION_HORAS=8
# Administrador inicial (lo crea: python scripts/crear_datos.py)
ADMIN_CORREO=admin@antioquia.example
ADMIN_PASSWORD=Admin2026*
ADMIN_NOMBRE=Administrador del Sistema
# Asistente con modelo de lenguaje (OPCIONAL). Vacío = solo reglas y preguntas frecuentes.
LLM_API_KEY=
LLM_MODEL=claude-haiku-5-5
"""


def _leer_env():
    """Lee el .env sin librerías: cada línea NOMBRE=valor; ignora vacías y comentarios (#)."""
    if not ARCHIVO_ENV.exists():
        ARCHIVO_ENV.write_text(PLANTILLA_ENV.format(secreto=secrets.token_hex(48)), encoding='utf-8')
        print('Se creó el archivo .env con una configuración inicial.')
    valores = {}
    for linea in ARCHIVO_ENV.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        nombre, valor = linea.split('=', 1)
        valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    return valores


_ENV = _leer_env()


def valor(nombre, defecto=''):
    """Primero busca en las variables del sistema y luego en el .env."""
    return os.environ.get(nombre, _ENV.get(nombre, defecto))


PUERTO = int(valor('PORT', '8000'))
PRODUCCION = valor('MODO', 'desarrollo') == 'produccion'
JWT_SECRETO = valor('JWT_SECRET')
SESION_HORAS = int(valor('SESION_HORAS', '8'))

ADMIN_CORREO = valor('ADMIN_CORREO', 'admin@antioquia.example')
ADMIN_PASSWORD = valor('ADMIN_PASSWORD', 'Admin2026*')
ADMIN_NOMBRE = valor('ADMIN_NOMBRE', 'Administrador del Sistema')

LLM_API_KEY = valor('LLM_API_KEY')
LLM_MODELO = valor('LLM_MODEL', 'claude-haiku-5-5')

CARPETA_PUBLICA = RAIZ / 'public'       # páginas HTML, estilos, JavaScript e imágenes
CARPETA_UPLOADS = RAIZ / 'uploads'      # adjuntos de las PQRDS
CARPETA_BD = RAIZ / 'database'          # schema.sql, datos_iniciales.sql y el archivo de la base
RUTA_BD = CARPETA_BD / 'pqrds.db'       # base de datos SQLite (un solo archivo)

# Colombia no cambia de horario en el año: siempre UTC-5
ZONA_COLOMBIA = timezone(timedelta(hours=-5), 'COT')

if len(JWT_SECRETO) < 32:
    raise SystemExit('ERROR: JWT_SECRET del archivo .env debe tener mínimo 32 caracteres. '
                     'Borre el archivo .env y vuelva a iniciar para que se cree uno nuevo.')
