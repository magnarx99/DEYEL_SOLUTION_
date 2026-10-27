"""Número de radicado PQRDS-AAAA-000001 y código para denuncias anónimas.

El consecutivo se guarda por año en la tabla consecutivo_radicado y se incrementa dentro de
una transacción (BEGIN IMMEDIATE bloquea la escritura): dos radicaciones simultáneas nunca
obtienen el mismo número.
"""
import secrets

from nucleo import bd, tiempo

ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # sin letras ni números que se confunden


def generar_radicado():
    anio = int(tiempo.hoy()[:4])
    fila = bd.uno("""INSERT INTO consecutivo_radicado (anio, ultimo) VALUES (?, 1)
                     ON CONFLICT (anio) DO UPDATE SET ultimo = ultimo + 1
                     RETURNING ultimo""", (anio,))
    return f"PQRDS-{anio}-{fila['ultimo']:06d}"


def generar_codigo_anonimo():
    return ''.join(secrets.choice(ALFABETO) for _ in range(8))
