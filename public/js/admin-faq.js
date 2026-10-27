// Administración de las respuestas del asistente virtual.
import { iniciarPanel } from './admin.js';
import { $, $$, api, esc, aviso, conCarga, mostrarErrores, limpiarErrores, toast } from './api.js';

const modal = $('#modal-faq');
const form = $('#form-faq');
let faqs = [];
let editando = null;

function pintar() {
  $('#filas').innerHTML = faqs.map((f) => `
    <tr class="${f.activo ? '' : 'inactivo'}" data-id="${f.id_faq}">
      <td><strong>${esc(f.pregunta)}</strong><br><small class="texto-suave">${esc(f.respuesta.slice(0, 110))}${f.respuesta.length > 110 ? '…' : ''}</small></td>
      <td><small>${esc(f.palabras_clave.split(',').join(', '))}</small></td>
      <td>${f.accion_url ? `<small>${esc(f.accion_texto)}<br><span class="texto-suave">${esc(f.accion_url)}</span></small>` : '—'}</td>
      <td>${f.activo ? '<span class="estado estado-RESPONDIDA">Activa</span>' : '<span class="estado estado-CERRADA">Inactiva</span>'}</td>
      <td><div class="fila-acciones">
        <button type="button" class="boton boton-secundario boton-chico" data-accion="editar">Editar</button>
        <button type="button" class="boton boton-peligro boton-chico" data-accion="eliminar">Eliminar</button>
      </div></td>
    </tr>`).join('') || '<tr><td colspan="5" class="vacia">No hay respuestas. Agregue la primera.</td></tr>';
}

async function cargar() {
  faqs = await api('/api/admin/faq');
  pintar();
}

function abrir(f) {
  editando = f?.id_faq || null;
  form.reset();
  limpiarErrores(form);
  $('#q-mensaje').innerHTML = '';
  $('#t-faq').textContent = f ? 'Editar respuesta' : 'Agregar respuesta';
  if (f) {
    for (const k of ['pregunta', 'palabras_clave', 'respuesta', 'accion_texto', 'accion_url']) form.elements[k].value = f[k] || '';
    form.elements.activo.checked = f.activo;
  }
  modal.showModal();
  form.elements.pregunta.focus();
}

$('#nueva').addEventListener('click', () => abrir(null));
$$('[data-cerrar]', modal).forEach((b) => b.addEventListener('click', () => modal.close()));
$('#filas').addEventListener('click', async (e) => {
  const b = e.target.closest('button[data-accion]');
  if (!b) return;
  const f = faqs.find((x) => String(x.id_faq) === b.closest('tr').dataset.id);
  if (b.dataset.accion === 'editar') abrir(f);
  if (b.dataset.accion === 'eliminar' && confirm(`¿Eliminar la respuesta "${f.pregunta}"?`)) {
    await api(`/api/admin/faq/${f.id_faq}`, { method: 'DELETE' });
    toast('Respuesta eliminada');
    cargar();
  }
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  limpiarErrores(form);
  const datos = Object.fromEntries(new FormData(form));
  datos.activo = form.elements.activo.checked;
  try {
    await conCarga(form.querySelector('button[type="submit"]'), () => api(editando ? `/api/admin/faq/${editando}` : '/api/admin/faq', {
      method: editando ? 'PUT' : 'POST', body: datos,
    }));
    modal.close();
    toast('Respuesta guardada');
    cargar();
  } catch (err) {
    mostrarErrores(form, err.detalles);
    aviso($('#q-mensaje'), esc(err.message), 'error');
  }
});

$('#form-prueba').addEventListener('submit', async (e) => {
  e.preventDefault();
  const mensaje = $('#prueba').value.trim();
  if (!mensaje) return;
  const r = await api('/api/chatbot', { method: 'POST', body: { mensaje } });
  aviso($('#resultado-prueba'), `${esc(r.respuesta)}${r.accion ? `<br><strong>Botón:</strong> ${esc(r.accion.texto)} (${esc(r.accion.url)})` : ''}`);
});

iniciarPanel('faq').then((s) => { if (s.autenticado) cargar(); });
