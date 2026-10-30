import { listo } from './layout.js';
import { $, $$, api, aviso, esc, fecha, conCarga, mostrarErrores, limpiarErrores, sesion, toast } from './api.js';
import {
  bloquePersonal, bloqueContacto, cargarMunicipios, rellenar, leerCiudadano, validarGrupo, validacionEnVivo, soloDigitos,
} from './formularios.js';

const form = $('#form-cuenta');
const formDocumento = $('#form-documento');
const formEliminar = $('#form-eliminar');
const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date());

$('#b-personal').innerHTML = bloquePersonal();
$('#b-contacto').innerHTML = bloqueContacto();
soloDigitos($('#f-telefono'));
soloDigitos($('#f-telefono_fijo'));
soloDigitos($('#d-cedula'));
soloDigitos($('#d-confirmar_cedula'));
$('#d-fecha_expedicion').max = hoy;
[form, formDocumento, formEliminar].forEach(validacionEnVivo);

let ciudadano;

function mostrar(c) {
  ciudadano = c;
  $('#dato-documento').textContent = `${c.tipo_documento} ${c.cedula}`;
  $('#dato-expedicion').textContent = fecha(c.fecha_expedicion);
  $('#dato-desde').textContent = fecha(c.fecha_creacion);
  rellenar(form, c);
}

listo.then(async (s) => {
  if (!s.autenticado) return location.replace('/login.html?volver=/mi-cuenta.html');
  if (s.usuario.rol !== 'CIUDADANO') return location.replace('/cambiar-password.html');
  await cargarMunicipios(form);
  mostrar(s.ciudadano);
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!validarGrupo(form)) return;
  try {
    const r = await conCarga($('#guardar'), () => api(`/api/ciudadanos/${ciudadano.id_ciudadano}`, { method: 'PUT', body: leerCiudadano(form) }));
    mostrar(r.ciudadano);
    sesion(true);
    aviso($('#mensaje'), 'Sus datos quedaron actualizados.', 'exito');
  } catch (err) {
    mostrarErrores(form, err.detalles);
    aviso($('#mensaje'), esc(err.message), 'error');
  }
});

// --- Ventanas: cerrar con los botones "Cancelar" y "X" ---
$$('dialog.modal').forEach((d) => {
  $$('[data-cerrar]', d).forEach((b) => b.addEventListener('click', () => d.close()));
});

/** El servidor llama "password" al campo que en estos formularios se llama "password_actual". */
const erroresDeFormulario = (detalles) => {
  const d = { ...(detalles || {}) };
  if (d.password) d.password_actual = d.password;
  return d;
};

// --- Corregir datos del documento ---
$('#abrir-documento').addEventListener('click', async () => {
  formDocumento.reset();
  limpiarErrores(formDocumento);
  aviso($('#mensaje-documento'), '');
  formDocumento.elements.tipo_documento.value = ciudadano.tipo_documento;
  formDocumento.elements.cedula.value = ciudadano.cedula;
  formDocumento.elements.fecha_expedicion.value = ciudadano.fecha_expedicion;
  $('#modal-documento').showModal();
  const info = $('#info-documento');
  aviso(info, 'Consultando cuántas correcciones tiene disponibles…');
  try {
    const r = await api('/api/ciudadanos/yo/documento');
    aviso(info, r.disponibles
      ? `Use esta opción solo si se equivocó al escribir su documento. Puede hacer <strong>${r.disponibles} de ${r.maximo}</strong> correcciones este año.
         Si cambia el número, úselo desde ahora para iniciar sesión y consultar sus radicados. Le avisaremos al correo registrado.`
      : `Ya usó las ${r.maximo} correcciones permitidas este año. Para otra corrección, radique una
         <a href="/radicar.html?tipo=DATOS_PERSONALES">solicitud de datos personales</a> con una copia de su documento.`,
    r.disponibles ? 'info' : 'alerta');
    $('#guardar-documento').disabled = !r.disponibles;
  } catch (err) {
    aviso(info, esc(err.message), 'error');
  }
});

formDocumento.addEventListener('submit', async (e) => {
  e.preventDefault();
  aviso($('#mensaje-documento'), '');
  if (!validarGrupo(formDocumento)) return;
  const v = (n) => formDocumento.elements[n].value.trim();
  try {
    const r = await conCarga($('#guardar-documento'), () => api('/api/ciudadanos/yo/documento', {
      method: 'POST',
      body: {
        tipo_documento: v('tipo_documento'), cedula: v('cedula'), confirmar_cedula: v('confirmar_cedula'),
        fecha_expedicion: v('fecha_expedicion'), motivo: v('motivo'), password: formDocumento.elements.password_actual.value,
      },
    }));
    mostrar(r.ciudadano);
    sesion(true);
    $('#modal-documento').close();
    aviso($('#mensaje'), 'Los datos de su documento quedaron corregidos. El cambio quedó registrado por seguridad.', 'exito');
    toast('Documento corregido.');
  } catch (err) {
    mostrarErrores(formDocumento, erroresDeFormulario(err.detalles));
    aviso($('#mensaje-documento'), esc(err.message), 'error');
  }
});

// --- Eliminar la cuenta ---
$('#abrir-eliminar').addEventListener('click', async () => {
  formEliminar.reset();
  limpiarErrores(formEliminar);
  aviso($('#mensaje-eliminar'), '');
  $('#modal-eliminar').showModal();
  try {
    const mias = await api('/api/pqrds/mias');
    $('#consecuencia-datos').innerHTML = mias.length
      ? `<strong>Sus datos personales:</strong> se conservan junto a sus ${mias.length} solicitud(es) radicada(s), solo para responderlas y archivarlas.`
      : '<strong>Sus datos personales:</strong> como no ha radicado solicitudes, también se borran por completo.';
  } catch { /* si falla se deja el texto general */ }
});

formEliminar.addEventListener('submit', async (e) => {
  e.preventDefault();
  aviso($('#mensaje-eliminar'), '');
  if (!validarGrupo(formEliminar)) return;
  try {
    const r = await conCarga($('#confirmar-eliminar'), () => api('/api/auth/eliminar-cuenta', {
      method: 'POST',
      body: { confirmacion: formEliminar.elements.confirmacion.value, password: formEliminar.elements.password_actual.value },
    }));
    sessionStorage.setItem('pqrds_aviso', r.datos_conservados
      ? 'Su cuenta fue eliminada. Sus solicitudes radicadas se conservan y puede consultarlas con el radicado y su cédula.'
      : 'Su cuenta y sus datos personales fueron eliminados.');
    location.replace('/');
  } catch (err) {
    mostrarErrores(formEliminar, erroresDeFormulario(err.detalles));
    aviso($('#mensaje-eliminar'), esc(err.message), 'error');
  }
});
