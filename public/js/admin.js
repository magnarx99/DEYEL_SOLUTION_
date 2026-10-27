// Utilidades del panel de gestión: menú del panel y ventana de detalle/gestión de una PQRDS.
import { listo } from './layout.js';
import {
  $, api, esc, icono, fecha, fechaHora, estadoHtml, semaforoHtml, aviso, catalogos, llenarSelect, tamano,
  conCarga, mostrarErrores, limpiarErrores, toast, ETIQUETA_ESTADO,
} from './api.js';

const SECCIONES = [
  ['dashboard', '/admin/dashboard.html', 'Tablero', 'chart-column', ['ADMIN']],
  ['bandeja', '/admin/bandeja.html', 'Bandeja de PQRDS', 'inbox', ['ADMIN', 'FUNCIONARIO']],
  ['cedula', '/admin/consulta-cedula.html', 'Consulta por cédula', 'id-card', ['ADMIN', 'FUNCIONARIO']],
  ['usuarios', '/admin/usuarios.html', 'Usuarios', 'users', ['ADMIN']],
  ['faq', '/admin/faq.html', 'Asistente virtual', 'bot', ['ADMIN']],
  ['auditoria', '/admin/auditoria.html', 'Auditoría', 'history', ['ADMIN']],
];

/** Pinta el menú del panel y devuelve la sesión. */
export async function iniciarPanel(actual) {
  const s = await listo;
  if (!s.autenticado || s.usuario.rol === 'CIUDADANO') return s; // el servidor ya respondió 403
  const nav = document.createElement('nav');
  nav.className = 'subnav';
  nav.setAttribute('aria-label', 'Secciones del panel');
  nav.innerHTML = `<div class="contenedor"><ul>${SECCIONES.filter((x) => x[4].includes(s.usuario.rol)).map(([id, href, texto, ic]) =>
    `<li><a href="${href}" ${id === actual ? 'aria-current="page"' : ''}>${icono(ic)}${texto}</a></li>`).join('')}</ul></div>`;
  (document.querySelector('.migas') || document.querySelector('header')).after(nav);
  return s;
}

// ---------------------------------------------------------------------
// Detalle y gestión de una PQRDS
// ---------------------------------------------------------------------
let modal;
let alCambiar = () => {};

function asegurarModal() {
  if (modal) return modal;
  modal = document.createElement('dialog');
  modal.className = 'modal';
  modal.setAttribute('aria-labelledby', 'modal-titulo');
  modal.innerHTML = `
    <div class="modal-cabecera"><h2 id="modal-titulo">Detalle</h2>
      <button type="button" class="cerrar" aria-label="Cerrar">${icono('x')}</button></div>
    <div class="modal-cuerpo" id="modal-cuerpo"></div>`;
  document.body.append(modal);
  modal.querySelector('.cerrar').addEventListener('click', () => modal.close());
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.close(); });
  return modal;
}

const dato = (k, v) => `<dt>${esc(k)}</dt><dd>${v}</dd>`;

function detalleHtml(p, s, catalogo, funcionarios) {
  const c = p.ciudadano;
  const cerrada = p.estado === 'CERRADA';
  const plazo = p.dias_habiles_restantes === null ? ''
    : p.dias_habiles_restantes < 0 ? ` (vencida hace ${-p.dias_habiles_restantes} días hábiles)`
      : ` (quedan ${p.dias_habiles_restantes} días hábiles)`;
  return `
    <div class="detalle-rejilla">
      <div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:16px">${estadoHtml(p.estado)} ${semaforoHtml(p.semaforo)}</div>
        <dl class="resumen">
          ${dato('Tipo', esc(p.tipo))}
          ${dato('Asunto', esc(p.asunto))}
          ${dato('Radicada', esc(fechaHora(p.fecha_radicacion)))}
          ${dato('Fecha límite', esc(fecha(p.fecha_limite) + plazo))}
          ${dato('Canal', esc(p.canal))}
          ${dato('Municipio del hecho', esc(p.municipio_hecho))}
          ${dato('Dependencia', esc(p.dependencia || 'Por asignar'))}
          ${dato('Funcionario', esc(p.funcionario || 'Sin asignar'))}
          ${p.fecha_cita_preferida ? dato('Cita solicitada', esc(`${fecha(p.fecha_cita_preferida)}, ${p.modalidad_cita.toLowerCase()}`)) : ''}
          ${dato('Respuesta por', esc({ CORREO: 'Correo electrónico', FISICO: 'Dirección física', NINGUNO: 'No aplica (anónima)' }[p.medio_respuesta]))}
        </dl>
        <h3>Descripción del caso</h3>
        <div class="descripcion-caso">${esc(p.descripcion)}</div>
        <h3>Adjuntos</h3>
        ${p.adjuntos.length ? `<ul class="adjuntos-lista">${p.adjuntos.map((a) =>
          `<li><a href="/api/admin/adjuntos/${a.id_adjunto}">${icono('download')}${esc(a.nombre_original)}</a> <span class="texto-suave">${tamano(a.tamano)}</span></li>`).join('')}</ul>`
          : '<p class="texto-suave texto-chico">Sin adjuntos.</p>'}
        ${p.respuesta ? `<h3>Respuesta registrada</h3><div class="respuesta-entidad">${esc(p.respuesta)}</div>` : ''}
        <h3>Historial</h3>
        <ol class="linea-tiempo">${p.historial.map((h) => `
          <li><time>${esc(fechaHora(h.fecha))}${h.usuario ? `, ${esc(h.usuario)}` : ''}</time>
          <p><strong>${esc(ETIQUETA_ESTADO[h.estado_nuevo])}</strong>${h.comentario ? `: ${esc(h.comentario)}` : ''}</p></li>`).join('')}</ol>
      </div>
      <div>
        <h3>Ciudadano</h3>
        ${c ? `<dl class="resumen">
            ${dato('Nombre', esc(`${c.nombres} ${c.apellidos}`))}
            ${dato('Documento', `<a href="/admin/consulta-cedula.html?cedula=${esc(c.cedula)}">${esc(`${c.tipo_documento} ${c.cedula}`)}</a>`)}
            ${dato('Celular', esc(c.telefono))}
            ${dato('Correo', esc(c.correo || '—'))}
            ${dato('Dirección', esc([c.direccion, c.barrio, c.municipio].filter(Boolean).join(', ')))}
          </dl>` : '<p class="texto-suave">Denuncia anónima: no hay datos del ciudadano.</p>'}
        <form class="gestion formulario" id="form-gestion" style="margin-top:24px" novalidate>
          <h3 style="margin-top:0">Gestionar</h3>
          ${cerrada ? '<p class="texto-suave texto-chico">La solicitud está cerrada.</p>' : ''}
          <div class="campo">
            <label for="g-estado">Estado</label>
            <select id="g-estado" name="estado" ${cerrada ? 'disabled' : ''}>
              ${Object.entries(ETIQUETA_ESTADO).map(([k, v]) => `<option value="${k}" ${k === p.estado ? 'selected' : ''}>${v}</option>`).join('')}
            </select>
            <span class="error-campo"></span>
          </div>
          <div class="campo">
            <label for="g-dependencia">Dependencia (trasladar)</label>
            <select id="g-dependencia" name="id_dependencia" ${cerrada ? 'disabled' : ''}></select>
            <span class="error-campo"></span>
          </div>
          ${s.usuario.rol === 'ADMIN' ? `
          <div class="campo">
            <label for="g-funcionario">Funcionario asignado</label>
            <select id="g-funcionario" name="id_funcionario_asignado" ${cerrada ? 'disabled' : ''}></select>
            <span class="error-campo"></span>
          </div>` : ''}
          <div class="campo">
            <label for="g-respuesta">Respuesta al ciudadano</label>
            <textarea id="g-respuesta" name="respuesta" maxlength="5000" placeholder="Obligatoria al marcar la solicitud como Respondida" ${cerrada ? 'disabled' : ''}></textarea>
            <span class="error-campo"></span>
          </div>
          <div class="campo">
            <label for="g-comentario">Nota interna para el historial</label>
            <input id="g-comentario" name="comentario" maxlength="300" ${cerrada ? 'disabled' : ''}>
          </div>
          <div id="g-mensaje" style="margin-top:12px"></div>
          <button class="boton boton-ancho" type="submit" style="margin-top:16px" data-cargando="Guardando…" ${cerrada ? 'disabled' : ''}>Guardar gestión</button>
        </form>
      </div>
    </div>`;
}

/** Abre la ventana con el detalle de la PQRDS y el formulario de gestión. */
export async function abrirDetalle(id, { alActualizar } = {}) {
  alCambiar = alActualizar || (() => {});
  const m = asegurarModal();
  const cuerpo = $('#modal-cuerpo', m);
  $('#modal-titulo', m).textContent = 'Cargando…';
  cuerpo.innerHTML = '<div class="esqueleto">Cargando la solicitud…</div>';
  if (!m.open) m.showModal();
  try {
    const [p, s, cat] = await Promise.all([api(`/api/admin/pqrds/${id}`), listo, catalogos()]);
    const funcionarios = s.usuario.rol === 'ADMIN' ? await api('/api/admin/funcionarios') : [];
    pintarDetalle(p, s, cat, funcionarios);
  } catch (err) {
    cuerpo.innerHTML = '';
    aviso(cuerpo, esc(err.message), 'error');
  }
}

function pintarDetalle(p, s, cat, funcionarios) {
  const cuerpo = $('#modal-cuerpo', modal);
  $('#modal-titulo', modal).textContent = p.radicado;
  cuerpo.innerHTML = detalleHtml(p, s, cat, funcionarios);
  llenarSelect($('#g-dependencia'), cat.dependencias, { vacio: 'Por asignar', valor: (d) => d.id_dependencia, texto: (d) => d.nombre });
  $('#g-dependencia').value = p.id_dependencia ?? '';
  if ($('#g-funcionario')) {
    llenarSelect($('#g-funcionario'), funcionarios, { vacio: 'Sin asignar', valor: (f) => f.id_usuario, texto: (f) => `${f.nombre}${f.dependencia ? ` (${f.dependencia})` : ''}` });
    $('#g-funcionario').value = p.id_funcionario_asignado ?? '';
  }

  const form = $('#form-gestion');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    limpiarErrores(form);
    const cambios = {
      estado: form.estado.value,
      respuesta: form.respuesta.value,
      comentario: form.comentario.value,
    };
    const dep = form.id_dependencia.value;
    if (String(p.id_dependencia ?? '') !== dep) cambios.id_dependencia = dep ? Number(dep) : null;
    if (form.id_funcionario_asignado && String(p.id_funcionario_asignado ?? '') !== form.id_funcionario_asignado.value) {
      cambios.id_funcionario_asignado = form.id_funcionario_asignado.value ? Number(form.id_funcionario_asignado.value) : null;
    }
    try {
      const actualizado = await conCarga(form.querySelector('button[type="submit"]'), () =>
        api(`/api/admin/pqrds/${p.id_pqrds}`, { method: 'PATCH', body: cambios }));
      toast(`Gestión guardada: ${actualizado.radicado}`);
      pintarDetalle(actualizado, s, cat, funcionarios);
      alCambiar();
    } catch (err) {
      mostrarErrores(form, err.detalles);
      aviso($('#g-mensaje'), esc(err.message), 'error');
    }
  });
}

/** Fila de tabla estándar para listas de PQRDS. */
export function filaPqrds(p, { conCiudadano = true } = {}) {
  return `<tr class="clicable" data-id="${p.id_pqrds}" tabindex="0">
    <td class="radicado">${esc(p.radicado)}</td>
    <td>${esc(fecha(p.fecha_radicacion))}</td>
    <td>${esc(p.tipo)}</td>
    ${conCiudadano ? `<td>${p.es_anonima ? '<span class="texto-suave">Anónima</span>' : `${esc(`${p.nombres} ${p.apellidos}`)}<br><small class="texto-suave">${esc(p.cedula)}</small>`}</td>` : ''}
    <td>${esc(p.asunto)}</td>
    <td>${esc(p.dependencia || 'Por asignar')}</td>
    <td>${estadoHtml(p.estado)}</td>
    <td>${esc(fecha(p.fecha_limite))}<br>${semaforoHtml(p.semaforo)}</td>
  </tr>`;
}

/** Abre el detalle al hacer clic o presionar Enter sobre una fila. */
export function filasClicables(tbody, opciones) {
  const abrir = (tr) => tr && abrirDetalle(tr.dataset.id, opciones);
  tbody.addEventListener('click', (e) => abrir(e.target.closest('tr[data-id]')));
  tbody.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') abrir(e.target.closest('tr[data-id]'));
  });
}
