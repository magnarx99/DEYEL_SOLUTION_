// Consulta pública del estado de una PQRDS (radicado + cédula, o código para denuncias anónimas).
import { listo } from './layout.js';
import { $, api, esc, aviso, fecha, fechaHora, estadoHtml, semaforoHtml, conCarga, ETIQUETA_ESTADO } from './api.js';
import { CEDULA_REGEX, soloDigitos } from './formularios.js';

const form = $('#form-seguimiento');
const radicado = $('#radicado');
const cedula = $('#cedula-seg');
const codigo = $('#codigo');
const anonima = $('#es-anonima');
const RADICADO_REGEX = /^PQRDS-\d{4}-\d{6}$/;
let conSesion = false;

soloDigitos(cedula);
radicado.addEventListener('input', () => { radicado.value = radicado.value.toUpperCase().replace(/\s/g, ''); });
anonima.addEventListener('change', () => {
  $('#caja-cedula').hidden = anonima.checked || conSesion;
  $('#caja-codigo').hidden = !anonima.checked;
});

export function detalleHtml(p) {
  const historial = (p.historial || []).map((h) => `
    <li><time>${esc(fechaHora(h.fecha))}</time><p><strong>${esc(ETIQUETA_ESTADO[h.estado_nuevo])}</strong>${h.comentario ? `: ${esc(h.comentario)}` : ''}</p></li>`).join('');
  return `
    <div class="panel">
      <div class="ficha-cabecera">
        <div>
          <p class="texto-suave texto-chico" style="margin:0">${esc(p.tipo)}</p>
          <h2 style="margin:0">${esc(p.radicado)}</h2>
        </div>
        ${estadoHtml(p.estado)}
      </div>
      <dl class="resumen">
        <dt>Asunto</dt><dd>${esc(p.asunto)}</dd>
        <dt>Dependencia</dt><dd>${esc(p.dependencia)}</dd>
        <dt>Fecha de radicación</dt><dd>${esc(fechaHora(p.fecha_radicacion))}</dd>
        <dt>Fecha límite de respuesta</dt><dd>${esc(fecha(p.fecha_limite))} ${semaforoHtml(p.semaforo)}</dd>
        ${p.fecha_cita_preferida ? `<dt>Cita solicitada</dt><dd>${esc(fecha(p.fecha_cita_preferida))}, ${p.modalidad_cita === 'VIRTUAL' ? 'virtual' : 'presencial'}</dd>` : ''}
      </dl>
      ${p.respuesta ? `<h3 style="margin-top:24px">Respuesta de la entidad</h3><div class="respuesta-entidad">${esc(p.respuesta)}</div>` : ''}
      <h3 style="margin-top:24px">Historial</h3>
      <ol class="linea-tiempo">${historial}</ol>
    </div>`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const mensaje = $('#mensaje');
  mensaje.innerHTML = '';
  const errores = [];
  radicado.closest('.campo').classList.toggle('con-error', !RADICADO_REGEX.test(radicado.value));
  if (!RADICADO_REGEX.test(radicado.value)) errores.push(radicado);
  if (anonima.checked) {
    codigo.closest('.campo').classList.toggle('con-error', !codigo.value.trim());
    if (!codigo.value.trim()) errores.push(codigo);
  } else if (!conSesion) {
    cedula.closest('.campo').classList.toggle('con-error', !CEDULA_REGEX.test(cedula.value));
    if (!CEDULA_REGEX.test(cedula.value)) errores.push(cedula);
  }
  if (errores.length) { errores[0].focus(); return; }

  const q = new URLSearchParams(anonima.checked ? { codigo: codigo.value.trim().toUpperCase() } : conSesion ? {} : { cedula: cedula.value });
  try {
    const p = await conCarga($('#consultar'), () => api(`/api/pqrds/radicado/${encodeURIComponent(radicado.value)}?${q}`));
    $('#resultado-seguimiento').innerHTML = detalleHtml(p);
  } catch (err) {
    $('#resultado-seguimiento').innerHTML = '';
    aviso(mensaje, esc(err.message), 'error');
  }
});

listo.then((s) => {
  conSesion = s.autenticado;
  if (conSesion) {
    $('#caja-cedula').hidden = true;
    aviso($('#mensaje'), 'Tiene la sesión iniciada: solo necesita el número de radicado.');
  }
  const r = new URLSearchParams(location.search).get('radicado');
  if (r) {
    radicado.value = r.toUpperCase();
    if (conSesion) form.requestSubmit();
    else cedula.focus();
  }
});
