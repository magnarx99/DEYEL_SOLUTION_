// Tablero del administrador: indicadores, gráficos (hechos con HTML y CSS, sin librerías) y últimas solicitudes.
import { iniciarPanel, filaPqrds, filasClicables } from './admin.js';
import { $, api, aviso, esc } from './api.js';

const COLORES = ['#2B5C8A', '#336EA3', '#4FA3A5', '#6A9BD8', '#7FB5B0', '#1E3A5F', '#A8C5E2', '#5E8DB8', '#9CCFC9'];

/** Barras verticales: cada barra mide en proporción al valor más alto. */
function barrasVerticales(datos, color) {
  const max = Math.max(1, ...datos.map((d) => d.total));
  return `<div class="barras-v" role="img" aria-label="${esc(datos.map((d) => `${d.nombre}: ${d.total}`).join(', '))}">
    ${datos.map((d) => `<div class="bv-col"><b>${d.total}</b>
      <span class="bv-barra" style="height:${(d.total / max) * 100}%;background:${color}"></span>
      <span class="bv-et" title="${esc(d.nombre)}">${esc(d.nombre)}</span></div>`).join('')}</div>`;
}

/** Barras horizontales, una por fila. */
function barrasHorizontales(datos) {
  const max = Math.max(1, ...datos.map((d) => d.total));
  return `<div class="barras-h" role="img" aria-label="${esc(datos.map((d) => `${d.nombre}: ${d.total}`).join(', '))}">
    ${datos.map((d, i) => `<div class="bh-fila"><span class="bh-et" title="${esc(d.nombre)}">${esc(d.nombre.replace('Secretaría de ', 'Sec. '))}</span>
      <span class="bh-barra"><i style="width:${(d.total / max) * 100}%;background:${COLORES[i % COLORES.length]}"></i></span><b>${d.total}</b></div>`).join('')}</div>`;
}

async function cargar() {
  const e = await api('/api/admin/estadisticas');
  const t = e.totales;
  $('#fecha-hoy').textContent = `Datos al ${new Intl.DateTimeFormat('es-CO', { dateStyle: 'long', timeZone: 'America/Bogota' }).format(new Date())}`;
  const tarjeta = (titulo, valor, url, clase = '') => `<a class="indicador ${clase}" href="${url}"><span>${titulo}</span><strong>${valor.toLocaleString('es-CO')}</strong></a>`;
  $('#indicadores').innerHTML = [
    tarjeta('Total radicadas', t.total, '/admin/bandeja.html'),
    tarjeta('Sin gestionar', t.radicadas, '/admin/bandeja.html?estado=RADICADA'),
    tarjeta('En trámite', t.en_tramite, '/admin/bandeja.html?estado=EN_TRAMITE'),
    tarjeta('Respondidas', t.respondidas, '/admin/bandeja.html?estado=RESPONDIDA', 'indicador-exito'),
    tarjeta('Vencidas', t.vencidas, '/admin/bandeja.html?semaforo=VENCIDA', 'indicador-error'),
    tarjeta('Vencen en 3 días hábiles', t.por_vencer, '/admin/bandeja.html?semaforo=POR_VENCER', 'indicador-alerta'),
  ].join('');

  $('#ultimas').innerHTML = e.ultimas.map((p) => filaPqrds(p)).join('') || '<tr><td colspan="8" class="vacia">Aún no hay solicitudes.</td></tr>';

  const meses = new Intl.DateTimeFormat('es-CO', { month: 'short', year: '2-digit', timeZone: 'UTC' });
  const cortos = { 'Solicitud de información': 'Información', 'Solicitud de datos personales': 'Datos personales', 'Agenda tu cita': 'Citas' };
  $('#g-tipo').innerHTML = barrasVerticales(e.porTipo.map((d) => ({ ...d, nombre: cortos[d.nombre] || d.nombre })), '#336EA3');
  $('#g-dependencia').innerHTML = barrasHorizontales(e.porDependencia);
  $('#g-mes').innerHTML = barrasVerticales(e.porMes.map((m) => ({ nombre: meses.format(new Date(`${m.mes}-15T00:00:00Z`)), total: m.total })), '#4FA3A5');
}

iniciarPanel('dashboard').then(async () => {
  filasClicables($('#ultimas'), { alActualizar: () => {} });
  try {
    await cargar();
  } catch (err) {
    aviso($('#indicadores'), esc(err.message), 'error');
  }
});
