"""Sesión del usuario: una ficha firmada guardada en la cookie 'pqrds_sesion' (httpOnly:
el JavaScript del navegador no puede leerla, lo que la protege de robos)."""
import configuracion
from nucleo import bd, claves

NOMBRE_COOKIE = 'pqrds_sesion'


def iniciar(respuesta, usuario):
    segundos = configuracion.SESION_HORAS * 3600
    ficha = claves.crear_ficha({'id': usuario['id_usuario'], 'rol': usuario['rol']}, segundos)
    respuesta.poner_cookie(NOMBRE_COOKIE, ficha, segundos, segura=configuracion.PRODUCCION)


def cerrar(respuesta):
    respuesta.borrar_cookie(NOMBRE_COOKIE)


def leer(peticion):
    """Si la cookie es válida, deja el usuario en peticion.usuario."""
    datos = claves.leer_ficha(peticion.cookies.get(NOMBRE_COOKIE))
    if not datos:
        return
    # Se consulta la base de datos en cada petición: así una cuenta desactivada pierde el acceso de inmediato
    peticion.usuario = bd.uno("""SELECT id_usuario, id_ciudadano, nombre, correo, rol, id_dependencia, debe_cambiar_password
                                   FROM usuario WHERE id_usuario = ? AND activo = 1""", (datos.get('id'),))
