"""Archivos adjuntos: PDF, JPG o PNG, máximo 5 MB cada uno y 5 por solicitud.

Además del nombre, se revisa la "firma" del archivo (sus primeros bytes) para comprobar que el
contenido real corresponde al tipo. En el disco se guardan con un nombre aleatorio: el nombre
que envía el usuario nunca se usa como ruta.
"""
import uuid
from pathlib import Path

import configuracion
from utilidades.errores import ErrorApp

PERMITIDOS = {
    '.pdf': ('application/pdf', b'%PDF'),
    '.png': ('image/png', b'\x89PNG'),
    '.jpg': ('image/jpeg', b'\xff\xd8\xff'),
    '.jpeg': ('image/jpeg', b'\xff\xd8\xff'),
}
MAX_BYTES = 5 * 1024 * 1024
MAX_ARCHIVOS = 5


def guardar(archivos):
    """Valida todos los archivos y, si están bien, los guarda. Devuelve los datos para la base."""
    archivos = [a for a in archivos if a['campo'] == 'adjuntos' and a['nombre']]
    if len(archivos) > MAX_ARCHIVOS:
        raise ErrorApp(400, 'Puede adjuntar máximo 5 archivos.')
    for a in archivos:
        extension = Path(a['nombre']).suffix.lower()
        if extension not in PERMITIDOS:
            raise ErrorApp(400, f"El archivo \"{a['nombre']}\" no es PDF, JPG o PNG.")
        if len(a['datos']) > MAX_BYTES:
            raise ErrorApp(400, 'Cada archivo debe pesar máximo 5 MB.')
        if not a['datos'].startswith(PERMITIDOS[extension][1]):
            raise ErrorApp(400, f"El contenido de \"{a['nombre']}\" no corresponde a un PDF, JPG o PNG válido.")
    configuracion.CARPETA_UPLOADS.mkdir(parents=True, exist_ok=True)
    guardados = []
    for a in archivos:
        extension = Path(a['nombre']).suffix.lower()
        nombre_disco = f'{uuid.uuid4()}{extension}'
        (configuracion.CARPETA_UPLOADS / nombre_disco).write_bytes(a['datos'])
        guardados.append({'nombre_original': Path(a['nombre']).name, 'ruta': nombre_disco,
                          'tipo_mime': PERMITIDOS[extension][0], 'tamano': len(a['datos'])})
    return guardados


def eliminar(guardados):
    """Borra archivos ya guardados (si la radicación falló, no deben quedar huérfanos)."""
    for a in guardados:
        (configuracion.CARPETA_UPLOADS / a['ruta']).unlink(missing_ok=True)


def ruta_segura(nombre_disco):
    """Ruta de un adjunto, sin permitir salir de la carpeta uploads."""
    return configuracion.CARPETA_UPLOADS / Path(nombre_disco).name
