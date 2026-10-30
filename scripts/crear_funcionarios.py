"""Agrega los funcionarios de prueba a la base de datos ACTUAL, sin borrar nada.

Uso (desde la carpeta del proyecto):   python scripts/crear_funcionarios.py

Sirve cuando la base se creó con `crear_datos.py --vacia` (solo trae el administrador)
y se quiere probar el panel con el rol Funcionario. Si un funcionario ya existe,
se reactiva, se desbloquea y se le vuelve a poner la contraseña de prueba.
Antes de tocar la base guarda una copia en database/respaldos/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # para importar los módulos del proyecto

import configuracion  # noqa: E402
from nucleo import bd, claves, tiempo  # noqa: E402
from scripts.crear_datos import CLAVE_FUNCIONARIOS, FUNCIONARIOS  # noqa: E402
from scripts.respaldar import respaldar  # noqa: E402


def main():
    if not bd.existe_base():
        print('Aún no existe la base de datos. Ejecute primero:  python scripts/crear_datos.py --vacia')
        sys.exit(1)
    copia = respaldar('antes_de_funcionarios')
    print(f'Copia de seguridad: {copia.relative_to(configuracion.RAIZ)}')

    resumen = claves.resumir_password(CLAVE_FUNCIONARIOS)
    with bd.transaccion():
        for nombre, correo, dependencia in FUNCIONARIOS:
            dep = bd.uno('SELECT id_dependencia FROM dependencia WHERE nombre = ?', (dependencia,))
            if not dep:
                print(f'  Se omitió {correo}: no existe la dependencia "{dependencia}".')
                continue
            existente = bd.uno('SELECT id_usuario, rol FROM usuario WHERE correo = ?', (correo,))
            if existente and existente['rol'] != 'FUNCIONARIO':
                print(f'  Se omitió {correo}: ese correo ya lo usa una cuenta con rol {existente["rol"]}.')
            elif existente:
                bd.ejecutar("""UPDATE usuario SET password_hash = ?, activo = 1, intentos_fallidos = 0, bloqueado_hasta = NULL,
                                      debe_cambiar_password = 0, id_dependencia = ? WHERE id_usuario = ?""",
                            (resumen, dep['id_dependencia'], existente['id_usuario']))
                print(f'  Actualizado: {correo} ({dependencia})')
            else:
                bd.insertar("""INSERT INTO usuario (nombre, correo, password_hash, rol, id_dependencia, fecha_creacion)
                               VALUES (?, ?, ?, 'FUNCIONARIO', ?, ?)""",
                            (nombre, correo, resumen, dep['id_dependencia'], tiempo.ahora()))
                print(f'  Creado:      {correo} ({dependencia})')
    bd.cerrar()
    print(f'\nListo. Contraseña de los funcionarios de prueba: {CLAVE_FUNCIONARIOS}')
    print('Ingrese en http://localhost:8000/login.html con el correo (no con cédula).')


if __name__ == '__main__':
    main()
