import { listo } from './layout.js';
import { $, api, aviso, esc, conCarga } from './api.js';
import { alternarPassword } from './formularios.js';

const form = $('#form-login');
alternarPassword(form);

/** Solo se permite volver a rutas internas del portal. */
function destino(rol) {
  const volver = new URLSearchParams(location.search).get('volver');
  if (volver && volver.startsWith('/') && !volver.startsWith('//')) return volver;
  if (rol === 'ADMIN') return '/admin/dashboard.html';
  if (rol === 'FUNCIONARIO') return '/admin/bandeja.html';
  return '/mis-solicitudes.html';
}

listo.then((s) => {
  if (s.autenticado) location.replace(destino(s.usuario.rol));
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  let ok = true;
  for (const input of [form.usuario, form.password]) {
    const vacio = !input.value.trim();
    input.closest('.campo').classList.toggle('con-error', vacio);
    if (vacio && ok) { input.focus(); ok = false; }
  }
  if (!ok) return;
  try {
    const r = await conCarga($('#entrar'), () => api('/api/auth/login', {
      method: 'POST', body: { usuario: form.usuario.value.trim(), password: form.password.value },
    }));
    location.href = r.debe_cambiar_password ? '/cambiar-password.html' : destino(r.rol);
  } catch (err) {
    aviso($('#mensaje'), esc(err.message), 'error');
    form.password.value = '';
    form.password.focus();
  }
});
