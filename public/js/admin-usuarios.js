// Gestión de usuarios: crear funcionarios, cambiar rol, activar/desactivar y desbloquear.
import { iniciarPanel } from './admin.js';
import { $, $$, api, esc, aviso, catalogos, llenarSelect, conCarga, mostrarErrores, limpiarErrores, toast } from './api.js';
import { alternarPassword } from './formularios.js';

const ROLES = { ADMIN: 'Administrador', FUNCIONARIO: 'Funcionario', CIUDADANO: 'Ciudadano' };
const modal = $('#modal-usuario');
const formUsuario = $('#form-usuario');
let usuarios = [];
let dependencias = [];
let yo = null;
let temporizador;

function pintar() {
  $('#total').textContent = `${usuarios.length} usuarios`;
  $('#filas').innerHTML = usuarios.map((u) => {
    const propio = u.correo === yo.correo;
    const opcionesRol = Object.entries(ROLES)
      .filter(([k]) => k !== 'CIUDADANO' || u.cedula)
      .map(([k, v]) => `<option value="${k}" ${k === u.rol ? 'selected' : ''}>${v}</option>`).join('');
    const opcionesDep = `<option value="">Sin dependencia</option>${dependencias.map((d) =>
      `<option value="${d.id_dependencia}" ${d.id_dependencia === u.id_dependencia ? 'selected' : ''}>${esc(d.nombre)}</option>`).join('')}`;
    return `<tr class="${u.activo ? '' : 'inactivo'}" data-id="${u.id_usuario}">
      <td><strong>${esc(u.nombre)}</strong>${u.cedula ? `<br><small class="texto-suave">CC ${esc(u.cedula)}</small>` : ''}</td>
      <td>${esc(u.correo)}</td>
      <td><label class="sr-only" for="rol-${u.id_usuario}">Rol de ${esc(u.nombre)}</label>
        <select id="rol-${u.id_usuario}" data-cambio="rol" ${propio ? 'disabled' : ''} style="min-height:34px">${opcionesRol}</select></td>
      <td>${u.rol === 'CIUDADANO' ? '<span class="texto-suave">—</span>' : `<label class="sr-only" for="dep-${u.id_usuario}">Dependencia</label>
        <select id="dep-${u.id_usuario}" data-cambio="dependencia" style="min-height:34px;max-width:240px">${opcionesDep}</select>`}</td>
      <td>${u.activo ? '<span class="estado estado-RESPONDIDA">Activo</span>' : '<span class="estado estado-CERRADA">Inactivo</span>'}
        ${u.bloqueado ? '<br><small class="semaforo semaforo-VENCIDA">Bloqueado por intentos</small>' : ''}</td>
      <td><div class="fila-acciones">
        ${propio ? '<span class="texto-suave texto-chico">Su cuenta</span>' : `<button type="button" class="boton ${u.activo ? 'boton-peligro' : 'boton-secundario'} boton-chico" data-accion="activo">${u.activo ? 'Desactivar' : 'Activar'}</button>`}
        ${u.bloqueado ? '<button type="button" class="boton boton-secundario boton-chico" data-accion="desbloquear">Desbloquear</button>' : ''}
      </div></td>
    </tr>`;
  }).join('') || '<tr><td colspan="6" class="vacia">No hay usuarios con estos filtros.</td></tr>';
}

async function cargar() {
  const q = new URLSearchParams({ q: $('#q').value.trim(), rol: $('#rol').value });
  usuarios = await api(`/api/admin/usuarios?${q}`);
  pintar();
}

async function actualizar(id, cambios) {
  try {
    await api(`/api/admin/usuarios/${id}`, { method: 'PATCH', body: cambios });
    toast('Usuario actualizado');
  } catch (err) {
    toast(err.message, 5000);
  }
  cargar();
}

$('#filas').addEventListener('change', (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (!tr) return;
  if (e.target.dataset.cambio === 'rol') actualizar(tr.dataset.id, { rol: e.target.value });
  if (e.target.dataset.cambio === 'dependencia') actualizar(tr.dataset.id, { id_dependencia: e.target.value || null });
});
$('#filas').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-accion]');
  if (!b) return;
  const id = b.closest('tr').dataset.id;
  const u = usuarios.find((x) => String(x.id_usuario) === id);
  if (b.dataset.accion === 'activo') {
    if (u.activo && !confirm(`¿Desactivar la cuenta de ${u.nombre}? No podrá iniciar sesión.`)) return;
    actualizar(id, { activo: !u.activo });
  }
  if (b.dataset.accion === 'desbloquear') actualizar(id, { desbloquear: true });
});

$('#filtros').addEventListener('input', () => {
  clearTimeout(temporizador);
  temporizador = setTimeout(cargar, 300);
});
$('#filtros').addEventListener('submit', (e) => e.preventDefault());

// ----- Crear funcionario -----
$('#nuevo').addEventListener('click', () => {
  formUsuario.reset();
  limpiarErrores(formUsuario);
  $('#u-mensaje').innerHTML = '';
  modal.showModal();
  $('#u-nombre').focus();
});
$$('[data-cerrar]', modal).forEach((b) => b.addEventListener('click', () => modal.close()));
alternarPassword(formUsuario);
formUsuario.addEventListener('submit', async (e) => {
  e.preventDefault();
  limpiarErrores(formUsuario);
  const datos = Object.fromEntries(new FormData(formUsuario));
  try {
    await conCarga(formUsuario.querySelector('button[type="submit"]'), () => api('/api/admin/usuarios', { method: 'POST', body: datos }));
    modal.close();
    toast(`Usuario creado: ${datos.correo}`);
    cargar();
  } catch (err) {
    mostrarErrores(formUsuario, err.detalles);
    aviso($('#u-mensaje'), esc(err.message), 'error');
  }
});

iniciarPanel('usuarios').then(async (s) => {
  if (!s.autenticado) return;
  yo = s.usuario;
  dependencias = (await catalogos()).dependencias;
  llenarSelect($('#u-dependencia'), dependencias, { vacio: 'Seleccione…', valor: (d) => d.id_dependencia, texto: (d) => d.nombre });
  cargar();
});
