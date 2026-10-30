-- =====================================================================
--  Portal PQRDS – Gobernación de Antioquia
--  Esquema de la base de datos SQLite (incluida en Python, no se instala nada).
--  Principio de una sola vez: los datos del ciudadano se guardan una única
--  vez (cédula UNIQUE) y cada PQRDS se relaciona con él (1 a N).
--  Fechas: 'AAAA-MM-DD'. Fecha y hora: 'AAAA-MM-DDTHH:MM:SS-05:00' (hora de Colombia).
--  Verdadero/falso: 1 / 0.
-- =====================================================================

DROP TABLE IF EXISTS auditoria;
DROP TABLE IF EXISTS faq_chatbot;
DROP TABLE IF EXISTS festivo;
DROP TABLE IF EXISTS pqrds_historial;
DROP TABLE IF EXISTS pqrds_adjunto;
DROP TABLE IF EXISTS pqrds;
DROP TABLE IF EXISTS consecutivo_radicado;
DROP TABLE IF EXISTS ciudadano_correccion;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS ciudadano;
DROP TABLE IF EXISTS tipo_solicitud;
DROP TABLE IF EXISTS dependencia;
DROP TABLE IF EXISTS municipio;

-- ---------------------------------------------------------------------
-- Catálogos
-- ---------------------------------------------------------------------
CREATE TABLE municipio (
  id_municipio INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE dependencia (
  id_dependencia  INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre          TEXT NOT NULL UNIQUE,
  correo_contacto TEXT
);

CREATE TABLE tipo_solicitud (
  id_tipo                INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo                 TEXT    NOT NULL UNIQUE,
  nombre                 TEXT    NOT NULL,
  descripcion            TEXT    NOT NULL,
  ejemplo                TEXT    NOT NULL,
  texto_boton            TEXT    NOT NULL,
  icono                  TEXT    NOT NULL,
  dias_habiles_respuesta INTEGER NOT NULL CHECK (dias_habiles_respuesta > 0),
  permite_anonimo        INTEGER NOT NULL DEFAULT 0 CHECK (permite_anonimo IN (0, 1)),
  orden                  INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------
-- Ciudadano: captura única de datos personales
-- ---------------------------------------------------------------------
CREATE TABLE ciudadano (
  id_ciudadano             INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo_documento           TEXT NOT NULL DEFAULT 'CC' CHECK (tipo_documento IN ('CC','CE','TI','PA')),
  -- Solo dígitos, de 6 a 10 caracteres
  cedula                   TEXT NOT NULL UNIQUE
                           CHECK (length(cedula) BETWEEN 6 AND 10 AND cedula NOT GLOB '*[^0-9]*'),
  fecha_expedicion         TEXT NOT NULL,
  nombres                  TEXT NOT NULL,
  apellidos                TEXT NOT NULL,
  fecha_nacimiento         TEXT,
  sexo                     TEXT CHECK (sexo IN ('FEMENINO','MASCULINO','INTERSEXUAL','NO_INFORMA')),
  grupo_poblacional        TEXT,
  municipio                TEXT NOT NULL REFERENCES municipio(nombre),
  barrio                   TEXT,
  direccion                TEXT,
  telefono                 TEXT NOT NULL CHECK (length(telefono) BETWEEN 7 AND 15 AND telefono NOT GLOB '*[^0-9]*'),
  telefono_fijo            TEXT,
  correo                   TEXT,
  notificacion_preferida   TEXT NOT NULL DEFAULT 'CORREO' CHECK (notificacion_preferida IN ('CORREO','SMS')),
  acepta_tratamiento_datos INTEGER NOT NULL CHECK (acepta_tratamiento_datos = 1),
  fecha_creacion           TEXT NOT NULL,
  fecha_actualizacion      TEXT NOT NULL
);

-- Historial de correcciones del documento (número, tipo o fecha de expedición).
-- Guarda el valor anterior y el nuevo para poder revisar o revertir un cambio.
CREATE TABLE ciudadano_correccion (
  id_correccion       INTEGER PRIMARY KEY AUTOINCREMENT,
  id_ciudadano        INTEGER NOT NULL REFERENCES ciudadano(id_ciudadano) ON DELETE CASCADE,
  tipo_anterior       TEXT NOT NULL,
  cedula_anterior     TEXT NOT NULL,
  expedicion_anterior TEXT NOT NULL,
  tipo_nuevo          TEXT NOT NULL,
  cedula_nueva        TEXT NOT NULL,
  expedicion_nueva    TEXT NOT NULL,
  motivo              TEXT NOT NULL,
  ip                  TEXT,
  fecha               TEXT NOT NULL
);
CREATE INDEX idx_correccion_ciudadano ON ciudadano_correccion(id_ciudadano, fecha);

-- ---------------------------------------------------------------------
-- Usuarios del sistema (ciudadanos con cuenta, funcionarios y administradores)
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
  id_usuario            INTEGER PRIMARY KEY AUTOINCREMENT,
  id_ciudadano          INTEGER UNIQUE REFERENCES ciudadano(id_ciudadano),
  nombre                TEXT    NOT NULL,
  correo                TEXT    NOT NULL UNIQUE,
  password_hash         TEXT    NOT NULL,
  rol                   TEXT    NOT NULL CHECK (rol IN ('CIUDADANO','FUNCIONARIO','ADMIN')),
  id_dependencia        INTEGER REFERENCES dependencia(id_dependencia),
  activo                INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
  intentos_fallidos     INTEGER NOT NULL DEFAULT 0,
  bloqueado_hasta       TEXT,
  debe_cambiar_password INTEGER NOT NULL DEFAULT 0 CHECK (debe_cambiar_password IN (0, 1)),
  reset_token_hash      TEXT,
  reset_expira          TEXT,
  fecha_creacion        TEXT    NOT NULL,
  -- Un usuario con rol Ciudadano siempre está vinculado a su ficha de ciudadano
  CHECK (rol <> 'CIUDADANO' OR id_ciudadano IS NOT NULL)
);

-- ---------------------------------------------------------------------
-- PQRDS
-- ---------------------------------------------------------------------
-- Consecutivo por año para el radicado PQRDS-AAAA-000001
CREATE TABLE consecutivo_radicado (
  anio   INTEGER PRIMARY KEY,
  ultimo INTEGER NOT NULL
);

CREATE TABLE pqrds (
  id_pqrds                INTEGER PRIMARY KEY AUTOINCREMENT,
  radicado                TEXT    NOT NULL UNIQUE,
  id_ciudadano            INTEGER REFERENCES ciudadano(id_ciudadano),      -- NULL solo en denuncias anónimas
  id_tipo                 INTEGER NOT NULL REFERENCES tipo_solicitud(id_tipo),
  id_dependencia          INTEGER REFERENCES dependencia(id_dependencia),  -- NULL = la entidad la asigna
  id_funcionario_asignado INTEGER REFERENCES usuario(id_usuario),
  id_usuario_radicador    INTEGER REFERENCES usuario(id_usuario),
  canal                   TEXT    NOT NULL DEFAULT 'WEB' CHECK (canal IN ('WEB','PRESENCIAL','TELEFONICO')),
  municipio_hecho         TEXT    NOT NULL REFERENCES municipio(nombre),
  asunto                  TEXT    NOT NULL CHECK (length(asunto) <= 150),
  descripcion             TEXT    NOT NULL CHECK (length(descripcion) <= 3000),
  medio_respuesta         TEXT    NOT NULL DEFAULT 'CORREO' CHECK (medio_respuesta IN ('CORREO','FISICO','NINGUNO')),
  fecha_cita_preferida    TEXT,
  modalidad_cita          TEXT    CHECK (modalidad_cita IN ('PRESENCIAL','VIRTUAL')),
  estado                  TEXT    NOT NULL DEFAULT 'RADICADA'
                          CHECK (estado IN ('RADICADA','EN_TRAMITE','RESPONDIDA','CERRADA','TRASLADADA')),
  es_anonima              INTEGER NOT NULL DEFAULT 0 CHECK (es_anonima IN (0, 1)),
  codigo_anonimo          TEXT,
  fecha_radicacion        TEXT    NOT NULL,
  fecha_limite            TEXT    NOT NULL,
  fecha_respuesta         TEXT,
  respuesta               TEXT,
  CHECK (es_anonima = 1 OR id_ciudadano IS NOT NULL),
  CHECK (es_anonima = 0 OR codigo_anonimo IS NOT NULL)
);

CREATE INDEX idx_pqrds_ciudadano ON pqrds(id_ciudadano, fecha_radicacion DESC);
CREATE INDEX idx_pqrds_estado    ON pqrds(estado);
CREATE INDEX idx_pqrds_limite    ON pqrds(fecha_limite);
CREATE INDEX idx_pqrds_dep       ON pqrds(id_dependencia);

CREATE TABLE pqrds_adjunto (
  id_adjunto      INTEGER PRIMARY KEY AUTOINCREMENT,
  id_pqrds        INTEGER NOT NULL REFERENCES pqrds(id_pqrds) ON DELETE CASCADE,
  nombre_original TEXT    NOT NULL,
  ruta            TEXT    NOT NULL,
  tipo_mime       TEXT    NOT NULL,
  tamano          INTEGER NOT NULL
);

CREATE TABLE pqrds_historial (
  id_historial    INTEGER PRIMARY KEY AUTOINCREMENT,
  id_pqrds        INTEGER NOT NULL REFERENCES pqrds(id_pqrds) ON DELETE CASCADE,
  estado_anterior TEXT,
  estado_nuevo    TEXT NOT NULL,
  id_usuario      INTEGER REFERENCES usuario(id_usuario),
  comentario      TEXT,
  fecha           TEXT NOT NULL
);
CREATE INDEX idx_historial_pqrds ON pqrds_historial(id_pqrds, fecha);

-- ---------------------------------------------------------------------
-- Apoyo
-- ---------------------------------------------------------------------
CREATE TABLE festivo (
  fecha       TEXT PRIMARY KEY,
  descripcion TEXT NOT NULL
);

CREATE TABLE faq_chatbot (
  id_faq         INTEGER PRIMARY KEY AUTOINCREMENT,
  palabras_clave TEXT    NOT NULL,   -- separadas por coma, sin tildes
  pregunta       TEXT    NOT NULL,
  respuesta      TEXT    NOT NULL,
  accion_texto   TEXT,               -- botón opcional que guía al usuario
  accion_url     TEXT,
  activo         INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE auditoria (
  id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
  id_usuario   INTEGER REFERENCES usuario(id_usuario),
  accion       TEXT NOT NULL,
  detalle      TEXT,
  ip           TEXT,
  fecha        TEXT NOT NULL
);
CREATE INDEX idx_auditoria_fecha ON auditoria(fecha DESC);
