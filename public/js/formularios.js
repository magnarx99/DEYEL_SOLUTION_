// Validación en el navegador (respuesta inmediata) y bloques de formulario reutilizables.
// El servidor vuelve a validar todo: esta capa es para ayudar al usuario, no para confiar en ella.
import { $$, esc, icono, llenarSelect, catalogos } from './api.js';

export const CEDULA_REGEX = /^[0-9]{6,10}$/;
const TELEFONO_REGEX = /^[0-9]{7,15}$/;
const CORREO_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const PASSWORD_REGEX = /^(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,72}$/;
const hoy = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date());

/** Reglas por nombre de campo: devuelven el mensaje de error o '' si es válido. */
const REGLAS = {
  tipo_documento: (v) => (v ? '' : 'Seleccione el tipo de documento.'),
  cedula: (v) => (CEDULA_REGEX.test(v) ? '' : 'El documento debe tener de 6 a 10 dígitos, sin puntos ni espacios.'),
  fecha_expedicion: (v) => (!v ? 'Indique la fecha de expedición.' : v > hoy() ? 'La fecha no puede ser futura.' : ''),
  nombres: (v) => (v.trim().length >= 2 ? '' : 'Escriba sus nombres.'),
  apellidos: (v) => (v.trim().length >= 2 ? '' : 'Escriba sus apellidos.'),
  fecha_nacimiento: (v) => (v && v > hoy() ? 'La fecha no puede ser futura.' : ''),
  municipio: (v) => (v ? '' : 'Seleccione su municipio.'),
  telefono: (v) => (TELEFONO_REGEX.test(v) ? '' : 'Escriba un celular válido, solo números (ej. 3001234567).'),
  telefono_fijo: (v) => (!v || TELEFONO_REGEX.test(v) ? '' : 'Teléfono no válido.'),
  correo: (v, el) => {
    if (!v) return el.required ? 'Escriba su correo electrónico.' : '';
    return CORREO_REGEX.test(v) ? '' : 'Escriba un correo válido, por ejemplo nombre@correo.com.';
  },
  password: (v) => (PASSWORD_REGEX.test(v) ? '' : 'Mínimo 8 caracteres, con una mayúscula, un número y un símbolo.'),
  confirmar_password: (v, el) => (v && v === el.form?.elements.password?.value ? '' : 'Las contraseñas no coinciden.'),
  acepta_tratamiento_datos: (_v, el) => (el.checked ? '' : 'Debe autorizar el tratamiento de sus datos para continuar.'),
  tipo: (v) => (v ? '' : 'Seleccione el tipo de solicitud.'),
  municipio_hecho: (v) => (v ? '' : 'Seleccione el municipio donde ocurrió el hecho.'),
  asunto: (v) => (v.trim().length >= 5 ? '' : 'Escriba un asunto de al menos 5 caracteres.'),
  descripcion: (v) => (v.trim().length >= 20 ? '' : 'Describa su caso con al menos 20 caracteres.'),
  medio_respuesta: (_v, el) => (el.form && [...el.form.elements.medio_respuesta].some((r) => r.checked) ? '' : 'Elija cómo quiere recibir la respuesta.'),
  fecha_cita_preferida: (v) => (!v ? 'Elija una fecha.' : v <= hoy() ? 'Elija una fecha a partir de mañana.' : ''),
  modalidad_cita: (_v, el) => (el.form && [...el.form.elements.modalidad_cita].some((r) => r.checked) ? '' : 'Elija la modalidad.'),
};

/** Valida un campo y muestra su mensaje. */
export function validarCampo(el) {
  const regla = REGLAS[el.name];
  if (!regla || el.disabled || el.closest('[hidden]')) return true;
  const mensaje = regla(el.type === 'checkbox' ? el.checked : (el.value || ''), el);
  const caja = el.closest('.campo');
  if (caja) {
    caja.classList.toggle('con-error', Boolean(mensaje));
    const err = caja.querySelector('.error-campo');
    if (err && mensaje) err.textContent = mensaje;
  }
  if (mensaje) el.setAttribute('aria-invalid', 'true');
  else el.removeAttribute('aria-invalid');
  return !mensaje;
}

/** Valida todos los campos de un contenedor. Enfoca el primero con error. */
export function validarGrupo(contenedor) {
  const vistos = new Set();
  let primero = null;
  for (const el of $$('input, select, textarea', contenedor)) {
    if (!el.name || (el.type === 'radio' && vistos.has(el.name))) continue;
    vistos.add(el.name);
    if (!validarCampo(el)) primero ??= el;
  }
  primero?.focus();
  return !primero;
}

/** Validación en tiempo real: al salir del campo y al corregirlo. */
export function validacionEnVivo(formulario) {
  formulario.addEventListener('focusout', (e) => {
    if (e.target.name && e.target.value) validarCampo(e.target);
  });
  formulario.addEventListener('input', (e) => {
    if (e.target.closest('.con-error')) validarCampo(e.target);
  });
  formulario.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox' || e.target.type === 'radio' || e.target.tagName === 'SELECT') validarCampo(e.target);
  });
}

/** Solo permite dígitos (cédula, teléfonos). */
export function soloDigitos(input) {
  input.addEventListener('input', () => {
    const limpio = input.value.replace(/\D/g, '');
    if (limpio !== input.value) input.value = limpio;
  });
}

/** Contador de caracteres para campos con límite. */
export function contador(campo, salida) {
  const max = Number(campo.maxLength);
  const actualizar = () => {
    salida.textContent = `${campo.value.length.toLocaleString('es-CO')} / ${max.toLocaleString('es-CO')}`;
    salida.classList.toggle('limite', campo.value.length > max * 0.9);
  };
  campo.addEventListener('input', actualizar);
  actualizar();
}

/** Indicador visual de fortaleza de la contraseña. */
export function medidorFortaleza(input, barra, texto) {
  input.addEventListener('input', () => {
    const v = input.value;
    let p = 0;
    if (v.length >= 8) p += 1;
    if (v.length >= 12) p += 1;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) p += 1;
    if (/[0-9]/.test(v)) p += 1;
    if (/[^A-Za-z0-9]/.test(v)) p += 1;
    const niveles = [['Muy débil', '#B23A48'], ['Débil', '#B23A48'], ['Aceptable', '#B7791F'], ['Buena', '#1E5AA8'], ['Fuerte', '#2E7D5B'], ['Muy fuerte', '#2E7D5B']];
    const [etiqueta, color] = niveles[p];
    barra.style.width = `${(p / 5) * 100}%`;
    barra.style.backgroundColor = color;
    texto.textContent = v ? `Seguridad de la contraseña: ${etiqueta}` : '';
  });
}

/** Botones "mostrar/ocultar contraseña". */
export function alternarPassword(raiz = document) {
  for (const b of $$('[data-ver-password]', raiz)) {
    b.addEventListener('click', () => {
      const input = b.previousElementSibling;
      const ver = input.type === 'password';
      input.type = ver ? 'text' : 'password';
      b.innerHTML = icono(ver ? 'eye-off' : 'eye');
      b.setAttribute('aria-label', ver ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  }
}

// ---------------------------------------------------------------------
// Bloques de datos personales (registro, primera radicación y "Mi cuenta")
// ---------------------------------------------------------------------
const campo = (nombre, etiqueta, control, { obligatorio = false, ayuda = '', clase = '' } = {}) => `
  <div class="campo ${clase}">
    <label for="f-${nombre}">${esc(etiqueta)}${obligatorio ? '<span class="obligatorio" aria-hidden="true">*</span>' : ''}</label>
    ${control}
    ${ayuda ? `<span class="ayuda" id="ay-${nombre}">${ayuda}</span>` : ''}
    <span class="error-campo" id="er-${nombre}" aria-live="polite"></span>
  </div>`;

const entradaTexto = (nombre, { tipo = 'text', obligatorio = false, max, extra = '' } = {}) =>
  `<input id="f-${nombre}" name="${nombre}" type="${tipo}" ${obligatorio ? 'required aria-required="true"' : ''} ${max ? `maxlength="${max}"` : ''} aria-describedby="er-${nombre}" ${extra}>`;

export const bloqueIdentificacion = ({ cedulaFija = false, sinCedula = false } = {}) => sinCedula ? `
  <div class="rejilla">
    ${campo('tipo_documento', 'Tipo de documento', `
      <select id="f-tipo_documento" name="tipo_documento" required aria-required="true">
        <option value="CC">Cédula de ciudadanía</option>
        <option value="CE">Cédula de extranjería</option>
        <option value="TI">Tarjeta de identidad</option>
        <option value="PA">Pasaporte</option>
      </select>`, { obligatorio: true })}
    ${campo('fecha_expedicion', 'Fecha de expedición del documento', entradaTexto('fecha_expedicion', { tipo: 'date', obligatorio: true, extra: `max="${hoy()}"` }), { obligatorio: true, ayuda: 'La usaremos para confirmar su identidad en próximas solicitudes.' })}
  </div>` : `
  <div class="rejilla rejilla-3">
    ${campo('tipo_documento', 'Tipo de documento', `
      <select id="f-tipo_documento" name="tipo_documento" required aria-required="true">
        <option value="CC">Cédula de ciudadanía</option>
        <option value="CE">Cédula de extranjería</option>
        <option value="TI">Tarjeta de identidad</option>
        <option value="PA">Pasaporte</option>
      </select>`, { obligatorio: true })}
    ${campo('cedula', 'Número de documento', entradaTexto('cedula', { obligatorio: true, max: 10, extra: `inputmode="numeric" autocomplete="off" ${cedulaFija ? 'readonly' : ''}` }), { obligatorio: true, ayuda: 'Solo números, sin puntos.' })}
    ${campo('fecha_expedicion', 'Fecha de expedición', entradaTexto('fecha_expedicion', { tipo: 'date', obligatorio: true, extra: `max="${hoy()}"` }), { obligatorio: true, ayuda: 'Aparece en su documento. La usamos para confirmar su identidad.' })}
  </div>`;

export const bloquePersonal = () => `
  <div class="rejilla">
    ${campo('nombres', 'Nombres', entradaTexto('nombres', { obligatorio: true, max: 80, extra: 'autocomplete="given-name"' }), { obligatorio: true })}
    ${campo('apellidos', 'Apellidos', entradaTexto('apellidos', { obligatorio: true, max: 80, extra: 'autocomplete="family-name"' }), { obligatorio: true })}
    ${campo('fecha_nacimiento', 'Fecha de nacimiento', entradaTexto('fecha_nacimiento', { tipo: 'date', extra: `max="${hoy()}" autocomplete="bday"` }))}
    ${campo('sexo', 'Sexo', `
      <select id="f-sexo" name="sexo">
        <option value="">Prefiero no indicarlo</option>
        <option value="FEMENINO">Femenino</option>
        <option value="MASCULINO">Masculino</option>
        <option value="INTERSEXUAL">Intersexual</option>
        <option value="NO_INFORMA">No informa</option>
      </select>`)}
    ${campo('grupo_poblacional', 'Grupo poblacional o condición especial', `
      <select id="f-grupo_poblacional" name="grupo_poblacional">
        <option value="">Ninguno / prefiero no indicarlo</option>
        <option value="PERSONA_CON_DISCAPACIDAD">Persona con discapacidad</option>
        <option value="VICTIMA_CONFLICTO">Víctima del conflicto armado</option>
        <option value="ADULTO_MAYOR">Adulto mayor</option>
        <option value="INDIGENA">Comunidad indígena</option>
        <option value="AFRODESCENDIENTE">Comunidad afrodescendiente</option>
        <option value="ROM">Pueblo Rom</option>
        <option value="MIGRANTE">Población migrante</option>
        <option value="LGBTIQ">Población LGBTIQ+</option>
      </select>`, { clase: 'ocupa-todo', ayuda: 'Opcional. Nos ayuda a darle atención prioritaria cuando la ley lo indica.' })}
  </div>`;

export const bloqueContacto = ({ correoObligatorio = false } = {}) => `
  <div class="rejilla">
    ${campo('municipio', 'Municipio de residencia', '<select id="f-municipio" name="municipio" required aria-required="true"></select>', { obligatorio: true })}
    ${campo('barrio', 'Barrio o vereda', entradaTexto('barrio', { max: 80 }))}
    ${campo('direccion', 'Dirección', entradaTexto('direccion', { max: 120, extra: 'autocomplete="street-address"' }), { clase: 'ocupa-todo', ayuda: 'Necesaria si quiere recibir respuestas por correo físico.' })}
    ${campo('telefono', 'Celular', entradaTexto('telefono', { tipo: 'tel', obligatorio: true, max: 15, extra: 'inputmode="numeric" autocomplete="tel"' }), { obligatorio: true })}
    ${campo('telefono_fijo', 'Teléfono fijo', entradaTexto('telefono_fijo', { tipo: 'tel', max: 15, extra: 'inputmode="numeric"' }))}
    ${campo('correo', 'Correo electrónico', entradaTexto('correo', { tipo: 'email', obligatorio: correoObligatorio, max: 120, extra: 'autocomplete="email"' }), { obligatorio: correoObligatorio, clase: 'ocupa-todo', ayuda: correoObligatorio ? 'Será su usuario para iniciar sesión.' : 'Recomendado: le enviaremos la respuesta a este correo.' })}
  </div>`;

export const bloqueAutorizacion = () => `
  <div class="campo">
    <label class="casilla" for="f-acepta_tratamiento_datos">
      <input type="checkbox" id="f-acepta_tratamiento_datos" name="acepta_tratamiento_datos" required aria-required="true">
      <span>Autorizo a la Gobernación de Antioquia a tratar mis datos personales para gestionar mis solicitudes, conforme a la Ley 1581 de 2012 y la <a href="/politica-datos.html" target="_blank" rel="noopener">política de tratamiento de datos</a>.<span class="obligatorio" aria-hidden="true">*</span></span>
    </label>
    <span class="error-campo" aria-live="polite"></span>
  </div>
  <div class="campo" style="margin-top:16px">
    <span class="etiqueta" id="et-notif">¿Cómo prefiere recibir avisos sobre sus solicitudes?</span>
    <div class="opciones" role="radiogroup" aria-labelledby="et-notif">
      <label class="opcion"><input type="radio" name="notificacion_preferida" value="CORREO" checked> Correo electrónico</label>
      <label class="opcion"><input type="radio" name="notificacion_preferida" value="SMS"> Mensaje de texto (SMS)</label>
    </div>
  </div>`;

/** Llena las listas de municipios de un contenedor. */
export async function cargarMunicipios(raiz) {
  const { municipios } = await catalogos();
  for (const s of $$('select[name="municipio"], select[name="municipio_hecho"]', raiz)) {
    llenarSelect(s, municipios, { vacio: 'Seleccione el municipio' });
  }
}

/** Lee los datos personales de un formulario como objeto. */
export function leerCiudadano(formulario) {
  const f = new FormData(formulario);
  const campos = ['tipo_documento', 'cedula', 'fecha_expedicion', 'nombres', 'apellidos', 'fecha_nacimiento', 'sexo',
    'grupo_poblacional', 'municipio', 'barrio', 'direccion', 'telefono', 'telefono_fijo', 'correo', 'notificacion_preferida'];
  const datos = Object.fromEntries(campos.filter((c) => f.has(c)).map((c) => [c, String(f.get(c) || '').trim()]));
  datos.acepta_tratamiento_datos = formulario.elements.acepta_tratamiento_datos?.checked ?? false;
  return datos;
}

/** Rellena un formulario con los datos de un ciudadano. */
export function rellenar(formulario, datos) {
  for (const [k, v] of Object.entries(datos || {})) {
    const el = formulario.elements[k];
    if (!el || v === null || v === undefined) continue;
    if (el instanceof RadioNodeList) [...el].forEach((r) => { r.checked = r.value === v; });
    else if (el.type === 'checkbox') el.checked = Boolean(v);
    else el.value = v;
  }
}
