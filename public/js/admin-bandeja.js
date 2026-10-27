// Bandeja de PQRDS: filtros, orden, paginación, detalle/gestión y exportación a Excel.
import { iniciarPanel, filaPqrds, filasClicables } from './admin.js';
import { $, $$, api, esc, catalogos, llenarSelect } from './api.js';
import { soloDigitos } from './formularios.js';

const form = $('#filtros');
const CAMPOS = ['q', 'cedula', 'desde', 'hasta', 'tipo', 'estado', 'dependencia', 'municipio', 'semaforo'];
const estado = { pagina: 1, porPagina: 15, orden: 'fecha', dir: 'desc', total: 0 };
let esAdmin = false;

function filtrosActuales() {
  const f = {};
  for (const c of CAMPOS) {
    const v = form.elements[c].value.trim();
    if (v) f[c] = v;
  }
  return f;
}

function consulta(extra = {}) {
  return new URLSearchParams({ ...filtrosActuales(), ...extra }).toString();
}

async function cargar() {
  const tbody = $('#filas');
  tbody.innerHTML = '<tr><td colspan="8" class="vacia">Cargando…</td></tr>';
  const q = consulta({ pagina: estado.pagina, porPagina: estado.porPagina, orden: estado.orden, dir: estado.dir });
  history.replaceState(null, '', `?${consulta()}`);
  if (esAdmin) $('#exportar').href = `/api/admin/exportar?${consulta({ orden: estado.orden, dir: estado.dir })}`;
  try {
    const r = await api(`/api/admin/pqrds?${q}`);
    estado.total = r.total;
    tbody.innerHTML = r.registros.map((p) => filaPqrds(p)).join('')
      || '<tr><td colspan="8" class="vacia">No hay solicitudes con estos filtros. Pruebe limpiando alguno.</td></tr>';
    const paginas = Math.max(1, Math.ceil(r.total / estado.porPagina));
    const desde = r.total ? (estado.pagina - 1) * estado.porPagina + 1 : 0;
    $('#total').textContent = `${r.total.toLocaleString('es-CO')} solicitudes encontradas`;
    $('#pagina-texto').textContent = `Mostrando ${desde}–${Math.min(estado.pagina * estado.porPagina, r.total)} de ${r.total} (página ${estado.pagina} de ${paginas})`;
    $('#anterior').disabled = estado.pagina <= 1;
    $('#siguiente').disabled = estado.pagina >= paginas;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="vacia">${esc(err.message)}</td></tr>`;
  }
  $$('th button[data-orden]').forEach((b) => {
    if (b.dataset.orden === estado.orden) b.setAttribute('aria-sort', estado.dir === 'asc' ? 'ascending' : 'descending');
    else b.removeAttribute('aria-sort');
  });
}

iniciarPanel('bandeja').then(async (s) => {
  if (!s.autenticado) return;
  esAdmin = s.usuario.rol === 'ADMIN';
  if (esAdmin) $('#exportar').classList.remove('oculto');
  else $('#alcance').textContent = 'Solicitudes de su dependencia y las asignadas a usted.';

  const cat = await catalogos();
  llenarSelect(form.tipo, cat.tipos, { vacio: 'Todos', valor: (t) => t.codigo, texto: (t) => t.nombre });
  llenarSelect(form.dependencia, [{ id_dependencia: 'SIN', nombre: 'Por asignar' }, ...cat.dependencias], { vacio: 'Todas', valor: (d) => d.id_dependencia, texto: (d) => d.nombre });
  llenarSelect(form.municipio, cat.municipios, { vacio: 'Todos' });
  soloDigitos(form.cedula);

  // Los filtros llegan también desde la URL (enlaces del tablero)
  const params = new URLSearchParams(location.search);
  for (const c of CAMPOS) if (params.get(c)) form.elements[c].value = params.get(c);

  form.addEventListener('submit', (e) => { e.preventDefault(); estado.pagina = 1; cargar(); });
  form.addEventListener('change', (e) => { if (e.target.tagName === 'SELECT') { estado.pagina = 1; cargar(); } });
  $('#limpiar').addEventListener('click', () => { form.reset(); estado.pagina = 1; cargar(); });
  $('#anterior').addEventListener('click', () => { estado.pagina -= 1; cargar(); });
  $('#siguiente').addEventListener('click', () => { estado.pagina += 1; cargar(); });
  $('#por-pagina').addEventListener('change', (e) => { estado.porPagina = Number(e.target.value); estado.pagina = 1; cargar(); });
  $$('th button[data-orden]').forEach((b) => b.addEventListener('click', () => {
    estado.dir = estado.orden === b.dataset.orden && estado.dir === 'desc' ? 'asc' : 'desc';
    estado.orden = b.dataset.orden;
    cargar();
  }));
  filasClicables($('#filas'), { alActualizar: cargar });
  cargar();
});
