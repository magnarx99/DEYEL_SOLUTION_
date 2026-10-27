"""Servidor del Portal PQRDS – Gobernación de Antioquia.

Hecho solo con la biblioteca estándar de Python (http.server + sqlite3).
Para iniciarlo:   python servidor.py
Luego abra en el navegador:   http://localhost:8000
"""
import sqlite3
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import configuracion
from nucleo import adjuntos, bd, sesion
from nucleo.web import Peticion, Respuesta, contexto, es_personal
from rutas import api
from utilidades.errores import ErrorApp

PUBLICA = configuracion.CARPETA_PUBLICA.resolve()
MAX_CUERPO = 26 * 1024 * 1024                     # 5 adjuntos de 5 MB + datos del formulario
PAGINAS_SOLO_ADMIN = {'dashboard.html', 'usuarios.html', 'faq.html', 'auditoria.html'}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


# ---------------------------------------------------------------------------- archivos públicos
def archivo_publico(ruta, status=200):
    """Devuelve un archivo de la carpeta public sin permitir salir de ella (p. ej. con ../)."""
    relativa = unquote(ruta).lstrip('/') or 'index.html'
    destino = (PUBLICA / relativa).resolve()
    if PUBLICA not in destino.parents and destino != PUBLICA:
        return None
    if destino.is_dir():
        destino = destino / 'index.html'
    if not destino.exists() and destino.with_suffix('.html').exists():
        destino = destino.with_suffix('.html')     # /pqrds también abre pqrds.html
    if not destino.is_file():
        return None
    return Respuesta.archivo(destino, status=status)


def pagina_error(codigo):
    return Respuesta.archivo(PUBLICA / f'{codigo}.html', status=codigo)


def proteger_panel(peticion):
    """Páginas de /admin: sin sesión -> al login; ciudadano -> 403; páginas de admin -> solo ADMIN."""
    if not peticion.usuario:
        return Respuesta.redirigir('/login.html?volver=' + quote(peticion.ruta))
    pagina = Path(peticion.ruta).name
    if not es_personal(peticion.usuario) or (pagina in PAGINAS_SOLO_ADMIN and peticion.usuario['rol'] != 'ADMIN'):
        return pagina_error(403)
    if peticion.ruta.rstrip('/') == '/admin':
        return Respuesta.redirigir('/admin/dashboard.html' if peticion.usuario['rol'] == 'ADMIN' else '/admin/bandeja.html')
    return None


# ---------------------------------------------------------------------------- errores
def respuesta_de_error(err):
    if isinstance(err, ErrorApp):
        return Respuesta.json({'error': err.mensaje, 'detalles': err.detalles}, err.status)
    if isinstance(err, sqlite3.IntegrityError):
        texto = str(err)
        if 'UNIQUE' in texto:
            return Respuesta.json({'error': 'El registro ya existe.'}, 409)
        if 'FOREIGN KEY' in texto:
            return Respuesta.json({'error': 'Uno de los valores seleccionados no existe.'}, 400)
        return Respuesta.json({'error': 'Algunos datos no cumplen el formato requerido.'}, 400)
    traceback.print_exc()
    return Respuesta.json({'error': 'Ocurrió un error interno. Intente de nuevo en unos minutos.'}, 500)


# ---------------------------------------------------------------------------- manejador de peticiones
class Manejador(BaseHTTPRequestHandler):
    server_version = 'PortalPQRDS/1.0'
    sys_version = ''

    def do_GET(self): self.atender('GET')        # noqa: E704
    def do_POST(self): self.atender('POST')      # noqa: E704
    def do_PUT(self): self.atender('PUT')        # noqa: E704
    def do_PATCH(self): self.atender('PATCH')    # noqa: E704
    def do_DELETE(self): self.atender('DELETE')  # noqa: E704

    def atender(self, metodo):
        partes = urlsplit(self.path)
        ruta = partes.path
        peticion = None
        try:
            largo = int(self.headers.get('Content-Length') or 0)
            if largo > MAX_CUERPO:
                self.rfile.read(min(largo, MAX_CUERPO))
                raise ErrorApp(400, 'Cada archivo debe pesar máximo 5 MB.')
            cuerpo = self.rfile.read(largo) if largo else b''
            peticion = Peticion(metodo, ruta, partes.query, self.headers, cuerpo, self.client_address[0])
            contexto.peticion = peticion
            sesion.leer(peticion)
            respuesta = self.despachar(peticion)
        except Exception as err:  # noqa: BLE001  (todo error se convierte en una respuesta clara)
            if peticion is not None and peticion.archivos_guardados:
                adjuntos.eliminar(peticion.archivos_guardados)
            respuesta = respuesta_de_error(err)
        finally:
            contexto.peticion = None
            bd.cerrar()
        self.enviar(respuesta)

    def despachar(self, peticion):
        ruta = peticion.ruta
        if ruta.startswith('/api/'):
            funcion, parametros = api.buscar(peticion.metodo, ruta)
            if not funcion:
                return Respuesta.json({'error': 'El recurso solicitado no existe.'}, 404)
            peticion.parametros = parametros
            resultado = funcion(peticion)
            return resultado if isinstance(resultado, Respuesta) else Respuesta.json(resultado)
        if peticion.metodo != 'GET':
            return Respuesta.json({'error': 'El recurso solicitado no existe.'}, 404)
        if ruta == '/admin' or ruta.startswith('/admin/'):
            bloqueo = proteger_panel(peticion)
            if bloqueo:
                return bloqueo
        return archivo_publico(ruta) or pagina_error(404)

    def enviar(self, respuesta):
        self.send_response(respuesta.status)
        for nombre, valor in respuesta.cabeceras.items():
            self.send_header(nombre, valor)
        for galleta in respuesta.cookies:
            self.send_header('Set-Cookie', galleta)
        # Cabeceras de seguridad
        self.send_header('Content-Security-Policy', CSP + ('; upgrade-insecure-requests' if configuracion.PRODUCCION else ''))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        if 'Cache-Control' not in respuesta.cabeceras:
            self.send_header('Cache-Control', 'no-store' if respuesta.cabeceras['Content-Type'].startswith('application/json') else 'no-cache')
        self.send_header('Content-Length', str(len(respuesta.cuerpo)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(respuesta.cuerpo)

    def log_message(self, formato, *args):
        # Registro corto en la terminal: método, ruta y código de respuesta
        sys.stderr.write(f'{self.command} {self.path.split("?")[0]} -> {args[1] if len(args) > 1 else ""}\n')


def iniciar():
    if not bd.existe_base():
        print('Aún no existe la base de datos. Ejecute primero:  python scripts/crear_datos.py')
        sys.exit(1)
    servidor = ThreadingHTTPServer(('127.0.0.1', configuracion.PUERTO), Manejador)
    servidor.daemon_threads = True
    print(f'Portal PQRDS en http://localhost:{configuracion.PUERTO}')
    if not configuracion.LLM_API_KEY:
        print('Asistente virtual: modo reglas (sin LLM_API_KEY).')
    print('Para detener el servidor pulse Ctrl + C.')
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor detenido.')
    finally:
        servidor.server_close()


if __name__ == '__main__':
    iniciar()
