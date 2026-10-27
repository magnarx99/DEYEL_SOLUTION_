"""Mini sistema web hecho solo con la biblioteca estándar de Python.

Contiene:
- Peticion: lo que envía el navegador (método, ruta, datos, cookies, archivos).
- Respuesta: lo que el servidor devuelve (JSON, archivo, redirección).
- Enrutador: relaciona cada dirección de la API con la función que la atiende.
- Decoradores de permisos (permitir, requerir_sesion) y límite de intentos.
- contexto: la petición actual, disponible para los servicios sin pasarla como parámetro.
"""
import json
import re
import threading
import time
from collections import defaultdict, deque
from email import policy
from email.parser import BytesParser
from functools import wraps
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qsl, quote

from utilidades.errores import ErrorApp

TIPOS_CONTENIDO = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8', '.pdf': 'application/pdf',
    '.woff2': 'font/woff2', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


# ------------------------------------------------------------------ petición actual (por hilo)
class _Contexto(threading.local):
    peticion = None


contexto = _Contexto()


def usuario_actual():
    return contexto.peticion.usuario if contexto.peticion else None


def ip_actual():
    return contexto.peticion.ip if contexto.peticion else None


def es_personal(usuario):
    return bool(usuario) and usuario['rol'] in ('FUNCIONARIO', 'ADMIN')


# ------------------------------------------------------------------ petición
class Peticion:
    def __init__(self, metodo, ruta, consulta, cabeceras, cuerpo, ip):
        self.metodo = metodo
        self.ruta = ruta
        self.consulta = dict(parse_qsl(consulta, keep_blank_values=False))  # ?a=1&b=2 -> {'a': '1', 'b': '2'}
        self.cabeceras = cabeceras
        self.cuerpo = cuerpo
        self.ip = ip
        self.parametros = {}      # valores de la ruta, p. ej. <cedula>
        self.usuario = None       # se llena al leer la sesión
        self.archivos_guardados = []
        galletas = SimpleCookie()
        try:
            galletas.load(cabeceras.get('Cookie', ''))
        except Exception:  # cookie mal formada: se ignora
            pass
        self.cookies = {k: v.value for k, v in galletas.items()}

    def json(self):
        """Lee el cuerpo como JSON. Devuelve {} si viene vacío."""
        if not self.cuerpo:
            return {}
        try:
            datos = json.loads(self.cuerpo.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise ErrorApp(400, 'La información enviada no tiene un formato válido.') from err
        return datos if isinstance(datos, dict) else {}

    def formulario(self):
        """Lee un formulario multipart (con archivos). Devuelve (campos, archivos)."""
        tipo = self.cabeceras.get('Content-Type', '')
        if not tipo.startswith('multipart/form-data'):
            return self.json(), []
        mensaje = BytesParser(policy=policy.HTTP).parsebytes(
            b'Content-Type: ' + tipo.encode('latin-1') + b'\r\n\r\n' + self.cuerpo)
        campos, archivos = {}, []
        for parte in mensaje.iter_parts():
            nombre = parte.get_param('name', header='content-disposition')
            if not nombre:
                continue
            datos = parte.get_payload(decode=True) or b''
            nombre_archivo = parte.get_filename()
            if nombre_archivo is not None:
                archivos.append({'campo': nombre, 'nombre': nombre_archivo, 'tipo': parte.get_content_type(), 'datos': datos})
            else:
                campos[nombre] = datos.decode('utf-8', errors='replace')
        return campos, archivos


# ------------------------------------------------------------------ respuesta
class Respuesta:
    def __init__(self, status=200, cuerpo=b'', tipo='application/json; charset=utf-8', cabeceras=None):
        self.status = status
        self.cuerpo = cuerpo
        self.cabeceras = {'Content-Type': tipo, **(cabeceras or {})}
        self.cookies = []

    @staticmethod
    def json(datos, status=200):
        texto = json.dumps(datos, ensure_ascii=False, default=str)
        return Respuesta(status, texto.encode('utf-8'))

    @staticmethod
    def archivo(ruta, nombre_descarga=None, status=200):
        ruta = Path(ruta)
        cabeceras = {'Cache-Control': 'no-cache'}
        if nombre_descarga:
            cabeceras['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(nombre_descarga)}"
        tipo = TIPOS_CONTENIDO.get(ruta.suffix.lower(), 'application/octet-stream')
        return Respuesta(status, ruta.read_bytes(), tipo, cabeceras)

    @staticmethod
    def descarga(datos, nombre, tipo):
        return Respuesta(200, datos, tipo, {'Content-Disposition': f"attachment; filename*=UTF-8''{quote(nombre)}"})

    @staticmethod
    def redirigir(url):
        return Respuesta(302, b'', 'text/plain; charset=utf-8', {'Location': url})

    def poner_cookie(self, nombre, valor, segundos, segura=False):
        partes = [f'{nombre}={valor}', 'Path=/', f'Max-Age={segundos}', 'HttpOnly', 'SameSite=Lax']
        if segura:
            partes.append('Secure')
        self.cookies.append('; '.join(partes))

    def borrar_cookie(self, nombre):
        self.cookies.append(f'{nombre}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')


# ------------------------------------------------------------------ enrutador
class Enrutador:
    """Relaciona 'MÉTODO /ruta/<parametro>' con una función."""

    def __init__(self):
        self.rutas = []

    def agregar(self, metodo, patron, funcion):
        regex = '^' + re.sub(r'<(\w+)>', r'(?P<\1>[^/]+)', patron) + '$'
        self.rutas.append((metodo, re.compile(regex), funcion))

    def ruta(self, metodo, patron):
        def decorador(funcion):
            self.agregar(metodo, patron, funcion)
            return funcion
        return decorador

    def buscar(self, metodo, ruta):
        for m, regex, funcion in self.rutas:
            coincidencia = regex.match(ruta)
            if coincidencia and m == metodo:
                return funcion, coincidencia.groupdict()
        return None, None


# ------------------------------------------------------------------ permisos
def requerir_sesion(funcion):
    @wraps(funcion)
    def envoltura(peticion):
        if not peticion.usuario:
            raise ErrorApp(401, 'Debe iniciar sesión para continuar.')
        return funcion(peticion)
    return envoltura


def permitir(*roles):
    """Permite el acceso solo a los roles indicados."""
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(peticion):
            if not peticion.usuario:
                raise ErrorApp(401, 'Debe iniciar sesión para continuar.')
            if peticion.usuario['rol'] not in roles:
                raise ErrorApp(403, 'No tiene permisos para realizar esta acción.')
            return funcion(peticion)
        return envoltura
    return decorador


# ------------------------------------------------------------------ límite de intentos
_registros = defaultdict(deque)
_candado = threading.Lock()


def limite(maximo, minutos, mensaje, grupo=None):
    """Frena los ataques de fuerza bruta: máximo N peticiones por IP en M minutos."""
    ventana = minutos * 60

    def decorador(funcion):
        nombre_grupo = grupo or funcion.__name__

        @wraps(funcion)
        def envoltura(peticion):
            clave = (nombre_grupo, peticion.ip)
            ahora = time.monotonic()
            with _candado:
                cola = _registros[clave]
                while cola and ahora - cola[0] > ventana:
                    cola.popleft()
                if len(cola) >= maximo:
                    raise ErrorApp(429, mensaje)
                cola.append(ahora)
            return funcion(peticion)
        return envoltura
    return decorador
