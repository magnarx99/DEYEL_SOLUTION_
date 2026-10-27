"""Catálogos para las listas desplegables y las preguntas frecuentes del asistente."""
import re

from nucleo import bd
from servicios import chatbot
from utilidades.errores import ErrorApp
from utilidades.validaciones import texto

_cache = {}


def catalogos():
    """Tipos de solicitud, dependencias y municipios (cambian muy poco: se guardan en memoria)."""
    if not _cache:
        _cache['tipos'] = bd.consultar("""SELECT codigo, nombre, descripcion, ejemplo, texto_boton, icono, dias_habiles_respuesta,
                                                 permite_anonimo FROM tipo_solicitud ORDER BY orden""")
        _cache['dependencias'] = bd.consultar('SELECT id_dependencia, nombre FROM dependencia ORDER BY nombre')
        _cache['municipios'] = [m['nombre'] for m in bd.consultar('SELECT nombre FROM municipio ORDER BY nombre')]
    return _cache


def _validar_faq(e):
    claves = [chatbot.normalizar(k) for k in texto(e.get('palabras_clave')).split(',')]
    d = {'palabras_clave': ','.join(k for k in claves if k), 'pregunta': texto(e.get('pregunta')),
         'respuesta': texto(e.get('respuesta')), 'accion_texto': texto(e.get('accion_texto')) or None,
         'accion_url': texto(e.get('accion_url')) or None, 'activo': e.get('activo') is not False}
    err = {}
    if not d['palabras_clave']:
        err['palabras_clave'] = 'Escriba al menos una palabra clave.'
    if not 3 <= len(d['pregunta']) <= 200:
        err['pregunta'] = 'Entre 3 y 200 caracteres.'
    if len(d['respuesta']) < 10:
        err['respuesta'] = 'Escriba una respuesta de al menos 10 caracteres.'
    # Solo enlaces internos del portal: el asistente nunca envía a sitios externos
    if d['accion_url'] and not re.fullmatch(r'/[a-zA-Z0-9\-_/.?=&]*', d['accion_url']):
        err['accion_url'] = 'Use una ruta interna, por ejemplo /pqrds.html'
    if d['accion_url'] and not d['accion_texto']:
        err['accion_texto'] = 'Escriba el texto del botón.'
    if err:
        raise ErrorApp(400, 'Revise los campos marcados.', err)
    return d


def listar_faq():
    return bd.consultar('SELECT * FROM faq_chatbot ORDER BY id_faq')


def guardar_faq(id_faq, entrada):
    d = _validar_faq(entrada)
    valores = (d['palabras_clave'], d['pregunta'], d['respuesta'], d['accion_texto'], d['accion_url'], d['activo'])
    if id_faq:
        if not bd.ejecutar("""UPDATE faq_chatbot SET palabras_clave=?, pregunta=?, respuesta=?, accion_texto=?, accion_url=?, activo=?
                               WHERE id_faq=?""", valores + (id_faq,)):
            raise ErrorApp(404, 'Pregunta no encontrada.')
    else:
        id_faq = bd.insertar("""INSERT INTO faq_chatbot (palabras_clave, pregunta, respuesta, accion_texto, accion_url, activo)
                                VALUES (?,?,?,?,?,?)""", valores)
    chatbot.invalidar_cache()
    return bd.uno('SELECT * FROM faq_chatbot WHERE id_faq = ?', (id_faq,))


def eliminar_faq(id_faq):
    if not bd.ejecutar('DELETE FROM faq_chatbot WHERE id_faq = ?', (id_faq,)):
        raise ErrorApp(404, 'Pregunta no encontrada.')
    chatbot.invalidar_cache()
