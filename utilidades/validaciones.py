"""Reglas de validación del servidor (verificación definitiva).
El navegador aplica las mismas reglas para dar respuesta inmediata, pero aquí se revisa todo de nuevo."""
import re
from datetime import date

from nucleo import tiempo

CEDULA_RE = re.compile(r'^[0-9]{6,10}$')
TELEFONO_RE = re.compile(r'^[0-9]{7,15}$')
CORREO_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')
FECHA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RADICADO_RE = re.compile(r'^PQRDS-\d{4}-\d{6}$')
# Mínimo 8 caracteres, una mayúscula, un número y un símbolo
PASSWORD_RE = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,72}$')

TIPOS_DOCUMENTO = ['CC', 'CE', 'TI', 'PA']
SEXOS = ['FEMENINO', 'MASCULINO', 'INTERSEXUAL', 'NO_INFORMA']
GRUPOS = ['', 'NINGUNO', 'PERSONA_CON_DISCAPACIDAD', 'VICTIMA_CONFLICTO', 'ADULTO_MAYOR',
          'INDIGENA', 'AFRODESCENDIENTE', 'ROM', 'MIGRANTE', 'LGBTIQ']
ESTADOS = ['RADICADA', 'EN_TRAMITE', 'RESPONDIDA', 'CERRADA', 'TRASLADADA']


def texto(valor):
    """El texto sin espacios al inicio ni al final ('' si no es texto)."""
    return valor.strip() if isinstance(valor, str) else ''


def coincide(regex, valor):
    return isinstance(valor, str) and bool(regex.match(valor))


def es_fecha_valida(valor, pasada=False):
    if not coincide(FECHA_RE, valor):
        return False
    try:
        fecha = date.fromisoformat(valor)
    except ValueError:
        return False
    return not (pasada and fecha.isoformat() > tiempo.hoy())


def validar_ciudadano(entrada=None, parcial=False):
    """Limpia y valida los datos personales. Devuelve (datos, errores)."""
    e = entrada or {}

    def sin_espacios(v):
        return re.sub(r'[\s-]', '', texto(v))

    d = {
        'tipo_documento': texto(e.get('tipo_documento')) or 'CC',
        'cedula': texto(e.get('cedula')),
        'fecha_expedicion': texto(e.get('fecha_expedicion')),
        'nombres': re.sub(r'\s+', ' ', texto(e.get('nombres'))),
        'apellidos': re.sub(r'\s+', ' ', texto(e.get('apellidos'))),
        'fecha_nacimiento': texto(e.get('fecha_nacimiento')) or None,
        'sexo': texto(e.get('sexo')) or None,
        'grupo_poblacional': texto(e.get('grupo_poblacional')) or None,
        'municipio': texto(e.get('municipio')),
        'barrio': texto(e.get('barrio')) or None,
        'direccion': texto(e.get('direccion')) or None,
        'telefono': sin_espacios(e.get('telefono')),
        'telefono_fijo': sin_espacios(e.get('telefono_fijo')) or None,
        'correo': texto(e.get('correo')).lower() or None,
        'notificacion_preferida': texto(e.get('notificacion_preferida')) or 'CORREO',
        'acepta_tratamiento_datos': e.get('acepta_tratamiento_datos') in (True, 'true'),
    }
    err = {}
    if not parcial:
        if d['tipo_documento'] not in TIPOS_DOCUMENTO:
            err['tipo_documento'] = 'Tipo de documento no válido.'
        if not coincide(CEDULA_RE, d['cedula']):
            err['cedula'] = 'El documento debe tener de 6 a 10 dígitos, sin puntos ni espacios.'
        if not es_fecha_valida(d['fecha_expedicion'], pasada=True):
            err['fecha_expedicion'] = 'Indique una fecha de expedición válida.'
        if not d['acepta_tratamiento_datos']:
            err['acepta_tratamiento_datos'] = 'Debe autorizar el tratamiento de datos personales.'
    if not 2 <= len(d['nombres']) <= 80:
        err['nombres'] = 'Escriba sus nombres.'
    if not 2 <= len(d['apellidos']) <= 80:
        err['apellidos'] = 'Escriba sus apellidos.'
    if d['fecha_nacimiento'] and not es_fecha_valida(d['fecha_nacimiento'], pasada=True):
        err['fecha_nacimiento'] = 'Fecha de nacimiento no válida.'
    if d['sexo'] and d['sexo'] not in SEXOS:
        err['sexo'] = 'Opción no válida.'
    if d['grupo_poblacional'] and d['grupo_poblacional'] not in GRUPOS:
        err['grupo_poblacional'] = 'Opción no válida.'
    if not d['municipio']:
        err['municipio'] = 'Seleccione su municipio.'
    if d['barrio'] and len(d['barrio']) > 80:
        err['barrio'] = 'Máximo 80 caracteres.'
    if d['direccion'] and len(d['direccion']) > 120:
        err['direccion'] = 'Máximo 120 caracteres.'
    if not coincide(TELEFONO_RE, d['telefono']):
        err['telefono'] = 'El celular debe tener solo números (7 a 15 dígitos).'
    if d['telefono_fijo'] and not coincide(TELEFONO_RE, d['telefono_fijo']):
        err['telefono_fijo'] = 'Teléfono fijo no válido.'
    if d['correo'] and (not coincide(CORREO_RE, d['correo']) or len(d['correo']) > 120):
        err['correo'] = 'Correo electrónico no válido.'
    if d['notificacion_preferida'] not in ('CORREO', 'SMS'):
        err['notificacion_preferida'] = 'Opción no válida.'
    return d, err
