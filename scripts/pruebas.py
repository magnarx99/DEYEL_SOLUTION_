"""Pruebas automáticas de la API (casos de prueba del informe).

Uso: con el servidor encendido (python servidor.py) y la base recién creada
(python scripts/crear_datos.py, NO la base vacía de datos reales),
abra OTRA terminal y ejecute:
    python scripts/pruebas.py
Solo usa la biblioteca estándar (urllib).
"""
import json
import random
import sys
import urllib.error
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import configuracion  # noqa: E402

BASE = f'http://localhost:{configuracion.PUERTO}'
resultados = {'aprobadas': 0, 'fallidas': 0}


class Cliente:
    """Navegador mínimo: guarda la cookie de sesión entre peticiones."""

    def __init__(self):
        self.abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()), SinRedireccion())

    def __call__(self, ruta, metodo='GET', json_datos=None, formulario=None):
        cabeceras, cuerpo = {}, None
        if json_datos is not None:
            cuerpo = json.dumps(json_datos).encode('utf-8')
            cabeceras['Content-Type'] = 'application/json'
        elif formulario is not None:
            cuerpo, tipo = formulario
            cabeceras['Content-Type'] = tipo
        solicitud = urllib.request.Request(BASE + ruta, data=cuerpo, method=metodo, headers=cabeceras)
        try:
            with self.abridor.open(solicitud, timeout=30) as r:
                return r.status, r.headers.get('Content-Type', ''), r.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers.get('Content-Type', ''), err.read()

    def json(self, *a, **k):
        status, tipo, cuerpo = self(*a, **k)
        return status, (json.loads(cuerpo) if 'json' in tipo and cuerpo else {})


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def multipart(campos, archivos=()):
    """Arma un formulario multipart/form-data a mano (como lo envía el navegador)."""
    limite = uuid.uuid4().hex
    partes = []
    for nombre, valor in campos.items():
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode('utf-8'))
    for nombre, archivo, tipo, datos in archivos:
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"; filename="{archivo}"\r\n'
                      f'Content-Type: {tipo}\r\n\r\n'.encode('utf-8') + datos + b'\r\n')
    partes.append(f'--{limite}--\r\n'.encode('utf-8'))
    return b''.join(partes), f'multipart/form-data; boundary={limite}'


def formulario_pqrds(**extra):
    campos = {'tipo': 'PETICION', 'municipio_hecho': 'Medellín', 'asunto': 'Prueba automática de radicación',
              'descripcion': 'Descripción de prueba con más de veinte caracteres para validar.', 'medio_respuesta': 'CORREO', **extra}
    archivos = campos.pop('_archivos', ())
    return multipart(campos, archivos)


def caso(nombre, funcion):
    try:
        funcion()
        resultados['aprobadas'] += 1
        print(f'  ✔ {nombre}')
    except AssertionError as err:
        resultados['fallidas'] += 1
        print(f'  ✘ {nombre}\n      {err}')


def main():
    print(f'Pruebas contra {BASE}\n')
    visitante, ciudadano, funcionario, admin = Cliente(), Cliente(), Cliente(), Cliente()
    try:
        accesos = [(ciudadano, '1017234567', 'Ciudadano2026*'),
                   (funcionario, 'funcionario.ciudadania@antioquia.example', 'Funcionario2026*'),
                   (admin, configuracion.ADMIN_CORREO, configuracion.ADMIN_PASSWORD)]
        estados = [cliente.json('/api/auth/login', 'POST', {'usuario': u, 'password': c}) + (u,) for cliente, u, c in accesos]
    except urllib.error.URLError:
        print('No fue posible conectarse. ¿Está encendido el servidor (python servidor.py)?')
        sys.exit(1)
    for estado, datos, usuario in estados:
        if estado != 200:
            print(f"No se pudo iniciar sesión con {usuario}: {datos.get('error', estado)}")
            print('  - Si dice "Demasiados intentos": detenga el servidor (Ctrl + C) y enciéndalo de nuevo (python servidor.py).')
            print('  - Si dice "Usuario o contraseña incorrectos": reinicie los datos con  python scripts/crear_datos.py')
            sys.exit(1)
    estado_admin, datos_admin = estados[2][0], estados[2][1]

    print('Reconocimiento por cédula')

    def cp01():
        s, d = funcionario.json('/api/ciudadanos/1017234567')
        assert s == 200 and d['completo'] and d['ciudadano']['nombres'] == 'María Fernanda', f'{s} {d}'
    caso('CP-01 Cédula existente: el funcionario recibe los datos completos para autocompletar', cp01)

    def cp01b():
        s, d = visitante.json('/api/ciudadanos/1017234567')
        assert s == 200 and not d['completo'] and '*' in d['ciudadano']['nombres'], f'{s} {d}'
    caso('CP-01b Cédula existente sin sesión: datos enmascarados (Ley 1581)', cp01b)

    def cp02():
        s, d = visitante.json('/api/ciudadanos/1099999998')
        assert s == 404 and d.get('encontrado') is False, f'estado {s}'
    caso('CP-02 Cédula nueva: 404 para habilitar la captura única', cp02)

    caso('CP-03 Cédula con letras: error sin consultar la base de datos', lambda: _estado(visitante('/api/ciudadanos/10172A4567'), 400))
    caso('CP-04 Cédula de menos de 6 dígitos: error de longitud', lambda: _estado(visitante('/api/ciudadanos/12345'), 400))
    caso('CP-05 Registro duplicado de cédula: 409', lambda: _estado(visitante('/api/ciudadanos', 'POST', {
        'cedula': '1017234567', 'fecha_expedicion': '2000-01-01', 'nombres': 'Otro', 'apellidos': 'Nombre', 'municipio': 'Bello',
        'telefono': '3001112233', 'acepta_tratamiento_datos': True}), 409))
    caso('Verificación con fecha de expedición incorrecta: rechazada',
         lambda: _estado(visitante('/api/ciudadanos/1017234567/verificar', 'POST', {'fecha_expedicion': '1999-12-31'}), 400))

    print('\nRadicación')
    nuevos = []

    def cp06():
        antes = len(ciudadano.json('/api/pqrds/mias')[1])
        for i in range(3):
            s, d = ciudadano.json('/api/pqrds', 'POST', formulario=formulario_pqrds(asunto=f'Caso de prueba número {i + 1}'))
            assert s == 201 and d['radicado'].startswith('PQRDS-'), f'radicación {s} {d}'
            nuevos.append(d['radicado'])
        despues = ciudadano.json('/api/pqrds/mias')[1]
        assert len(despues) == antes + 3, f'tenía {antes}, ahora {len(despues)}'
        consulta = admin.json('/api/admin/ciudadanos/1017234567/pqrds')[1]
        assert all(any(p['radicado'] == r for p in consulta['pqrds']) for r in nuevos), 'el administrador no ve los 3 casos'
    caso('CP-06 El mismo ciudadano radica 3 casos sin volver a digitar datos', cp06)

    def visitante_nuevo():
        cedula = str(1090000000 + random.randrange(9999999))
        datos = {'cedula': cedula, 'fecha_expedicion': '2012-03-04', 'nombres': 'Ciudadano', 'apellidos': 'De Prueba',
                 'municipio': 'Rionegro', 'telefono': '3015554433', 'correo': 'prueba@correo.example', 'acepta_tratamiento_datos': True}
        s, d = visitante.json('/api/pqrds', 'POST', formulario=formulario_pqrds(ciudadano=json.dumps(datos)))
        assert s == 201 and d['ciudadano_nuevo'] and d['token_verificacion'], f'{s} {d}'
        s2, d2 = visitante.json('/api/pqrds', 'POST', formulario=formulario_pqrds(token_verificacion=d['token_verificacion'], tipo='SUGERENCIA'))
        assert s2 == 201 and not d2['ciudadano_nuevo'], f'segunda radicación {s2}'
    caso('Visitante nuevo: crea su ficha y la PQRDS juntas y recibe la ficha para la siguiente', visitante_nuevo)

    def anonima():
        s, d = visitante.json('/api/pqrds', 'POST', formulario=formulario_pqrds(tipo='DENUNCIA', anonima='true', medio_respuesta=''))
        assert s == 201 and d['codigo_anonimo'], f'{s} {d}'
        s2, d2 = visitante.json(f"/api/pqrds/radicado/{d['radicado']}?codigo={d['codigo_anonimo']}")
        assert s2 == 200 and d2['estado'] == 'RADICADA', f'seguimiento {s2}'
    caso('Denuncia anónima y seguimiento con código', anonima)

    caso('Seguimiento con cédula equivocada: no revela la solicitud',
         lambda: _estado(visitante(f'/api/pqrds/radicado/{nuevos[0]}?cedula=43512876'), 404))

    def adjunto_valido():
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
        s, d = ciudadano.json('/api/pqrds', 'POST', formulario=formulario_pqrds(_archivos=[('adjuntos', 'soporte.pdf', 'application/pdf', pdf)]))
        assert s == 201 and d['adjuntos'] == 1, f'{s} {d}'
    caso('Adjunto PDF válido: se guarda', adjunto_valido)

    caso('Adjunto falso (texto con extensión .pdf): rechazado', lambda: _estado(ciudadano(
        '/api/pqrds', 'POST', formulario=formulario_pqrds(_archivos=[('adjuntos', 'falso.pdf', 'application/pdf', b'esto no es un pdf')])), 400))

    print('\nPanel del administrador')
    caso('Inicio de sesión del administrador', lambda: _cumple(estado_admin == 200 and datos_admin.get('rol') == 'ADMIN',
                                                            f'estado {estado_admin}: ¿cambió la contraseña? Ejecute python scripts/crear_datos.py'))

    def excel():
        s, tipo, cuerpo = admin('/api/admin/exportar?cedula=1017234567&estado=RADICADA')
        assert s == 200 and 'spreadsheetml' in tipo and cuerpo[:2] == b'PK', f'{s} {tipo}'
    caso('CP-07 Exportar a Excel con filtros aplicados', excel)

    def gestion():
        lista = admin.json('/api/admin/pqrds?estado=RADICADA&porPagina=5')[1]
        id_p = lista['registros'][0]['id_pqrds']
        s1, _ = admin.json(f'/api/admin/pqrds/{id_p}', 'PATCH', {'estado': 'RESPONDIDA'})
        assert s1 == 400, f'sin respuesta: {s1}'
        s2, d2 = admin.json(f'/api/admin/pqrds/{id_p}', 'PATCH', {'estado': 'RESPONDIDA', 'respuesta': 'Respuesta de prueba al ciudadano.'})
        assert s2 == 200 and d2['estado'] == 'RESPONDIDA', f'con respuesta: {s2}'
    caso('Gestión: marcar como respondida exige escribir la respuesta', gestion)

    def auditoria():
        s, d = admin.json('/api/admin/auditoria?accion=CONSULTA_CEDULA')
        assert s == 200 and d['total'] > 0, f"total {d.get('total')}"
    caso('La auditoría registra las consultas por cédula', auditoria)

    print('\nSeguridad')

    def inyeccion():
        a = visitante('/api/ciudadanos/' + urllib.parse.quote("' OR '1'='1"))[0]
        s, d = admin.json('/api/admin/pqrds?q=' + urllib.parse.quote("' OR '1'='1") + '&cedula=' + urllib.parse.quote("1' OR '1'='1"))
        assert a == 400, f'cédula: {a}'
        assert s == 200 and d['total'] == 0, f"bandeja: {s} total {d.get('total')}"
    caso("CP-08 Inyección SQL (' OR '1'='1) rechazada", inyeccion)

    def acceso_admin():
        pagina = ciudadano('/admin/dashboard.html')[0]
        api_admin = ciudadano('/api/admin/pqrds')[0]
        assert pagina == 403 and api_admin == 403, f'página {pagina}, API {api_admin}'
    caso('CP-09 Ciudadano intenta entrar a /admin: 403', acceso_admin)

    def funcionario_limites():
        a, b = funcionario('/api/admin/exportar')[0], funcionario('/api/admin/usuarios')[0]
        assert a == 403 and b == 403, f'{a} / {b}'
    caso('Funcionario no puede exportar ni gestionar usuarios', funcionario_limites)
    caso('Visitante sin sesión es enviado al inicio de sesión desde /admin', lambda: _estado(visitante('/admin/bandeja.html'), 302))
    caso('Ruta con ../ no permite leer archivos fuera de public', lambda: _cumple(
        visitante('/../configuracion.py')[0] == 404 and visitante('/%2e%2e/configuracion.py')[0] == 404, 'se pudo salir de public'))

    print('\nAsistente virtual')

    def chat_diferencia():
        d = visitante.json('/api/chatbot', 'POST', {'mensaje': '¿Qué diferencia hay entre queja y reclamo?'})[1]
        assert 'QUEJA' in d['respuesta'] and 'RECLAMO' in d['respuesta'], d['respuesta']
    caso('CP-10 "¿Qué diferencia hay entre queja y reclamo?" responde la diferencia', chat_diferencia)

    def chat_queja():
        d = visitante.json('/api/chatbot', 'POST', {'mensaje': 'quiero quejarme de un funcionario'})[1]
        assert (d.get('accion') or {}).get('url') == '/radicar.html?tipo=QUEJA', d
    caso('"Quiero quejarme de un funcionario" lleva al formulario de queja', chat_queja)

    def chat_documento():
        d = visitante.json('/api/chatbot', 'POST', {'mensaje': 'mi cedula es 1017234567'})[1]
        assert 'no escriba su número de documento' in d['respuesta'].lower(), d['respuesta']
    caso('No acepta números de documento en el chat', chat_documento)

    print(f"\n{resultados['aprobadas']} pruebas aprobadas, {resultados['fallidas']} fallidas.")
    sys.exit(1 if resultados['fallidas'] else 0)


def _estado(resultado, esperado):
    assert resultado[0] == esperado, f'estado {resultado[0]} (se esperaba {esperado})'


def _cumple(condicion, mensaje):
    assert condicion, mensaje


if __name__ == '__main__':
    import urllib.parse  # noqa: E402,F401
    main()
