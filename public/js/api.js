// Utilidades compartidas del frontend: llamadas a la API, formato, íconos y mensajes.

/** Llama a la API y devuelve el JSON. Lanza un Error con .status y .detalles si falla. */
export async function api(url, { method = 'GET', body, form } = {}) {
  const opciones = { method, headers: {}, credentials: 'same-origin' };
  if (form) opciones.body = form; // FormData (adjuntos): el navegador pone el Content-Type
  else if (body !== undefined) {
    opciones.headers['Content-Type'] = 'application/json';
    opciones.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(url, opciones);
  } catch {
    throw Object.assign(new Error('No hay conexión con el servidor. Revise su internet e intente de nuevo.'), { status: 0 });
  }
  const datos = resp.headers.get('content-type')?.includes('application/json') ? await resp.json() : null;
  if (!resp.ok) {
    const err = new Error(datos?.error || 'No fue posible completar la operación.');
    err.status = resp.status;
    err.detalles = datos?.detalles;
    err.datos = datos;
    throw err;
  }
  return datos;
}

/** Escapa texto para insertarlo de forma segura en HTML. */
export function esc(valor) {
  return String(valor ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** Ícono del sprite local (Lucide). */
export function icono(nombre, clase = 'icono') {
  return `<svg class="${clase}" aria-hidden="true" focusable="false"><use href="/img/iconos.svg#i-${nombre}"></use></svg>`;
}

export const $ = (sel, raiz = document) => raiz.querySelector(sel);
export const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

// ----- Formato -----
const formatoFecha = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'America/Bogota' });
const formatoFechaHora = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Bogota' });

/** Fecha corta. Acepta 'AAAA-MM-DD' o marca de tiempo ISO. */
export function fecha(v) {
  if (!v) return '—';
  const d = /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T12:00:00-05:00`) : new Date(v);
  return formatoFecha.format(d);
}
export const fechaHora = (v) => (v ? formatoFechaHora.format(new Date(v)) : '—');

export const ETIQUETA_ESTADO = {
  RADICADA: 'Radicada', EN_TRAMITE: 'En trámite', RESPONDIDA: 'Respondida', CERRADA: 'Cerrada', TRASLADADA: 'Trasladada',
};
export const ETIQUETA_SEMAFORO = { VENCIDA: 'Vencida', POR_VENCER: 'Por vencer', A_TIEMPO: 'A tiempo', ATENDIDA: 'Atendida' };
export const estadoHtml = (e) => `<span class="estado estado-${esc(e)}">${esc(ETIQUETA_ESTADO[e] || e)}</span>`;
export const semaforoHtml = (s) => `<span class="semaforo semaforo-${esc(s)}">${esc(ETIQUETA_SEMAFORO[s] || '')}</span>`;
export const tamano = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

// ----- Datos compartidos (se piden una sola vez por página) -----
let promesaSesion;
export function sesion(refrescar = false) {
  if (!promesaSesion || refrescar) promesaSesion = api('/api/auth/yo').catch(() => ({ autenticado: false }));
  return promesaSesion;
}
let promesaCatalogos;
export function catalogos() {
  if (!promesaCatalogos) promesaCatalogos = api('/api/catalogos');
  return promesaCatalogos;
}

/** Llena un <select> con opciones. */
export function llenarSelect(select, opciones, { vacio = 'Seleccione…', valor = (o) => o, texto = (o) => o } = {}) {
  select.innerHTML = (vacio !== null ? `<option value="">${esc(vacio)}</option>` : '')
    + opciones.map((o) => `<option value="${esc(valor(o))}">${esc(texto(o))}</option>`).join('');
}

// ----- Mensajes -----
export function toast(texto, ms = 3500) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.setAttribute('role', 'status');
  t.textContent = texto;
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

/** Muestra un aviso dentro de un contenedor. tipo: info | exito | error | alerta */
export function aviso(contenedor, texto, tipo = 'info') {
  const iconos = { info: 'info', exito: 'circle-check', error: 'circle-alert', alerta: 'circle-alert' };
  contenedor.innerHTML = texto
    ? `<div class="aviso ${tipo !== 'info' ? `aviso-${tipo}` : ''}" role="${tipo === 'error' ? 'alert' : 'status'}">${icono(iconos[tipo])}<div>${texto}</div></div>`
    : '';
}

/** Marca los campos con error a partir de { campo: 'mensaje' } que devuelve el servidor. */
export function mostrarErrores(formulario, detalles = {}) {
  let primero = null;
  for (const [campo, mensaje] of Object.entries(detalles || {})) {
    const input = formulario.querySelector(`[name="${campo}"]`);
    const caja = input?.closest('.campo');
    if (!caja) continue;
    caja.classList.add('con-error');
    const err = caja.querySelector('.error-campo');
    if (err) err.textContent = mensaje;
    input.setAttribute('aria-invalid', 'true');
    primero ??= input;
  }
  primero?.focus();
  return Boolean(primero);
}

export function limpiarErrores(formulario) {
  $$('.con-error', formulario).forEach((c) => c.classList.remove('con-error'));
  $$('[aria-invalid]', formulario).forEach((i) => i.removeAttribute('aria-invalid'));
}

/** Pone un botón en estado "cargando" mientras dura la promesa. */
export async function conCarga(boton, trabajo) {
  const html = boton.innerHTML;
  boton.disabled = true;
  boton.innerHTML = `<span class="cargando" aria-hidden="true"></span> ${esc(boton.dataset.cargando || 'Procesando…')}`;
  try {
    return await trabajo();
  } finally {
    boton.disabled = false;
    boton.innerHTML = html;
  }
}
