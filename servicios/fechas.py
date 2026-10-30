"""Días hábiles: excluye sábados, domingos y festivos de Colombia (tabla festivo).
Según la Ley 1755 de 2015, el término se cuenta desde el día hábil siguiente a la radicación."""
import time
from datetime import date, timedelta

from nucleo import bd, tiempo

_cache = {'festivos': None, 'hora': 0}


def obtener_festivos():
    if _cache['festivos'] is not None and time.time() - _cache['hora'] < 3600:
        return _cache['festivos']
    _cache['festivos'] = {f['fecha'] for f in bd.consultar('SELECT fecha FROM festivo')}
    _cache['hora'] = time.time()
    return _cache['festivos']


def _es_habil(dia, festivos):
    return dia.weekday() < 5 and dia.isoformat() not in festivos   # weekday: 5 = sábado, 6 = domingo


def es_dia_habil(fecha):
    """True si 'AAAA-MM-DD' es de lunes a viernes y no es festivo."""
    return _es_habil(date.fromisoformat(fecha), obtener_festivos())


MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def legible(fecha):
    """'2026-11-09' -> '9 de noviembre de 2026'."""
    d = date.fromisoformat(fecha)
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def fecha_minima_cita(dias_respuesta):
    """Primera fecha en que se puede agendar una cita: el día hábil siguiente al plazo de respuesta.
    Así la dependencia alcanza a revisar la solicitud y confirmar la cita antes de que llegue el día."""
    return sumar_dias_habiles(tiempo.hoy(), dias_respuesta + 1)


def sumar_dias_habiles(fecha_inicio, dias):
    """Suma N días hábiles a 'AAAA-MM-DD' y devuelve la fecha límite 'AAAA-MM-DD'."""
    festivos = obtener_festivos()
    dia = date.fromisoformat(fecha_inicio)
    contados = 0
    while contados < dias:
        dia += timedelta(days=1)
        if _es_habil(dia, festivos):
            contados += 1
    return dia.isoformat()


def dias_habiles_restantes(fecha_limite):
    """Días hábiles que faltan hasta la fecha límite (negativo si ya venció)."""
    festivos = obtener_festivos()
    dia = date.fromisoformat(tiempo.hoy())
    limite = date.fromisoformat(fecha_limite)
    signo = 1 if limite >= dia else -1
    n = 0
    while dia != limite:
        dia += timedelta(days=signo)
        if _es_habil(dia, festivos):
            n += signo
    return n
