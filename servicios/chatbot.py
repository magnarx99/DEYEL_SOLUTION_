"""Asistente virtual "Ana".

Nivel base (siempre activo): reglas y preguntas frecuentes guardadas en la tabla faq_chatbot.
Nivel opcional: si existe LLM_API_KEY en el .env, las preguntas que las reglas no resuelven se
envían a un modelo de lenguaje (con urllib, de la biblioteca estándar) con instrucciones
restringidas a temas de PQRDS.
"""
import json
import re
import time
import unicodedata
import urllib.request

import configuracion
from nucleo import bd, web
from utilidades.validaciones import RADICADO_RE

SUGERENCIAS = ['¿Qué tipo de solicitud elijo?', '¿Cómo consulto mi radicado?', 'Olvidé mi contraseña']
ETIQUETA_ESTADO = {'RADICADA': 'Radicada (recibida, pendiente de asignación)', 'EN_TRAMITE': 'En trámite',
                   'RESPONDIDA': 'Respondida', 'CERRADA': 'Cerrada', 'TRASLADADA': 'Trasladada a otra dependencia'}
_cache = {'faq': None, 'hora': 0}


def normalizar(texto=''):
    """Minúsculas, sin tildes ni signos, con espacios sencillos."""
    sin_tildes = ''.join(ch for ch in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9ñ\s-]', ' ', sin_tildes)).strip()


def _faq():
    if _cache['faq'] is not None and time.time() - _cache['hora'] < 60:
        return _cache['faq']
    filas = bd.consultar('SELECT * FROM faq_chatbot WHERE activo = 1 ORDER BY id_faq')
    for f in filas:
        f['claves'] = [normalizar(k) for k in f['palabras_clave'].split(',') if normalizar(k)]
    _cache['faq'], _cache['hora'] = filas, time.time()
    return filas


def invalidar_cache():
    _cache['faq'] = None


def _mejor_coincidencia(mensaje, faqs):
    """Da puntos a cada pregunta frecuente según las palabras clave que aparecen en el mensaje."""
    m = f' {normalizar(mensaje)} '
    mejor, puntaje = None, 0
    for f in faqs:
        p = sum(len(k.split()) for k in f['claves'] if f' {k} ' in m or (len(k) > 5 and k in m))
        if f['pregunta'] == 'Saludo':
            p *= 0.5          # el saludo solo gana si no hay algo más específico
        if p > puntaje:
            mejor, puntaje = f, p
    return mejor


def _consultar_radicado(radicado, usuario):
    if not usuario:
        return {'respuesta': f'Para proteger su información, consulte el radicado {radicado} en la página "Consultar radicado" '
                             'con su número de cédula, o inicie sesión.',
                'accion': {'texto': 'Consultar radicado', 'url': f'/seguimiento.html?radicado={radicado}'}}
    p = bd.uno("""SELECT p.estado, p.fecha_limite, p.id_ciudadano, t.nombre AS tipo FROM pqrds p
                    JOIN tipo_solicitud t ON t.id_tipo = p.id_tipo WHERE p.radicado = ?""", (radicado,))
    if not p or (not web.es_personal(usuario) and p['id_ciudadano'] != usuario['id_ciudadano']):
        return {'respuesta': f'No encontré el radicado {radicado} entre sus solicitudes. Verifique el número.'}
    return {'respuesta': f"Su {p['tipo'].lower()} {radicado} está: {ETIQUETA_ESTADO[p['estado']]}. "
                         f"Fecha límite de respuesta: {p['fecha_limite']}.",
            'accion': {'texto': 'Ver mis solicitudes', 'url': '/mis-solicitudes.html'}}


def _anonimizar(texto):
    """Quita números largos y correos antes de enviar texto a un servicio externo."""
    return re.sub(r'[^\s@]+@[^\s@]+', '[correo omitido]', re.sub(r'\b\d{6,}\b', '[número omitido]', texto))


def _consultar_modelo(mensaje, faqs):
    conocimiento = '\n'.join(f"- {f['pregunta']}: {f['respuesta']}" for f in faqs if f['pregunta'] != 'Saludo')
    sistema = ('Eres el asistente virtual del portal de PQRDS de la Gobernación de Antioquia (Colombia). '
               'Responde SOLO sobre peticiones, quejas, reclamos, sugerencias, felicitaciones, denuncias, solicitudes de '
               'información, datos personales, citas y el uso de este portal. Si preguntan otra cosa, indica amablemente que '
               'solo puedes ayudar con PQRDS. Responde en español, con trato de "usted", en máximo 4 frases claras. Nunca pidas '
               'ni repitas datos personales. No inventes plazos ni normas: usa esta información oficial del portal:\n' + conocimiento)
    cuerpo = json.dumps({'model': configuracion.LLM_MODELO, 'max_tokens': 400, 'system': sistema,
                         'messages': [{'role': 'user', 'content': _anonimizar(mensaje)}]}).encode('utf-8')
    solicitud = urllib.request.Request('https://api.anthropic.com/v1/messages', data=cuerpo, method='POST', headers={
        'content-type': 'application/json', 'x-api-key': configuracion.LLM_API_KEY, 'anthropic-version': '2023-06-01'})
    with urllib.request.urlopen(solicitud, timeout=12) as r:
        datos = json.loads(r.read().decode('utf-8'))
    return ''.join(c.get('text', '') for c in datos.get('content', [])).strip()


def responder(mensaje_original, usuario):
    mensaje = str(mensaje_original or '')[:500].strip()
    if not mensaje:
        return {'respuesta': 'Escriba su pregunta, por favor.', 'sugerencias': SUGERENCIAS}

    # 1. Número de radicado
    encontrado = re.search(r'PQRDS-\d{4}-\d{6}', mensaje.upper())
    if encontrado and RADICADO_RE.match(encontrado.group()):
        return _consultar_radicado(encontrado.group(), usuario)

    # 2. Protección de datos: no se deben escribir documentos ni teléfonos en el chat
    if re.search(r'\b\d{6,10}\b', mensaje):
        return {'respuesta': 'Por su seguridad, no escriba su número de documento ni teléfonos en el chat. Si necesita '
                             'consultar una solicitud, use la opción "Consultar radicado".',
                'accion': {'texto': 'Consultar radicado', 'url': '/seguimiento.html'}}

    # 3. Preguntas frecuentes por palabras clave
    faqs = _faq()
    f = _mejor_coincidencia(mensaje, faqs)
    if f:
        return {'respuesta': f['respuesta'],
                'accion': {'texto': f['accion_texto'], 'url': f['accion_url']} if f['accion_url'] else None,
                'sugerencias': SUGERENCIAS if f['pregunta'] == 'Saludo' else None}

    # 4. Modelo de lenguaje (opcional)
    if configuracion.LLM_API_KEY:
        try:
            texto = _consultar_modelo(mensaje, faqs)
            if texto:
                return {'respuesta': texto, 'origen': 'modelo'}
        except Exception as err:
            print('Asistente: no se pudo consultar el modelo de lenguaje:', err)

    # 5. Respuesta por defecto
    return {'respuesta': 'No estoy seguro de haber entendido. Puedo ayudarle a elegir el tipo de solicitud, radicarla '
                         'o consultar su estado. Pruebe con una de estas opciones:', 'sugerencias': SUGERENCIAS}
