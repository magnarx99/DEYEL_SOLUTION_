"""Rutas de la API REST: cada dirección, quién puede usarla y qué función la atiende."""
from nucleo import adjuntos, bd, sesion
from nucleo.web import Enrutador, Respuesta, es_personal, limite, permitir, requerir_sesion
from servicios import auditoria, autenticacion, catalogos, chatbot, ciudadanos, excel, pqrds, usuarios
from nucleo import tiempo
from utilidades.errores import ErrorApp
from utilidades.validaciones import CEDULA_RE, RADICADO_RE, coincide, texto

api = Enrutador()
PERSONAL = ('FUNCIONARIO', 'ADMIN')
INTENTOS_LOGIN = (10, 15, 'Demasiados intentos. Espere 15 minutos e intente de nuevo.')


def _id(valor):
    if not str(valor).isdigit() or int(valor) <= 0:
        raise ErrorApp(400, 'Identificador no válido.')
    return int(valor)


# ====================================================================== autenticación
@api.ruta('POST', '/api/auth/registro')
@limite(*INTENTOS_LOGIN, grupo='acceso')
def registro(p):
    u = autenticacion.registrar(p.json())
    r = Respuesta.json({'mensaje': 'Cuenta creada. La vinculamos a las solicitudes que ya había presentado con su cédula.'
                        if u['vinculado'] else 'Cuenta creada correctamente.', 'rol': u['rol']}, 201)
    sesion.iniciar(r, u)
    return r


@api.ruta('POST', '/api/auth/login')
@limite(*INTENTOS_LOGIN, grupo='acceso')
def login(p):
    datos = p.json()
    u = autenticacion.iniciar_sesion(datos.get('usuario'), datos.get('password'))
    r = Respuesta.json({'rol': u['rol'], 'nombre': u['nombre'], 'debe_cambiar_password': bool(u['debe_cambiar_password'])})
    sesion.iniciar(r, u)
    return r


@api.ruta('POST', '/api/auth/logout')
def logout(p):
    r = Respuesta.json({'mensaje': 'Sesión cerrada.'})
    sesion.cerrar(r)
    return r


@api.ruta('GET', '/api/auth/yo')
def yo(p):
    """Datos de la sesión actual (para armar el menú y precargar formularios)."""
    u = p.usuario
    if not u:
        return {'autenticado': False}
    return {'autenticado': True,
            'usuario': {'nombre': u['nombre'], 'correo': u['correo'], 'rol': u['rol'], 'id_dependencia': u['id_dependencia'],
                        'debe_cambiar_password': u['debe_cambiar_password']},
            'ciudadano': ciudadanos.buscar_por_id(u['id_ciudadano']) if u['id_ciudadano'] else None}


@api.ruta('POST', '/api/auth/recuperar')
@limite(*INTENTOS_LOGIN, grupo='acceso')
def recuperar(p):
    origen = f"http://{p.cabeceras.get('Host', 'localhost')}"
    autenticacion.solicitar_recuperacion(p.json().get('correo'), origen)
    return {'mensaje': 'Si el correo está registrado, le enviamos un enlace para crear una nueva contraseña.'}


@api.ruta('POST', '/api/auth/restablecer')
@limite(*INTENTOS_LOGIN, grupo='acceso')
def restablecer(p):
    datos = p.json()
    autenticacion.restablecer(datos.get('token'), datos.get('password'))
    return {'mensaje': 'Contraseña actualizada. Ya puede iniciar sesión.'}


# Límite general por IP; los errores de contraseña además bloquean la cuenta (ver autenticacion.confirmar_password)
CONFIRMAR_PASSWORD = (20, 15, 'Demasiados intentos. Espere 15 minutos.')


@api.ruta('POST', '/api/auth/eliminar-cuenta')
@limite(*CONFIRMAR_PASSWORD, grupo='confirmar_password')
@requerir_sesion
def eliminar_cuenta(p):
    datos = p.json()
    r = Respuesta.json(autenticacion.eliminar_cuenta(p.usuario, datos.get('password'), datos.get('confirmacion')))
    sesion.cerrar(r)
    return r


@api.ruta('POST', '/api/auth/cambiar-password')
@requerir_sesion
def cambiar_password(p):
    datos = p.json()
    autenticacion.cambiar_password(p.usuario['id_usuario'], datos.get('actual'), datos.get('nueva'))
    return {'mensaje': 'Contraseña actualizada.'}


# ====================================================================== catálogos
@api.ruta('GET', '/api/catalogos')
def ver_catalogos(p):
    return {**catalogos.catalogos(), 'cita': catalogos.reglas_cita()}


# ====================================================================== ciudadanos (reconocimiento por cédula)
@api.ruta('GET', '/api/ciudadanos/<cedula>')
@limite(60, 15, 'Demasiadas consultas. Espere unos minutos.')
def buscar_ciudadano(p):
    cedula = p.parametros['cedula']
    if not coincide(CEDULA_RE, cedula):
        raise ErrorApp(400, 'La cédula debe tener de 6 a 10 dígitos, sin puntos ni espacios.')
    c = ciudadanos.buscar_por_cedula(cedula)
    if es_personal(p.usuario):
        auditoria.registrar('BUSCAR_CEDULA', f"Cédula {cedula}{'' if c else ' (no existe)'}")
    if not c:
        return Respuesta.json({'encontrado': False}, 404)
    return ciudadanos.presentar(p.usuario, c)


@api.ruta('POST', '/api/ciudadanos/<cedula>/verificar')
@limite(10, 15, 'Demasiados intentos de verificación. Espere 15 minutos.', grupo='verificacion')
def verificar_ciudadano(p):
    cedula = p.parametros['cedula']
    if not coincide(CEDULA_RE, cedula):
        raise ErrorApp(400, 'Cédula no válida.')
    return {'verificado': True, **ciudadanos.verificar_identidad(cedula, p.json())}


@api.ruta('POST', '/api/ciudadanos')
def crear_ciudadano(p):
    datos = p.json()
    nuevo = ciudadanos.crear(datos)
    if es_personal(p.usuario):
        auditoria.registrar('CREAR_CIUDADANO', f"Cédula {datos.get('cedula')}")
    return Respuesta.json({'id_ciudadano': nuevo,
                           'token_verificacion': None if p.usuario else ciudadanos.emitir_token_verificacion(nuevo)}, 201)


@api.ruta('PUT', '/api/ciudadanos/<id>')
@requerir_sesion
def actualizar_ciudadano(p):
    id_ciudadano = _id(p.parametros['id'])
    if not es_personal(p.usuario) and p.usuario['id_ciudadano'] != id_ciudadano:
        raise ErrorApp(403, 'Solo puede actualizar sus propios datos.')
    ciudadanos.actualizar(id_ciudadano, p.json())
    auditoria.registrar('ACTUALIZAR_CIUDADANO', f'Ciudadano #{id_ciudadano}')
    return {'actualizado': True, 'ciudadano': ciudadanos.buscar_por_id(id_ciudadano)}


@api.ruta('GET', '/api/ciudadanos/yo/documento')
@permitir('CIUDADANO')
def estado_documento(p):
    """Cuántas correcciones del documento le quedan al ciudadano este año."""
    usadas = ciudadanos.correcciones_recientes(p.usuario['id_ciudadano'])
    return {'usadas': usadas, 'maximo': ciudadanos.MAX_CORRECCIONES, 'disponibles': max(ciudadanos.MAX_CORRECCIONES - usadas, 0)}


@api.ruta('POST', '/api/ciudadanos/yo/documento')
@limite(*CONFIRMAR_PASSWORD, grupo='confirmar_password')
@permitir('CIUDADANO')
def corregir_documento(p):
    datos = p.json()
    autenticacion.confirmar_password(p.usuario['id_usuario'], datos.get('password'))
    return {'actualizado': True, 'ciudadano': ciudadanos.corregir_documento(p.usuario['id_ciudadano'], datos)}


# ====================================================================== PQRDS
@api.ruta('POST', '/api/pqrds')
@limite(20, 60, 'Ha radicado muchas solicitudes en poco tiempo. Intente más tarde.')
def radicar(p):
    campos, archivos = p.formulario()
    p.archivos_guardados = adjuntos.guardar(archivos)   # si algo falla después, el servidor los borra
    return Respuesta.json(pqrds.radicar(campos, p.archivos_guardados), 201)


@api.ruta('GET', '/api/pqrds/radicado/<radicado>')
@limite(10, 15, 'Demasiados intentos de verificación. Espere 15 minutos.', grupo='verificacion')
def seguimiento(p):
    radicado = texto(p.parametros['radicado']).upper()
    if not coincide(RADICADO_RE, radicado):
        raise ErrorApp(400, 'El radicado debe tener el formato PQRDS-AAAA-000000.')
    return pqrds.seguimiento(radicado, texto(p.consulta.get('cedula')), texto(p.consulta.get('codigo')))


@api.ruta('GET', '/api/pqrds/mias')
@permitir('CIUDADANO')
def mis_pqrds(p):
    return pqrds.mias()


# ====================================================================== panel de gestión
@api.ruta('GET', '/api/admin/estadisticas')
@permitir('ADMIN')
def estadisticas(p):
    return pqrds.estadisticas()


@api.ruta('GET', '/api/admin/pqrds')
@permitir(*PERSONAL)
def bandeja(p):
    return pqrds.listar(p.consulta)


@api.ruta('GET', '/api/admin/pqrds/<id>')
@permitir(*PERSONAL)
def detalle(p):
    return pqrds.detalle(_id(p.parametros['id']))


@api.ruta('PATCH', '/api/admin/pqrds/<id>')
@permitir(*PERSONAL)
def gestionar(p):
    return pqrds.gestionar(_id(p.parametros['id']), p.json())


@api.ruta('GET', '/api/admin/ciudadanos/<cedula>/pqrds')
@permitir(*PERSONAL)
def pqrds_por_cedula(p):
    return pqrds.por_cedula(p.parametros['cedula'])


@api.ruta('GET', '/api/admin/exportar')
@permitir('ADMIN')
def exportar(p):
    """Descarga en Excel con los mismos filtros de la bandeja."""
    registros = pqrds.listar(p.consulta, sin_paginar=True)['registros']
    filtros = [f'{k}={v}' for k, v in p.consulta.items() if v and k not in ('pagina', 'porPagina')]
    auditoria.registrar('EXPORTAR_EXCEL', f"{len(registros)} registros" + (f"; filtros: {', '.join(filtros)}" if filtros else ''))
    return Respuesta.descarga(excel.generar_libro(registros), f'PQRDS_Gobernacion_{tiempo.hoy()}.xlsx',
                              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@api.ruta('GET', '/api/admin/adjuntos/<id>')
@permitir(*PERSONAL)
def descargar_adjunto(p):
    a = bd.uno('SELECT * FROM pqrds_adjunto WHERE id_adjunto = ?', (_id(p.parametros['id']),))
    if not a:
        raise ErrorApp(404, 'Adjunto no encontrado.')
    pqrds.verificar_alcance(a['id_pqrds'])
    ruta = adjuntos.ruta_segura(a['ruta'])
    if not ruta.exists():
        raise ErrorApp(404, 'El archivo ya no está disponible.')
    auditoria.registrar('DESCARGAR_ADJUNTO', a['nombre_original'])
    return Respuesta.archivo(ruta, a['nombre_original'])


@api.ruta('GET', '/api/admin/funcionarios')
@permitir(*PERSONAL)
def lista_funcionarios(p):
    return usuarios.funcionarios()


@api.ruta('GET', '/api/admin/usuarios')
@permitir('ADMIN')
def lista_usuarios(p):
    return usuarios.listar(p.consulta.get('rol'), p.consulta.get('q'))


@api.ruta('POST', '/api/admin/usuarios')
@permitir('ADMIN')
def crear_usuario(p):
    datos = p.json()
    nuevo = usuarios.crear_personal(datos)
    auditoria.registrar('CREAR_USUARIO', f"{datos.get('correo')} ({datos.get('rol')})")
    return Respuesta.json(nuevo, 201)


@api.ruta('PATCH', '/api/admin/usuarios/<id>')
@permitir('ADMIN')
def actualizar_usuario(p):
    r = usuarios.actualizar(_id(p.parametros['id']), p.json(), p.usuario)
    auditoria.registrar('ACTUALIZAR_USUARIO', f"{r['nombre']}: rol {r['rol']}, {'activo' if r['activo'] else 'inactivo'}")
    return r


@api.ruta('GET', '/api/admin/faq')
@permitir('ADMIN')
def lista_faq(p):
    return catalogos.listar_faq()


@api.ruta('POST', '/api/admin/faq')
@permitir('ADMIN')
def crear_faq(p):
    return Respuesta.json(catalogos.guardar_faq(None, p.json()), 201)


@api.ruta('PUT', '/api/admin/faq/<id>')
@permitir('ADMIN')
def editar_faq(p):
    return catalogos.guardar_faq(_id(p.parametros['id']), p.json())


@api.ruta('DELETE', '/api/admin/faq/<id>')
@permitir('ADMIN')
def borrar_faq(p):
    catalogos.eliminar_faq(_id(p.parametros['id']))
    return {'eliminado': True}


@api.ruta('GET', '/api/admin/auditoria')
@permitir('ADMIN')
def ver_auditoria(p):
    pagina = max(int(p.consulta['pagina']) if str(p.consulta.get('pagina', '')).isdigit() else 1, 1)
    return auditoria.listar(pagina=pagina, accion=p.consulta.get('accion') or None)


# ====================================================================== asistente virtual
@api.ruta('POST', '/api/chatbot')
@limite(30, 1, 'Está enviando mensajes muy rápido. Espere un momento.')
def asistente(p):
    return chatbot.responder(p.json().get('mensaje'), p.usuario)
