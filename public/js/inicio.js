import { listo } from './layout.js';
import { $ } from './api.js';
import { CEDULA_REGEX, soloDigitos } from './formularios.js';

const form = $('#form-inicio');
const input = $('#cedula-inicio');
soloDigitos(input);

listo.then((s) => {
  if (s.ciudadano) input.value = s.ciudadano.cedula;
});

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const campo = input.closest('.campo');
  if (!CEDULA_REGEX.test(input.value)) {
    campo.classList.add('con-error');
    input.focus();
    return;
  }
  // La cédula viaja en la sesión del navegador, no en la URL
  sessionStorage.setItem('pqrds_cedula', input.value);
  location.href = '/pqrds.html';
});
input.addEventListener('input', () => input.closest('.campo').classList.remove('con-error'));
