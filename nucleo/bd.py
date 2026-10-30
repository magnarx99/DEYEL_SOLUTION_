"""Acceso a la base de datos SQLite (módulo sqlite3 de la biblioteca estándar).

- Cada hilo (cada petición) usa su propia conexión.
- Todas las consultas usan parámetros '?': los datos del usuario nunca se pegan dentro
  del texto SQL, así se evita la inyección SQL.
- Las columnas de verdadero/falso se devuelven como True/False.
"""
import sqlite3
import threading
from contextlib import contextmanager

import configuracion

COLUMNAS_LOGICAS = {'activo', 'es_anonima', 'permite_anonimo', 'tiene_cuenta', 'debe_cambiar_password',
                    'acepta_tratamiento_datos', 'bloqueado'}
_local = threading.local()


def _fila_a_diccionario(cursor, fila):
    datos = {}
    for i, columna in enumerate(cursor.description):
        nombre = columna[0]
        v = fila[i]
        datos[nombre] = bool(v) if nombre in COLUMNAS_LOGICAS and v is not None else v
    return datos


def conexion():
    """Devuelve la conexión del hilo actual (la crea si no existe)."""
    con = getattr(_local, 'con', None)
    if con is None:
        con = sqlite3.connect(configuracion.RUTA_BD, timeout=15, isolation_level=None)
        con.row_factory = _fila_a_diccionario
        con.execute('PRAGMA foreign_keys = ON')
        con.execute('PRAGMA busy_timeout = 15000')
        _local.con = con
        _local.profundidad = 0
    return con


def cerrar():
    """Cierra la conexión del hilo (se llama al terminar cada petición)."""
    con = getattr(_local, 'con', None)
    if con is not None:
        con.close()
        _local.con = None


def consultar(sql, parametros=()):
    """Devuelve una lista de filas; cada fila es un diccionario {columna: valor}."""
    return conexion().execute(sql, parametros).fetchall()


def uno(sql, parametros=()):
    """Devuelve la primera fila o None."""
    filas = conexion().execute(sql, parametros).fetchall()   # se leen todas para cerrar la instrucción
    return filas[0] if filas else None


def ejecutar(sql, parametros=()):
    """Ejecuta INSERT, UPDATE o DELETE. Devuelve cuántas filas cambió."""
    return conexion().execute(sql, parametros).rowcount


def insertar(sql, parametros=()):
    """Ejecuta un INSERT y devuelve el id de la fila creada."""
    return conexion().execute(sql, parametros).lastrowid


@contextmanager
def transaccion():
    """Agrupa operaciones: se guardan todas o ninguna. Admite llamadas anidadas."""
    con = conexion()
    if _local.profundidad > 0:          # ya hay una transacción abierta: se usa la misma
        _local.profundidad += 1
        try:
            yield con
        finally:
            _local.profundidad -= 1
        return
    con.execute('BEGIN IMMEDIATE')
    _local.profundidad = 1
    try:
        yield con
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise
    finally:
        _local.profundidad = 0


def ejecutar_script(texto_sql):
    """Ejecuta un archivo .sql completo (varias instrucciones)."""
    conexion().executescript(texto_sql)


def migrar():
    """Aplica database/migraciones.sql: agrega a una base existente lo nuevo sin borrar datos."""
    ejecutar_script((configuracion.CARPETA_BD / 'migraciones.sql').read_text(encoding='utf-8'))


def existe_base():
    return configuracion.RUTA_BD.exists() and configuracion.RUTA_BD.stat().st_size > 0
