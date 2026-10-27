"""PQRDS: radicación, seguimiento, bandeja de gestión, consulta por cédula y estadísticas."""
import json

from nucleo import bd, tiempo, web
from servicios import auditoria, ciudadanos, fechas
from utilidades.errores import ErrorApp
from utilidades.radicado import generar_codigo_anonimo, generar_radicado
from utilidades.validaciones import CEDULA_RE, ESTADOS, coincide, es_fecha_valida, texto

CANALES = ['WEB', 'PRESENCIAL', 'TELEFONICO']
ETIQUETA_CANAL = {'WEB': 'portal web', 'PRESENCIAL': 'atención presencial', 'TELEFONICO': 'atención telefónica'}


def _entero(valor, defecto=None):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def semaforo(p):
    """Atendida, Vencida, Por vencer (4 días o menos) o A tiempo."""
    if p['estado'] in ('RESPONDIDA', 'CERRADA'):
        return 'ATENDIDA'
    hoy = tiempo.hoy()
    if p['fecha_limite'] < hoy:
        return 'VENCIDA'
    return 'POR_VENCER' if p['fecha_limite'] <= tiempo.sumar_dias_calendario(hoy, 4) else 'A_TIEMPO'


def _con_semaforo(filas):
    for f in filas:
        f['semaforo'] = semaforo(f)
    return filas


# ============================================================================ radicación
def _leer_ciudadano(valor):
    if not valor:
        return None
    if isinstance(valor, dict):
        return valor
    try:
        return json.loads(valor)
    except ValueError as err:
        raise ErrorApp(400, 'Los datos personales no tienen un formato válido.') from err


def _validar_caso(cuerpo, tipo):
    dependencia = cuerpo.get('id_dependencia')
    caso = {
        'id_dependencia': _entero(dependencia, -1) if dependencia else None,
        'municipio_hecho': texto(cuerpo.get('municipio_hecho')),
        'asunto': texto(cuerpo.get('asunto')),
        'descripcion': texto(cuerpo.get('descripcion')),
        'medio_respuesta': texto(cuerpo.get('medio_respuesta')) or 'CORREO',
        'fecha_cita_preferida': texto(cuerpo.get('fecha_cita_preferida')) or None,
        'modalidad_cita': texto(cuerpo.get('modalidad_cita')) or None,
    }
    e = {}
    if caso['id_dependencia'] is not None and not bd.uno('SELECT 1 AS ok FROM dependencia WHERE id_dependencia = ?', (caso['id_dependencia'],)):
        e['id_dependencia'] = 'Seleccione una dependencia de la lista.'
    if not ciudadanos.validar_municipio(caso['municipio_hecho']):
        e['municipio_hecho'] = 'Seleccione el municipio donde ocurrió el hecho.'
    if not 5 <= len(caso['asunto']) <= 150:
        e['asunto'] = 'El asunto debe tener entre 5 y 150 caracteres.'
    if not 20 <= len(caso['descripcion']) <= 3000:
        e['descripcion'] = 'Describa su caso con al menos 20 caracteres (máximo 3.000).'
    if caso['medio_respuesta'] not in ('CORREO', 'FISICO', 'NINGUNO'):
        e['medio_respuesta'] = 'Seleccione cómo quiere recibir la respuesta.'
    if tipo['codigo'] == 'CITA':
        manana = tiempo.sumar_dias_calendario(tiempo.hoy(), 1)
        if not es_fecha_valida(caso['fecha_cita_preferida']) or caso['fecha_cita_preferida'] < manana:
            e['fecha_cita_preferida'] = 'Elija una fecha a partir de mañana.'
        if caso['modalidad_cita'] not in ('PRESENCIAL', 'VIRTUAL'):
            e['modalidad_cita'] = 'Indique si prefiere la cita presencial o virtual.'
    else:
        caso['fecha_cita_preferida'] = None
        caso['modalidad_cita'] = None
    return caso, e


def radicar(cuerpo, adjuntos):
    """Radica una PQRDS. Identifica al ciudadano según quién radica:
    - Ciudadano con sesión: usa su propia ficha (no digita nada).
    - Funcionario o administrador: busca por cédula; si no existe, crea la ficha con los datos enviados.
    - Visitante: usa la ficha de verificación (ya registrado) o crea la ficha (primera vez).
    - Denuncia anónima: sin ciudadano."""
    usuario = web.usuario_actual()
    tipo = bd.uno('SELECT * FROM tipo_solicitud WHERE codigo = ?', (texto(cuerpo.get('tipo')),))
    if not tipo:
        raise ErrorApp(400, 'Seleccione un tipo de solicitud válido.', {'tipo': 'Tipo no válido.'})
    anonima = tipo['permite_anonimo'] and str(cuerpo.get('anonima')) == 'true'
    canal = cuerpo.get('canal') if web.es_personal(usuario) and cuerpo.get('canal') in CANALES else 'WEB'

    with bd.transaccion():
        caso, errores = _validar_caso(cuerpo, tipo)
        if anonima:
            caso['medio_respuesta'] = 'NINGUNO'
        elif caso['medio_respuesta'] == 'NINGUNO':
            errores['medio_respuesta'] = 'Seleccione cómo quiere recibir la respuesta.'
        if errores:
            raise ErrorApp(400, 'Revise los campos del caso marcados.', errores)

        # 1. Identificar o registrar al ciudadano (una sola vez)
        id_ciudadano, nuevo = None, False
        if not anonima:
            if usuario and usuario['rol'] == 'CIUDADANO':
                id_ciudadano = usuario['id_ciudadano']
            elif web.es_personal(usuario):
                cedula = texto(cuerpo.get('cedula'))
                if not coincide(CEDULA_RE, cedula):
                    raise ErrorApp(400, 'La cédula debe tener de 6 a 10 dígitos.', {'cedula': 'Cédula no válida.'})
                existente = ciudadanos.buscar_por_cedula(cedula)
                if existente:
                    id_ciudadano = existente['id_ciudadano']
                else:
                    id_ciudadano = ciudadanos.crear({**(_leer_ciudadano(cuerpo.get('ciudadano')) or {}), 'cedula': cedula})
                    nuevo = True
            else:
                id_ciudadano = ciudadanos.leer_token_verificacion(cuerpo.get('token_verificacion'))
                if not id_ciudadano:
                    datos = _leer_ciudadano(cuerpo.get('ciudadano'))
                    if not datos:
                        raise ErrorApp(400, 'Identifíquese con su cédula antes de radicar.')
                    id_ciudadano = ciudadanos.crear(datos)      # 409 si la cédula ya existe
                    nuevo = True
            if caso['medio_respuesta'] == 'CORREO':
                c = ciudadanos.buscar_por_id(id_ciudadano)
                if not c or not c['correo']:
                    raise ErrorApp(400, 'No tiene un correo registrado. Elija respuesta por dirección física o actualice sus datos.',
                                   {'medio_respuesta': 'Sin correo registrado.'})

        # 2. Radicado y fecha límite en días hábiles
        radicado = generar_radicado()
        fecha_radicacion = tiempo.ahora()
        fecha_limite = fechas.sumar_dias_habiles(tiempo.hoy(), tipo['dias_habiles_respuesta'])
        codigo = generar_codigo_anonimo() if anonima else None
        id_pqrds = bd.insertar(
            """INSERT INTO pqrds (radicado, id_ciudadano, id_tipo, id_dependencia, id_usuario_radicador, canal, municipio_hecho,
                 asunto, descripcion, medio_respuesta, fecha_cita_preferida, modalidad_cita, es_anonima, codigo_anonimo,
                 fecha_radicacion, fecha_limite)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (radicado, id_ciudadano, tipo['id_tipo'], caso['id_dependencia'], usuario['id_usuario'] if usuario else None, canal,
             caso['municipio_hecho'], caso['asunto'], caso['descripcion'], caso['medio_respuesta'], caso['fecha_cita_preferida'],
             caso['modalidad_cita'], anonima, codigo, fecha_radicacion, fecha_limite))
        for a in adjuntos:
            bd.insertar('INSERT INTO pqrds_adjunto (id_pqrds, nombre_original, ruta, tipo_mime, tamano) VALUES (?,?,?,?,?)',
                        (id_pqrds, a['nombre_original'][:200], a['ruta'], a['tipo_mime'], a['tamano']))
        bd.insertar("""INSERT INTO pqrds_historial (id_pqrds, estado_anterior, estado_nuevo, id_usuario, comentario, fecha)
                       VALUES (?, NULL, 'RADICADA', ?, ?, ?)""",
                    (id_pqrds, usuario['id_usuario'] if usuario else None, f'Solicitud radicada por {ETIQUETA_CANAL[canal]}.', fecha_radicacion))
        if web.es_personal(usuario):
            auditoria.registrar('RADICAR_EN_NOMBRE', f"{radicado} para cédula {texto(cuerpo.get('cedula'))}")

    return {
        'radicado': radicado, 'tipo': tipo['nombre'], 'fecha_radicacion': fecha_radicacion, 'fecha_limite': fecha_limite,
        'dias_habiles': tipo['dias_habiles_respuesta'], 'adjuntos': len(adjuntos), 'ciudadano_nuevo': nuevo,
        'codigo_anonimo': codigo,
        # Permite registrar otra solicitud en la misma sesión sin volver a digitar datos
        'token_verificacion': ciudadanos.emitir_token_verificacion(id_ciudadano) if (not anonima and not usuario) else None,
    }


# ============================================================================ consultas
SELECT_BASE = """
  SELECT p.id_pqrds, p.radicado, p.estado, p.asunto, p.descripcion, p.canal, p.municipio_hecho,
         p.medio_respuesta, p.fecha_radicacion, p.fecha_limite, p.fecha_respuesta, p.respuesta,
         p.es_anonima, p.fecha_cita_preferida, p.modalidad_cita, p.id_ciudadano,
         t.codigo AS tipo_codigo, t.nombre AS tipo, d.nombre AS dependencia, p.id_dependencia,
         p.id_funcionario_asignado, f.nombre AS funcionario,
         c.cedula, c.nombres, c.apellidos, c.municipio, c.telefono, c.correo
    FROM pqrds p
    JOIN tipo_solicitud t ON t.id_tipo = p.id_tipo
    LEFT JOIN dependencia d ON d.id_dependencia = p.id_dependencia
    LEFT JOIN usuario f ON f.id_usuario = p.id_funcionario_asignado
    LEFT JOIN ciudadano c ON c.id_ciudadano = p.id_ciudadano"""


def _historial_publico(id_pqrds):
    return bd.consultar('SELECT estado_anterior, estado_nuevo, fecha FROM pqrds_historial WHERE id_pqrds = ? ORDER BY fecha, id_historial', (id_pqrds,))


def _vista_publica(p):
    """Datos de una PQRDS sin información personal."""
    atendida = p['estado'] in ('RESPONDIDA', 'CERRADA')
    return {
        'radicado': p['radicado'], 'tipo': p['tipo'], 'tipo_codigo': p['tipo_codigo'], 'estado': p['estado'], 'asunto': p['asunto'],
        'dependencia': p['dependencia'] or 'Por asignar', 'fecha_radicacion': p['fecha_radicacion'], 'fecha_limite': p['fecha_limite'],
        'fecha_respuesta': p['fecha_respuesta'], 'semaforo': semaforo(p), 'respuesta': p['respuesta'] if atendida else None,
        'fecha_cita_preferida': p['fecha_cita_preferida'], 'modalidad_cita': p['modalidad_cita'],
    }


def seguimiento(radicado, cedula, codigo):
    """Consulta por radicado: exige la cédula del titular, el código anónimo o una sesión autorizada."""
    usuario = web.usuario_actual()
    p = bd.uno(f'{SELECT_BASE} WHERE p.radicado = ?', (radicado,))
    autorizado = p is not None and (
        web.es_personal(usuario)
        or (usuario is not None and p['id_ciudadano'] is not None and usuario['id_ciudadano'] == p['id_ciudadano'])
        or (bool(cedula) and p['cedula'] == cedula)
        or (bool(codigo) and p['es_anonima']
            and codigo.upper() == bd.uno('SELECT codigo_anonimo FROM pqrds WHERE id_pqrds = ?', (p['id_pqrds'],))['codigo_anonimo'])
    )
    # Mismo mensaje si no existe o si los datos no coinciden: no se revela qué radicados existen
    if not autorizado:
        raise ErrorApp(404, 'No encontramos una solicitud con ese radicado y documento. Verifique los datos.')
    return {**_vista_publica(p), 'historial': _historial_publico(p['id_pqrds'])}


def mias():
    filas = bd.consultar(f'{SELECT_BASE} WHERE p.id_ciudadano = ? ORDER BY p.fecha_radicacion DESC', (web.usuario_actual()['id_ciudadano'],))
    return [{**_vista_publica(p), 'descripcion': p['descripcion'], 'historial': _historial_publico(p['id_pqrds'])} for p in filas]


# ============================================================================ bandeja de gestión
# Columnas permitidas para ordenar (lista blanca: el usuario nunca escribe SQL)
ORDENES = {'fecha': 'b.fecha_radicacion', 'limite': 'b.fecha_limite', 'radicado': 'b.radicado', 'estado': 'b.estado',
           'tipo': 'b.tipo', 'dependencia': 'b.dependencia', 'ciudadano': 'b.apellidos'}


def _filtros(f, usuario):
    """Arma el WHERE con parámetros '?' a partir de los filtros (nunca se pegan valores al SQL)."""
    cond, params = [], []
    if es_fecha_valida(f.get('desde')):
        cond.append('substr(p.fecha_radicacion, 1, 10) >= ?'); params.append(f['desde'])
    if es_fecha_valida(f.get('hasta')):
        cond.append('substr(p.fecha_radicacion, 1, 10) <= ?'); params.append(f['hasta'])
    if f.get('tipo'):
        cond.append('t.codigo = ?'); params.append(f['tipo'])
    if f.get('estado') in ESTADOS:
        cond.append('p.estado = ?'); params.append(f['estado'])
    if f.get('dependencia') == 'SIN':
        cond.append('p.id_dependencia IS NULL')
    elif str(f.get('dependencia') or '').isdigit():
        cond.append('p.id_dependencia = ?'); params.append(int(f['dependencia']))
    if f.get('municipio'):
        cond.append('p.municipio_hecho = ?'); params.append(f['municipio'])
    if coincide(CEDULA_RE, f.get('cedula')):
        cond.append('c.cedula = ?'); params.append(f['cedula'])
    if f.get('q'):
        patron = f"%{str(f['q'])[:80]}%"
        cond.append('(p.radicado LIKE ? OR p.asunto LIKE ? OR c.apellidos LIKE ? OR c.nombres LIKE ?)'); params += [patron] * 4
    hoy = tiempo.hoy()
    if f.get('semaforo') == 'VENCIDA':
        cond.append("p.estado NOT IN ('RESPONDIDA','CERRADA') AND p.fecha_limite < ?"); params.append(hoy)
    if f.get('semaforo') == 'POR_VENCER':
        cond.append("p.estado NOT IN ('RESPONDIDA','CERRADA') AND p.fecha_limite BETWEEN ? AND ?")
        params += [hoy, tiempo.sumar_dias_calendario(hoy, 4)]
    # Alcance del funcionario: su dependencia, lo asignado a él y, si es de Atención a la Ciudadanía, lo no asignado
    if usuario and usuario['rol'] == 'FUNCIONARIO':
        cond.append("""(p.id_dependencia = ? OR p.id_funcionario_asignado = ?
                       OR (p.id_dependencia IS NULL AND ? = (SELECT id_dependencia FROM dependencia WHERE nombre = 'Atención a la Ciudadanía')))""")
        params += [usuario['id_dependencia'], usuario['id_usuario'], usuario['id_dependencia']]
    return ('WHERE ' + ' AND '.join(cond)) if cond else '', params


def listar(filtros, sin_paginar=False):
    where, params = _filtros(filtros, web.usuario_actual())
    columna = ORDENES.get(filtros.get('orden'), ORDENES['fecha'])
    direccion = 'ASC' if filtros.get('dir') == 'asc' else 'DESC'
    por_pagina = min(max(_entero(filtros.get('porPagina'), 15), 5), 100)
    pagina = max(_entero(filtros.get('pagina'), 1), 1)
    limite, extra = ('LIMIT 50000', []) if sin_paginar else ('LIMIT ? OFFSET ?', [por_pagina, (pagina - 1) * por_pagina])
    filas = bd.consultar(f"""SELECT b.*, COUNT(*) OVER() AS total FROM ({SELECT_BASE} {where}) b
                              ORDER BY {columna} {direccion} NULLS LAST, b.id_pqrds DESC {limite}""", params + extra)
    return {'total': filas[0]['total'] if filas else 0, 'pagina': pagina, 'porPagina': por_pagina,
            'registros': _con_semaforo([{k: v for k, v in f.items() if k != 'total'} for f in filas])}


def verificar_alcance(id_pqrds):
    """Comprueba que quien consulta pueda ver y gestionar esa PQRDS."""
    where, params = _filtros({}, web.usuario_actual())
    p = bd.uno(f"{SELECT_BASE} {where + ' AND' if where else 'WHERE'} p.id_pqrds = ?", params + [id_pqrds])
    if not p:
        raise ErrorApp(404, 'La solicitud no existe o no pertenece a su dependencia.')
    p['semaforo'] = semaforo(p)
    return p


def detalle(id_pqrds):
    p = verificar_alcance(id_pqrds)
    adjuntos = bd.consultar('SELECT id_adjunto, nombre_original, tipo_mime, tamano FROM pqrds_adjunto WHERE id_pqrds = ?', (id_pqrds,))
    historial = bd.consultar("""SELECT h.estado_anterior, h.estado_nuevo, h.comentario, h.fecha, u.nombre AS usuario
                                  FROM pqrds_historial h LEFT JOIN usuario u ON u.id_usuario = h.id_usuario
                                 WHERE h.id_pqrds = ? ORDER BY h.fecha, h.id_historial""", (id_pqrds,))
    ciudadano = ciudadanos.buscar_por_id(p['id_ciudadano']) if p['id_ciudadano'] else None
    auditoria.registrar('VER_PQRDS', p['radicado'])
    atendida = p['estado'] in ('RESPONDIDA', 'CERRADA')
    return {**p, 'dias_habiles_restantes': None if atendida else fechas.dias_habiles_restantes(p['fecha_limite']),
            'ciudadano': ciudadano, 'adjuntos': adjuntos, 'historial': historial}


def gestionar(id_pqrds, cambios):
    """Cambia el estado, traslada de dependencia, asigna funcionario o registra la respuesta."""
    usuario = web.usuario_actual()
    actual = verificar_alcance(id_pqrds)
    estado = cambios.get('estado') or actual['estado']
    comentario = texto(cambios.get('comentario'))
    respuesta = texto(cambios.get('respuesta'))
    e = {}
    if estado not in ESTADOS:
        e['estado'] = 'Estado no válido.'
    if estado == 'RESPONDIDA' and len(respuesta) < 10 and not actual['respuesta']:
        e['respuesta'] = 'Escriba la respuesta al ciudadano (mínimo 10 caracteres).'
    if actual['estado'] == 'CERRADA' and estado != 'CERRADA':
        e['estado'] = 'Una solicitud cerrada no puede reabrirse.'

    id_dependencia = actual['id_dependencia']
    if 'id_dependencia' in cambios and cambios['id_dependencia'] != '':
        id_dependencia = None if cambios['id_dependencia'] is None else _entero(cambios['id_dependencia'], -1)
        if id_dependencia is not None and not bd.uno('SELECT 1 AS ok FROM dependencia WHERE id_dependencia = ?', (id_dependencia,)):
            e['id_dependencia'] = 'Dependencia no válida.'
    id_funcionario = actual['id_funcionario_asignado']
    if 'id_funcionario_asignado' in cambios:
        if usuario['rol'] != 'ADMIN':
            raise ErrorApp(403, 'Solo el administrador puede asignar funcionarios.')
        id_funcionario = _entero(cambios['id_funcionario_asignado'], -1) if cambios['id_funcionario_asignado'] else None
        if id_funcionario and not bd.uno("SELECT 1 AS ok FROM usuario WHERE id_usuario = ? AND rol IN ('FUNCIONARIO','ADMIN') AND activo = 1", (id_funcionario,)):
            e['id_funcionario_asignado'] = 'Funcionario no válido.'
    if e:
        raise ErrorApp(400, 'Revise los campos marcados.', e)

    cambio_dependencia = id_dependencia != actual['id_dependencia']
    estado_final = 'TRASLADADA' if cambio_dependencia and estado == actual['estado'] and estado != 'CERRADA' else estado
    ahora = tiempo.ahora()
    with bd.transaccion():
        bd.ejecutar("""UPDATE pqrds SET estado = ?, id_dependencia = ?, id_funcionario_asignado = ?,
                              respuesta = COALESCE(NULLIF(?, ''), respuesta),
                              fecha_respuesta = CASE WHEN ? = 'RESPONDIDA' AND fecha_respuesta IS NULL THEN ? ELSE fecha_respuesta END
                        WHERE id_pqrds = ?""",
                    (estado_final, id_dependencia, id_funcionario, respuesta, estado_final, ahora, id_pqrds))
        notas = [comentario]
        if cambio_dependencia:
            fila = bd.uno('SELECT nombre FROM dependencia WHERE id_dependencia = ?', (id_dependencia,)) if id_dependencia else None
            notas.append(f"Trasladada a {fila['nombre'] if fila else 'sin dependencia'}.")
        if id_funcionario != actual['id_funcionario_asignado']:
            notas.append('Funcionario asignado actualizado.')
        if respuesta:
            notas.append('Se registró respuesta al ciudadano.')
        if estado_final != actual['estado'] or any(notas):
            bd.insertar("""INSERT INTO pqrds_historial (id_pqrds, estado_anterior, estado_nuevo, id_usuario, comentario, fecha)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (id_pqrds, actual['estado'], estado_final, usuario['id_usuario'], ' '.join(n for n in notas if n) or None, ahora))
        auditoria.registrar('GESTIONAR_PQRDS', f"{actual['radicado']}: {actual['estado']} → {estado_final}")
    return detalle(id_pqrds)


def por_cedula(cedula):
    """Ficha del ciudadano y todas sus PQRDS (consulta por cédula del panel)."""
    if not coincide(CEDULA_RE, cedula):
        raise ErrorApp(400, 'La cédula debe tener de 6 a 10 dígitos.')
    ciudadano = ciudadanos.buscar_por_cedula(cedula)
    auditoria.registrar('CONSULTA_CEDULA', f"Cédula {cedula}{'' if ciudadano else ' (sin resultados)'}")
    if not ciudadano:
        raise ErrorApp(404, 'No hay ningún ciudadano registrado con esa cédula.')
    filas = bd.consultar(f'{SELECT_BASE} WHERE p.id_ciudadano = ? ORDER BY p.fecha_radicacion DESC', (ciudadano['id_ciudadano'],))
    return {'ciudadano': ciudadano, 'pqrds': _con_semaforo(filas)}


def estadisticas():
    """Datos del tablero del administrador."""
    hoy = tiempo.hoy()
    en3 = fechas.sumar_dias_habiles(hoy, 3)
    totales = bd.uno("""SELECT COUNT(*) AS total,
              COUNT(*) FILTER (WHERE estado = 'RADICADA') AS radicadas,
              COUNT(*) FILTER (WHERE estado IN ('EN_TRAMITE','TRASLADADA')) AS en_tramite,
              COUNT(*) FILTER (WHERE estado IN ('RESPONDIDA','CERRADA')) AS respondidas,
              COUNT(*) FILTER (WHERE estado NOT IN ('RESPONDIDA','CERRADA') AND fecha_limite < ?) AS vencidas,
              COUNT(*) FILTER (WHERE estado NOT IN ('RESPONDIDA','CERRADA') AND fecha_limite BETWEEN ? AND ?) AS por_vencer,
              COUNT(DISTINCT id_ciudadano) AS ciudadanos
         FROM pqrds""", (hoy, hoy, en3))
    por_tipo = bd.consultar("""SELECT t.nombre, COUNT(p.id_pqrds) AS total FROM tipo_solicitud t
                                LEFT JOIN pqrds p ON p.id_tipo = t.id_tipo GROUP BY t.id_tipo ORDER BY t.orden""")
    por_dependencia = bd.consultar("""SELECT COALESCE(d.nombre, 'Por asignar') AS nombre, COUNT(*) AS total FROM pqrds p
                                       LEFT JOIN dependencia d ON d.id_dependencia = p.id_dependencia
                                      GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 8""")
    hace_6_meses = tiempo.sumar_dias_calendario(hoy, -183)
    por_mes = bd.consultar("""SELECT substr(fecha_radicacion, 1, 7) AS mes, COUNT(*) AS total
                                FROM pqrds WHERE substr(fecha_radicacion, 1, 10) >= ? GROUP BY 1 ORDER BY 1""", (hace_6_meses,))
    ultimas = _con_semaforo(bd.consultar(f'{SELECT_BASE} ORDER BY p.fecha_radicacion DESC, p.id_pqrds DESC LIMIT 8'))
    return {'totales': totales, 'porTipo': por_tipo, 'porDependencia': por_dependencia, 'porMes': por_mes, 'ultimas': ultimas}
