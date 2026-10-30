// Estructura común de todas las páginas: encabezado institucional, menú según el rol,
// migas de pan, pie de página y asistente virtual.
import { api, esc, icono, sesion, toast } from './api.js';
import { iniciarChatbot, abrirChatbot } from './chatbot.js';

const cuerpo = document.body;
const pagina = cuerpo.dataset.pagina || '';

function enlacesSegunRol(s) {
  const rol = s.autenticado ? s.usuario.rol : null;
  if (rol === 'ADMIN' || rol === 'FUNCIONARIO') {
    return [
      [rol === 'ADMIN' ? '/admin/dashboard.html' : '/admin/bandeja.html', 'Panel de gestión', 'panel', 'layout-dashboard'],
      ['/pqrds.html', 'Radicar PQRDS', 'radicar', 'file-pen-line'],
      ['/admin/consulta-cedula.html', 'Consulta por cédula', 'cedula', 'id-card'],
    ];
  }
  const base = [
    ['/', 'Inicio', 'inicio', 'house'],
    ['/pqrds.html', 'Radicar PQRDS', 'radicar', 'file-pen-line'],
    ['/seguimiento.html', 'Consultar radicado', 'seguimiento', 'search'],
  ];
  // Con sesión, el logo lleva al inicio: se omite el enlace para que el menú quepa en una línea
  if (rol === 'CIUDADANO') return [...base.slice(1), ['/mis-solicitudes.html', 'Mis solicitudes', 'mis-solicitudes', 'inbox']];
  return base;
}

function pintarEncabezado(s) {
  const enlaces = enlacesSegunRol(s).map(([href, texto, id, ic]) =>
    `<a href="${href}" ${id === pagina ? 'aria-current="page"' : ''}>${icono(ic)}${esc(texto)}</a>`).join('');
  const personal = s.autenticado && s.usuario.rol !== 'CIUDADANO';
  const ayuda = personal ? '' : `<button type="button" class="enlace-menu" id="abrir-ayuda">${icono('circle-help')}Ayuda</button>`;
  const sesionHtml = s.autenticado
    ? `${s.usuario.rol === 'CIUDADANO' ? `<a href="/mi-cuenta.html" ${pagina === 'cuenta' ? 'aria-current="page"' : ''}>${icono('user')}Mi cuenta</a>` : ''}
       <button type="button" class="enlace-menu boton-sesion" id="cerrar-sesion">${icono('log-out')}Cerrar sesión</button>`
    : `<a class="boton-sesion" href="/login.html">${icono('log-in')}Iniciar sesión</a>`;

  const encabezado = document.createElement('header');
  encabezado.innerHTML = `
    <a class="saltar" href="#contenido">Saltar al contenido</a>
    <div class="franja-gov"><div class="contenedor">
      <span>Portal oficial de atención a la ciudadanía</span>
      <span>${s.autenticado ? `Sesión: ${esc(s.usuario.nombre)}` : 'Línea de atención: horario hábil de lunes a viernes'}</span>
    </div></div>
    <div class="encabezado"><div class="contenedor">
      <a class="marca" href="/">
        <img src="/img/logo-placeholder.svg" alt="">
        <span class="marca-texto"><strong>Gobernación de Antioquia</strong><span>Peticiones, quejas, reclamos, sugerencias y denuncias</span></span>
      </a>
      <button type="button" class="boton-menu" aria-expanded="false" aria-controls="menu-principal">${icono('menu')}<span class="sr-only">Abrir menú</span></button>
      <nav class="menu" id="menu-principal" aria-label="Menú principal">${enlaces}${ayuda}${sesionHtml}</nav>
    </div></div>`;
  if (s.autenticado) encabezado.classList.add('menu-largo'); // con sesión el menú tiene más opciones
  cuerpo.prepend(encabezado);

  const boton = encabezado.querySelector('.boton-menu');
  const menu = encabezado.querySelector('.menu');
  boton.addEventListener('click', () => {
    const abierto = menu.classList.toggle('abierto');
    boton.setAttribute('aria-expanded', String(abierto));
  });
  encabezado.querySelector('#abrir-ayuda')?.addEventListener('click', abrirChatbot);
  encabezado.querySelector('#cerrar-sesion')?.addEventListener('click', async () => {
    await api('/api/auth/logout', { method: 'POST' }).catch(() => {});
    location.href = '/';
  });
}

function pintarMigas() {
  if (!cuerpo.dataset.migas) return;
  const migas = JSON.parse(cuerpo.dataset.migas);
  const nav = document.createElement('nav');
  nav.className = 'migas';
  nav.setAttribute('aria-label', 'Ruta de navegación');
  nav.innerHTML = `<div class="contenedor"><ol>${migas.map(([texto, href], i) =>
    (i === migas.length - 1 || !href ? `<li><span aria-current="page">${esc(texto)}</span></li>` : `<li><a href="${href}">${esc(texto)}</a></li>`)).join('')}</ol></div>`;
  document.querySelector('header').after(nav);
}

function pintarPie() {
  const pie = document.createElement('footer');
  pie.className = 'pie';
  pie.innerHTML = `
    <div class="contenedor">
      <div>
        <h2>Gobernación de Antioquia</h2>
        <p>Centro Administrativo Departamental José María Córdova (La Alpujarra), Medellín.<br>
        Este portal es un prototipo académico: los datos de contacto son de ejemplo.</p>
      </div>
      <div>
        <h2>Atención</h2>
        <ul>
          <li><a href="/pqrds.html">Radicar PQRDS</a></li>
          <li><a href="/seguimiento.html">Consultar radicado</a></li>
          <li><a href="/registro.html">Crear cuenta</a></li>
        </ul>
      </div>
      <div>
        <h2>Transparencia</h2>
        <ul>
          <li><a href="/politica-datos.html">Política de tratamiento de datos</a></li>
          <li><a href="/politica-datos.html#terminos">Términos de respuesta</a></li>
        </ul>
      </div>
    </div>
    <div class="pie-legal"><div class="contenedor">Este portal aplica la Ley 1755 de 2015 (derecho de petición), la Ley 1581 de 2012 (protección de datos personales) y la Ley 1712 de 2014 (transparencia).</div></div>`;
  cuerpo.append(pie);
}

export const listo = (async () => {
  const s = await sesion();
  // Si el administrador debe cambiar su contraseña temporal, se le lleva a hacerlo primero
  if (s.autenticado && s.usuario.debe_cambiar_password && pagina !== 'cambiar-password') {
    location.replace('/cambiar-password.html');
    return s;
  }
  pintarEncabezado(s);
  pintarMigas();
  pintarPie();
  // Mensaje que dejó la página anterior antes de redirigir (p. ej. "Su cuenta fue eliminada")
  const pendiente = sessionStorage.getItem('pqrds_aviso');
  if (pendiente) {
    sessionStorage.removeItem('pqrds_aviso');
    toast(pendiente, 9000);
  }
  if (!('sinChat' in cuerpo.dataset) && !(s.autenticado && s.usuario.rol !== 'CIUDADANO')) iniciarChatbot();
  return s;
})();
