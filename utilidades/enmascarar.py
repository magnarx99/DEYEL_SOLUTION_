"""Enmascaramiento de datos personales (Ley 1581 de 2012).
Se usa cuando quien consulta una cédula no es el titular ni un funcionario."""


def enmascarar_nombre(nombre=''):
    """'Juan Carlos' -> 'Jua*** Car***'"""
    return ' '.join(f'{p[0]}**' if len(p) <= 3 else f'{p[:3]}***' for p in (nombre or '').split())


def enmascarar_telefono(telefono=''):
    """'3001234521' -> '******4521'"""
    return '*' * max(len(telefono) - 4, 0) + telefono[-4:] if telefono else ''


def enmascarar_correo(correo=''):
    """'juana.perez@correo.com' -> 'ju*********@correo.com'"""
    if not correo or '@' not in correo:
        return ''
    usuario, dominio = correo.split('@', 1)
    return f"{usuario[:2]}{'*' * max(len(usuario) - 2, 3)}@{dominio}"


def ciudadano_enmascarado(c):
    """Solo los datos mínimos y enmascarados de un ciudadano."""
    return {
        'nombres': enmascarar_nombre(c['nombres']),
        'apellidos': enmascarar_nombre(c['apellidos']),
        'telefono': enmascarar_telefono(c['telefono']),
        'correo': enmascarar_correo(c.get('correo')),
        'municipio': c['municipio'],
        'tiene_correo': bool(c.get('correo')),
    }
