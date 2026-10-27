import { listo } from './layout.js';
import { $, api, aviso, esc, fecha, conCarga, mostrarErrores, sesion } from './api.js';
import {
  bloquePersonal, bloqueContacto, cargarMunicipios, rellenar, leerCiudadano, validarGrupo, validacionEnVivo, soloDigitos,
} from './formularios.js';

const form = $('#form-cuenta');
$('#b-personal').innerHTML = bloquePersonal();
$('#b-contacto').innerHTML = bloqueContacto();
soloDigitos($('#f-telefono'));
soloDigitos($('#f-telefono_fijo'));
validacionEnVivo(form);

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
