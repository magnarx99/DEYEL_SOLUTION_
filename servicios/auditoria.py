"""Bitácora de auditoría: quién consultó, exportó o modificó datos personales, y cuándo."""
from nucleo import bd, tiempo, web


def registrar(accion, detalle=None):
    usuario = web.usuario_actual()
    bd.insertar('INSERT INTO auditoria (id_usuario, accion, detalle, ip, fecha) VALUES (?, ?, ?, ?, ?)',
                (usuario['id_usuario'] if usuario else None, accion, detalle, web.ip_actual(), tiempo.ahora()))


def listar(pagina=1, por_pagina=25, accion=None):
    filtro, parametros = '', []
    if accion:
        filtro, parametros = 'WHERE a.accion = ?', [accion]
    filas = bd.consultar(f"""SELECT a.id_auditoria, a.accion, a.detalle, a.ip, a.fecha, u.nombre AS usuario, u.rol,
                                    COUNT(*) OVER() AS total
                               FROM auditoria a LEFT JOIN usuario u ON u.id_usuario = a.id_usuario
                               {filtro}
                              ORDER BY a.fecha DESC, a.id_auditoria DESC LIMIT ? OFFSET ?""",
                         parametros + [por_pagina, (pagina - 1) * por_pagina])
    return {'total': filas[0]['total'] if filas else 0,
            'registros': [{k: v for k, v in f.items() if k != 'total'} for f in filas]}
