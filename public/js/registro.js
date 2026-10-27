// Registro por pasos con validación en tiempo real.
import { listo } from './layout.js';
import { $, $$, api, aviso, esc, conCarga, mostrarErrores } from './api.js';
import {
  validarGrupo, validacionEnVivo, soloDigitos, medidorFortaleza, alternarPassword, bloqueIdentificacion,
  bloquePersonal, bloqueContacto, bloqueAutorizacion, cargarMunicipios, leerCiudadano,
} from './formularios.js';

const form = $('#form-registro');
const NOMBRES = ['Identificación', 'Datos personales', 'Ubicación y contacto', 'Datos de acceso', 'Autorizaciones'];
let paso = 1;

$('#b-identificacion').innerHTML = bloqueIdentificacion();
$('#b-personal').innerHTML = bloquePersonal();
$('#b-contacto').innerHTML = bloqueContacto({ correoObligatorio: true });
$('#b-autorizacion').innerHTML = bloqueAutorizacion();
cargarMunicipios(form);
['#f-cedula', '#f-telefono', '#f-telefono_fijo'].forEach((s) => soloDigitos($(s)));
medidorFortaleza($('#f-password'), $('#barra-fortaleza'), $('#texto-fortaleza'));
alternarPassword(form);
validacionEnVivo(form);

const cedulaGuardada = sessionStorage.getItem('pqrds_cedula');
if (cedulaGuardada) $('#f-cedula').value = cedulaGuardada;

function irA(n, enfocar = true) {
  paso = n;
  $$('section[data-paso]', form).forEach((s) => { s.hidden = Number(s.dataset.paso) !== n; });
  $('#paso-actual').textContent = n;
  $('#paso-nombre').textContent = NOMBRES[n - 1];
  $('#barra').style.width = `${n * 20}%`;
  $('.pasos-barra').setAttribute('aria-valuenow', n);
  $$('.pasos-lista li').forEach((li) => {
    const k = Number(li.dataset.paso);
    li.className = k === n ? 'actual' : k < n ? 'hecho' : '';
  });
  $('#anterior').hidden = n === 1;
  $('#siguiente').hidden = n === 5;
  $('#crear').hidden = n !== 5;
  if (n === 4) $('#correo-usuario').textContent = $('#f-correo').value;
  if (enfocar) $(`#h-${n}`).focus();
}

$('#siguiente').addEventListener('click', () => {
  if (validarGrupo($(`section[data-paso="${paso}"]`, form))) irA(paso + 1);
});
$('#anterior').addEventListener('click', () => irA(paso - 1));

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (paso !== 5 || !validarGrupo($('section[data-paso="5"]', form))) return;
  const datos = {
    ...leerCiudadano(form),
    password: form.elements.password.value,
    confirmar_password: form.elements.confirmar_password.value,
  };
  try {
    const r = await conCarga($('#crear'), () => api('/api/auth/registro', { method: 'POST', body: datos }));
    sessionStorage.setItem('pqrds_aviso', r.mensaje);
    location.href = '/mis-solicitudes.html';
  } catch (err) {
    aviso($('#mensaje'), esc(err.message), 'error');
    if (err.detalles) {
      // Lleva al usuario al primer paso que tiene un error
      const primero = Object.keys(err.detalles).map((c) => form.elements[c]?.closest?.('section[data-paso]')).find(Boolean);
      if (primero) {
        irA(Number(primero.dataset.paso));
        mostrarErrores(form, err.detalles);
      }
    }
  }
});

listo.then((s) => {
  if (s.autenticado) location.replace('/mis-solicitudes.html');
});
irA(1, false);
