"""Fechas y horas en hora de Colombia (UTC-5), en el formato que usa la base de datos."""
from datetime import datetime, timedelta

import configuracion


def ahora():
    """Fecha y hora actual de Colombia: 'AAAA-MM-DDTHH:MM:SS-05:00'."""
    return datetime.now(configuracion.ZONA_COLOMBIA).isoformat(timespec='seconds')


def hoy():
    """Fecha de hoy en Colombia: 'AAAA-MM-DD'."""
    return datetime.now(configuracion.ZONA_COLOMBIA).date().isoformat()


def dentro_de(minutos=0, dias=0):
    """Fecha y hora futura (o pasada si es negativo) en el mismo formato."""
    momento = datetime.now(configuracion.ZONA_COLOMBIA) + timedelta(minutes=minutos, days=dias)
    return momento.isoformat(timespec='seconds')


def sumar_dias_calendario(fecha, dias):
    return (datetime.fromisoformat(fecha).date() + timedelta(days=dias)).isoformat()


def a_fecha_hora(texto):
    return datetime.fromisoformat(texto) if texto else None
