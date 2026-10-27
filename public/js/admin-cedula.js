// Consulta por cédula: ficha del ciudadano y todas sus PQRDS.
import { iniciarPanel, filaPqrds, filasClicables } from './admin.js';
import { $, api, esc, icono, aviso, fecha, conCarga } from './api.js';
import { CEDULA_REGEX, soloDigitos } from './formularios.js';

const form = $('#form-cedula');
const input = $('#cedula');
let esAdmin = false;
soloDigitos(input);

const GRUPOS = {
  PERSONA_CON_DISCAPACIDAD: 'Persona con discapacidad', VICTIMA_CONFLICTO: 'Víctima del conflicto', ADULTO_MAYOR: 'Adulto mayor',
  INDIGENA: 'Indígena', AFRODESCENDIENTE: 'Afrodescendiente', ROM: 'Rom', MIGRANTE: 'Migrante', LGBTIQ: 'LGBTIQ+',
};

async function consultar() {
  const cedula = input.value.trim();
  if (!CEDULA_REGEX.test(cedula)) {
    input.closest('.campo').classList.add('con-error');
    input.focus();
    return;
  }
  input.closest('.campo').classList.remove('con-error');
  $('#mensaje').innerHTML = '';
  try {
    const r = await conCarga($('#consultar'), () => api(`/api/admin/ciudadanos/${cedula}/pqrds`));
    history.replaceState(null, '', `?cedula=${cedula}`);
    const c = r.ciudadano;
    const abiertas = r.pqrds.filter((p) => !['RESPONDIDA', 'CERRADA'].includes(p.estado)).length;
    $('#resultado').innerHTML = `
      <div class="ficha" style="background:#fff">
        <div class="ficha-cabecera">
          <h3>${icono('user')}${esc(`${c.nombres} ${c.apellidos}`)}</h3>
          <span class="texto-suave texto-chico">${c.tiene_cuenta ? 'Tiene cuenta en el portal' : 'Sin cuenta en el portal'}</span>
        </div>
        <dl class="ficha-datos">
          <div><dt>Documento</dt><dd>${esc(`${c.tipo_documento} ${c.cedula}`)}</dd></div>
          <div><dt>Expedición</dt><dd>${esc(fecha(c.fecha_expedicion))}</dd></div>
          <div><dt>Municipio</dt><dd>${esc(c.municipio)}</dd></div>
          <div><dt>Dirección</dt><dd>${esc([c.direccion, c.barrio].filter(Boolean).join(', ') || '—')}</dd></div>
          <div><dt>Celular</dt><dd>${esc(c.telefono)}</dd></div>
          <div><dt>Correo</dt><dd>${esc(c.correo || '—')}</dd></div>
          <div><dt>Grupo poblacional</dt><dd>${esc(GRUPOS[c.grupo_poblacional] || 'Ninguno')}</dd></div>
          <div><dt>Registrado desde</dt><dd>${esc(fecha(c.fecha_creacion))}</dd></div>
          <div><dt>Solicitudes</dt><dd>${r.pqrds.length} en total, ${abiertas} en curso</dd></div>
        </dl>
      </div>
      <div class="resumen-filtros" style="margin-top:24px">
        <h2 style="font-size:1.25rem;margin:0">Solicitudes de este ciudadano</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <a class="boton boton-secundario boton-chico" href="/pqrds.html" id="radicar-nombre">${icono('plus')}Radicar en su nombre</a>
          ${esAdmin ? `<a class="boton boton-chico" href="/api/admin/exportar?cedula=${encodeURIComponent(c.cedula)}">${icono('file-spreadsheet')}Descargar en Excel</a>` : ''}
        </div>
      </div>
      <div class="tabla-envoltura"><table class="tabla">
        <thead><tr><th>Radicado</th><th>Fecha</th><th>Tipo</th><th>Asunto</th><th>Dependencia</th><th>Estado</th><th>Límite</th></tr></thead>
        <tbody id="filas">${r.pqrds.map((p) => filaPqrds(p, { conCiudadano: false })).join('')
          || '<tr><td colspan="7" class="vacia">Este ciudadano aún no tiene solicitudes.</td></tr>'}</tbody>
      </table></div>`;
    $('#radicar-nombre').addEventListener('click', () => sessionStorage.setItem('pqrds_cedula_funcionario', c.cedula));
    filasClicables($('#filas'), { alActualizar: consultar });
  } catch (err) {
    $('#resultado').innerHTML = '';
    aviso($('#mensaje'), esc(err.message), err.status === 404 ? 'alerta' : 'error');
  }
}

form.addEventListener('submit', (e) => { e.preventDefault(); consultar(); });

iniciarPanel('cedula').then((s) => {
  if (!s.autenticado) return;
  esAdmin = s.usuario.rol === 'ADMIN';
  const cedula = new URLSearchParams(location.search).get('cedula');
  if (cedula) {
    input.value = cedula;
    consultar();
  } else input.focus();
});
