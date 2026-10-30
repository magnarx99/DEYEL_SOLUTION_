# Portal PQRDS – Gobernación de Antioquia (versión Python, sin librerías)

Prototipo académico basado en el proyecto PPI **Deyel-Solution**. El ciudadano registra sus datos **una sola vez**;
en las siguientes solicitudes el portal lo reconoce por su cédula y solo pide el nuevo caso.

Está hecho **solo con Python y su biblioteca estándar**: no hay que instalar nada con `pip`, ni Node, ni PostgreSQL.

| Parte | Cómo se hizo |
|---|---|
| Servidor web | `http.server` (ThreadingHTTPServer) |
| Base de datos | `sqlite3` – archivo `database/pqrds.db` |
| Contraseñas | `hashlib.pbkdf2_hmac` (PBKDF2-SHA256, 240 000 iteraciones) |
| Sesiones | Ficha JWT firmada con `hmac` en una cookie httpOnly |
| Exportar a Excel | `zipfile` + XML (archivo `.xlsx` real) |
| Páginas | HTML, CSS y JavaScript sin librerías (gráficos hechos con CSS) |

## Requisitos
- Python **3.10 o superior** (en Windows marque *Add python.exe to PATH* al instalar).
- Visual Studio Code con la extensión **Python** (opcional, recomendado).

## Cómo encenderlo
```bash
python scripts/crear_datos.py     # 1. crea la base de datos con datos de ejemplo (solo la primera vez)
python servidor.py                # 2. enciende el portal
```
Abra **http://localhost:8000**. Para apagarlo pulse `Ctrl + C` en la terminal.
En macOS/Linux use `python3` en lugar de `python`.

## Usuarios de prueba
| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | admin@antioquia.example | Admin2026* (pide cambiarla al entrar) |
| Funcionario | funcionario.ciudadania@antioquia.example | Funcionario2026* |
| Ciudadano | 1017234567 (cédula) | Ciudadano2026* |

Los funcionarios y la ciudadana de prueba **solo existen si la base se creó con datos de prueba**
(`python scripts/crear_datos.py`). Una base creada con `--vacia` solo trae el administrador.
Para agregar los funcionarios de prueba a una base que ya tiene datos, **sin borrar nada**:
```bash
python scripts/crear_funcionarios.py
```
El funcionario entra con su **correo** (no con cédula). También puede crear funcionarios desde el panel del
administrador: *Usuarios > Nuevo usuario*.

## Reglas de la cuenta del ciudadano
- **Citas:** la entidad tiene hasta 5 días hábiles para responder, así que la cita solo se puede pedir para un
  día hábil (lunes a viernes, sin festivos) **después** de ese plazo.
- **Corregir el documento** (*Mi cuenta > Corregir*): permite cambiar el tipo, el número y la fecha de expedición si se
  digitaron mal. Pide la contraseña, el número dos veces y el motivo; máximo 2 correcciones al año; no deja tomar un
  número que ya es de otra persona; guarda el valor anterior (tabla `ciudadano_correccion`) y queda en la auditoría.
- **Eliminar la cuenta** (*Mi cuenta > Eliminar mi cuenta*): pide la contraseña y escribir ELIMINAR. Borra el usuario;
  si la persona no tiene solicitudes también borra sus datos. Si tiene solicitudes, estas se conservan (la entidad
  debe responderlas y archivarlas) y se pueden seguir consultando con el radicado y la cédula.
- Cinco contraseñas erradas seguidas (al iniciar sesión, corregir el documento o eliminar la cuenta) bloquean la cuenta 15 minutos.

Al encender el portal se aplica `database/migraciones.sql`, que agrega a una base antigua lo nuevo **sin borrar datos**.

## Empezar a cargar datos reales
```bash
python scripts/crear_datos.py --vacia   # base limpia: solo catálogos y el administrador (una sola vez)
python servidor.py
```
Todo lo que se registre en el portal (ciudadanos, PQRDS, usuarios, respuestas) queda guardado en
`database/pqrds.db` al instante y se conserva aunque apague el portal o el computador.

- **No vuelva a ejecutar `crear_datos.py`** cuando tenga datos reales: borra todo (pide escribir BORRAR y antes guarda una copia).
- Haga copias de seguridad con `python scripts/respaldar.py` (quedan en `database/respaldos/`).
- Para restaurar una copia: apague el portal, copie el archivo de `database/respaldos/` a `database/` y renómbrelo `pqrds.db`.

## Pruebas automáticas
Con el portal encendido, en otra terminal: `python scripts/pruebas.py` (25 casos).
Las pruebas necesitan la base **con datos de prueba** (`python scripts/crear_datos.py`). No las ejecute sobre su base de datos real: crean solicitudes ficticias.

## Estructura
```
servidor.py          Punto de entrada: recibe peticiones y sirve las páginas
configuracion.py     Lee .env (lo crea solo la primera vez)
rutas.py             Todas las direcciones /api/...
nucleo/              Piezas base: base de datos, web, claves, sesión, adjuntos, tiempo
servicios/           Reglas del negocio: ciudadanos, PQRDS, fechas, Excel, chatbot, usuarios...
utilidades/          Validaciones, radicado, enmascarar datos, errores
database/            schema.sql, datos_iniciales.sql y pqrds.db (se genera)
scripts/             crear_datos.py, respaldar.py y pruebas.py
public/              Páginas HTML, estilos CSS, JavaScript e imágenes
uploads/             Archivos adjuntos que suben los ciudadanos
```
