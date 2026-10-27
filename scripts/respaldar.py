"""Copia de seguridad de la base de datos.

Uso (desde la carpeta del proyecto):   python scripts/respaldar.py
Crea una copia en database/respaldos/ con la fecha y la hora en el nombre.
Se puede ejecutar con el portal encendido: sqlite3 copia la base de forma segura.

Para RESTAURAR una copia: apague el portal (Ctrl + C), copie el archivo de
database/respaldos/ que quiera recuperar, péguelo en database/ y cámbiele el
nombre a pqrds.db (reemplazando el actual). Luego encienda el portal.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import configuracion  # noqa: E402

CARPETA_RESPALDOS = configuracion.CARPETA_BD / 'respaldos'


def respaldar(motivo=''):
    """Copia database/pqrds.db a database/respaldos/ y devuelve la ruta de la copia (o None si no hay base)."""
    if not configuracion.RUTA_BD.exists():
        return None
    CARPETA_RESPALDOS.mkdir(exist_ok=True)
    marca = datetime.now(configuracion.ZONA_COLOMBIA).strftime('%Y-%m-%d_%H-%M-%S')
    base = f"pqrds_{marca}{'_' + motivo if motivo else ''}"
    destino, n = CARPETA_RESPALDOS / f'{base}.db', 2
    while destino.exists():                     # nunca sobrescribe una copia anterior
        destino, n = CARPETA_RESPALDOS / f'{base}_{n}.db', n + 1
    origen = sqlite3.connect(configuracion.RUTA_BD)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)          # copia segura aunque el portal esté usando la base
    copia.close()
    origen.close()
    return destino


def contar_registros():
    """Cuántos ciudadanos, PQRDS y usuarios hay en la base actual."""
    if not configuracion.RUTA_BD.exists():
        return None
    try:
        conexion = sqlite3.connect(configuracion.RUTA_BD)
        totales = {tabla: conexion.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]
                   for tabla in ('ciudadano', 'pqrds', 'usuario')}
        conexion.close()
        return totales
    except sqlite3.Error:
        return None


if __name__ == '__main__':
    ruta = respaldar()
    if not ruta:
        print('Aún no existe la base de datos (database/pqrds.db). No hay nada que respaldar.')
        sys.exit(1)
    t = contar_registros() or {}
    print(f'Copia de seguridad creada: {ruta.relative_to(configuracion.RAIZ)}')
    print(f"Contiene {t.get('ciudadano', 0)} ciudadanos, {t.get('pqrds', 0)} PQRDS y {t.get('usuario', 0)} usuarios.")
