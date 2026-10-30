-- =====================================================================
--  Actualizaciones para bases de datos creadas con versiones anteriores.
--  Se ejecuta sola cada vez que se enciende el portal y NO borra nada:
--  cada instrucción solo actúa si el cambio todavía no existe.
-- =====================================================================

-- Historial de correcciones del documento (igual que en schema.sql)
CREATE TABLE IF NOT EXISTS ciudadano_correccion (
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
CREATE INDEX IF NOT EXISTS idx_correccion_ciudadano ON ciudadano_correccion(id_ciudadano, fecha);

-- Respuesta sobre citas: explica el plazo mínimo (solo si nadie la ha editado desde el panel)
UPDATE faq_chatbot
   SET respuesta = 'Elija "Agenda tu cita", identifíquese con su cédula, indique el trámite, la fecha preferida y si la prefiere presencial o virtual. Como la entidad tiene hasta 5 días hábiles para responder, la cita solo puede ser en un día hábil después de ese plazo. La dependencia le confirmará la fecha y la hora.'
 WHERE respuesta = 'Elija "Agenda tu cita", identifíquese con su cédula, indique el trámite, la fecha preferida y si la prefiere presencial o virtual. La dependencia le confirmará la cita.';

-- Nuevas preguntas frecuentes del asistente
INSERT INTO faq_chatbot (palabras_clave, pregunta, respuesta, accion_texto, accion_url)
SELECT 'eliminar cuenta,borrar cuenta,cerrar cuenta,darme de baja,desvincular,desvincularme',
       '¿Cómo elimino mi cuenta?',
       'Ingrese a "Mi cuenta" y, al final de la página, use "Eliminar mi cuenta". Le pediremos su contraseña para confirmar. Sus solicitudes ya radicadas se conservan porque la entidad debe responderlas y archivarlas por ley; podrá seguir consultándolas con el radicado y su cédula.',
       'Ir a Mi cuenta', '/mi-cuenta.html'
 WHERE NOT EXISTS (SELECT 1 FROM faq_chatbot WHERE pregunta = '¿Cómo elimino mi cuenta?');

INSERT INTO faq_chatbot (palabras_clave, pregunta, respuesta, accion_texto, accion_url)
SELECT 'corregir cedula,error cedula,fecha de expedicion,me equivoque,documento mal,cambiar cedula,corregir documento',
       'Me equivoqué al escribir mi cédula o la fecha de expedición',
       'Ingrese a "Mi cuenta" y use "Corregir datos del documento". Por seguridad le pediremos su contraseña, que escriba el número dos veces y el motivo. Puede hacer hasta 2 correcciones al año; si necesita más, radique una solicitud de datos personales con copia de su documento.',
       'Ir a Mi cuenta', '/mi-cuenta.html'
 WHERE NOT EXISTS (SELECT 1 FROM faq_chatbot WHERE pregunta = 'Me equivoqué al escribir mi cédula o la fecha de expedición');
