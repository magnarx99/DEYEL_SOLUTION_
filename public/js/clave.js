// Recuperar contraseña, restablecerla con el enlace y cambiarla con sesión iniciada.
import { listo } from './layout.js';
import { $, api, aviso, esc, conCarga } from './api.js';
import { validarGrupo, validacionEnVivo, alternarPassword, medidorFortaleza } from './formularios.js';

const form = $('#form-clave');
const pagina = document.body.dataset.pagina;
const mensaje = $('#mensaje');
alternarPassword(form);
validacionEnVivo(form);
if ($('#barra-fortaleza')) medidorFortaleza($('#f-password'), $('#barra-fortaleza'), $('#texto-fortaleza'));

const destinoPorRol = (rol) => ({ ADMIN: '/admin/dashboard.html', FUNCIONARIO: '/admin/bandeja.html' }[rol] || '/mis-solicitudes.html');

listo.then((s) => {
  if (pagina === 'cambiar-password') {
    if (!s.autenticado) location.replace('/login.html?volver=/cambiar-password.html');
    else if (!s.usuario.debe_cambiar_password) $('#motivo').textContent = 'Elija una contraseña que no use en otros sitios.';
  }
  if (pagina === 'restablecer' && !new URLSearchParams(location.search).get('token')) {
    aviso(mensaje, 'El enlace no es válido. <a href="/recuperar.html">Solicite uno nuevo</a>.', 'error');
    $('#enviar').disabled = true;
  }
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (pagina === 'recuperar') {
    const correo = form.elements.correo.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(correo)) {
      form.elements.correo.closest('.campo').classList.add('con-error');
      form.elements.correo.closest('.campo').querySelector('.error-campo').textContent = 'Escriba un correo válido.';
      return;
    }
    try {
      const r = await conCarga($('#enviar'), () => api('/api/auth/recuperar', { method: 'POST', body: { correo } }));
      aviso(mensaje, `${esc(r.mensaje)}<br><small>En este prototipo el enlace se muestra en la consola del servidor.</small>`, 'exito');
    } catch (err) {
      aviso(mensaje, esc(err.message), 'error');
    }
    return;
  }

  if (!validarGrupo(form)) return;
  try {
    if (pagina === 'restablecer') {
      const token = new URLSearchParams(location.search).get('token');
      await conCarga($('#enviar'), () => api('/api/auth/restablecer', { method: 'POST', body: { token, password: form.elements.password.value } }));
      aviso(mensaje, 'Contraseña actualizada. <a href="/login.html">Inicie sesión</a> con su nueva contraseña.', 'exito');
      form.reset();
    } else {
      await conCarga($('#enviar'), () => api('/api/auth/cambiar-password', {
        method: 'POST', body: { actual: form.elements.actual.value, nueva: form.elements.password.value },
      }));
      const s = await api('/api/auth/yo');
      location.href = destinoPorRol(s.usuario?.rol);
    }
  } catch (err) {
    aviso(mensaje, esc(err.message), 'error');
  }
});
