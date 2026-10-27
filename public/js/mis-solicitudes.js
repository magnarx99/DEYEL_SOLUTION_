// "Mis solicitudes": todas las PQRDS del ciudadano con sesión iniciada.
import { listo } from './layout.js';
import { $, api, esc, aviso, fecha, fechaHora, estadoHtml, semaforoHtml, ETIQUETA_ESTADO } from './api.js';

let solicitudes = [];
let filtro = 'TODAS';

const GRUPOS = {
  TODAS: () => true,
  ABIERTAS: (p) => !['RESPONDIDA', 'CERRADA'].includes(p.estado),
  RESPONDIDAS: (p) => ['RESPONDIDA', 'CERRADA'].includes(p.estado),
};
const ETIQUETAS = { TODAS: 'Todas', ABIERTAS: 'En curso', RESPONDIDAS: 'Respondidas' };

function pintarFiltros() {
  $('#filtros').innerHTML = Object.keys(GRUPOS).map((k) => `
    <label class="opcion"><input type="radio" name="filtro" value="${k}" ${k === filtro ? 'checked' : ''}>
      ${ETIQUETAS[k]} (${solicitudes.filter(GRUPOS[k]).length})</label>`).join('');
}

function pintar() {
  const lista = solicitudes.filter(GRUPOS[filtro]);
  if (!solicitudes.length) {
    $('#lista').innerHTML = `<div class="panel" style="text-align:center">
      <h2>Aún no tiene solicitudes</h2>
      <p class="texto-suave">Cuando radique una petición, queja, reclamo o cualquier otra solicitud, la verá aquí con su estado.</p>
      <a class="boton" href="/pqrds.html">Radicar mi primera solicitud</a></div>`;
    return;
  }
  if (!lista.length) {
    $('#lista').innerHTML = '<div class="panel texto-suave" style="text-align:center">No hay solicitudes en este grupo.</div>';
    return;
  }
  $('#lista').innerHTML = lista.map((p) => `
    <details class="solicitud">
      <summary>
        <div>
          <div class="solicitud-titulo">${esc(p.asunto)}</div>
          <div class="solicitud-meta">
            <span>${esc(p.radicado)}</span><span>${esc(p.tipo)}</span><span>Radicada el ${esc(fecha(p.fecha_radicacion))}</span>
          </div>
        </div>
        <div style="text-align:right">${estadoHtml(p.estado)}<div style="margin-top:4px">${semaforoHtml(p.semaforo)}</div></div>
      </summary>
      <div class="solicitud-cuerpo">
        <div>
          <dl class="resumen">
            <dt>Dependencia</dt><dd>${esc(p.dependencia)}</dd>
            <dt>Fecha límite</dt><dd>${esc(fecha(p.fecha_limite))}</dd>
            ${p.fecha_cita_preferida ? `<dt>Cita solicitada</dt><dd>${esc(fecha(p.fecha_cita_preferida))}, ${p.modalidad_cita === 'VIRTUAL' ? 'virtual' : 'presencial'}</dd>` : ''}
            <dt>Descripción</dt><dd style="font-weight:400">${esc(p.descripcion)}</dd>
          </dl>
          ${p.respuesta
            ? `<h3 style="margin-top:20px">Respuesta de la entidad</h3><div class="respuesta-entidad">${esc(p.respuesta)}</div>`
            : '<p class="texto-suave texto-chico" style="margin-top:16px">La respuesta aparecerá aquí cuando la entidad la registre.</p>'}
        </div>
        <div>
          <h3>Historial</h3>
          <ol class="linea-tiempo">${p.historial.map((h) => `<li><time>${esc(fechaHora(h.fecha))}</time><p><strong>${esc(ETIQUETA_ESTADO[h.estado_nuevo])}</strong></p></li>`).join('')}</ol>
        </div>
      </div>
    </details>`).join('');
}

$('#filtros').addEventListener('change', (e) => {
  filtro = e.target.value;
  pintar();
});

listo.then(async (s) => {
  if (!s.autenticado) return location.replace('/login.html?volver=/mis-solicitudes.html');
  if (s.usuario.rol !== 'CIUDADANO') return location.replace('/admin/');
  $('#saludo').textContent = `Hola, ${s.ciudadano.nombres.split(' ')[0]}`;
  const avisoGuardado = sessionStorage.getItem('pqrds_aviso');
  if (avisoGuardado) {
    aviso($('#aviso'), esc(avisoGuardado), 'exito');
    sessionStorage.removeItem('pqrds_aviso');
  }
  try {
    solicitudes = await api('/api/pqrds/mias');
    pintarFiltros();
    pintar();
  } catch (err) {
    $('#lista').innerHTML = '';
    aviso($('#aviso'), esc(err.message), 'error');
  }
});
