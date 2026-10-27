// Asistente virtual "Ana": botón flotante con avatar, saludo automático, menú de opciones
// y conversación con /api/chatbot (reglas + preguntas frecuentes administrables).
import { api, esc, icono } from './api.js';

const AVATAR = '/img/asistente.svg';
const MENU = [
  ['file-pen-line', 'Radicar una PQRDS', '¿Cómo radico una PQRDS?'],
  ['search', 'Consultar mi radicado', '¿Cómo consulto mi radicado?'],
  ['circle-help', '¿Qué tipo de solicitud elijo?', '¿Qué tipo de solicitud elijo?'],
  ['clock', 'Tiempos de respuesta', '¿Cuánto tardan en responder?'],
  ['shield-check', 'Protección de mis datos', '¿Cómo protegen mis datos personales?'],
  ['calendar-check', 'Agendar una cita', '¿Cómo agendo una cita?'],
];
const formatoHora = new Intl.DateTimeFormat('es-CO', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Bogota' });
let raiz;
let ventana;
let mensajes;
let entrada;

// La preferencia "ya vi el saludo" es solo una comodidad: si el navegador no permite guardarla, no pasa nada
const leerSaludoVisto = () => { try { return sessionStorage.getItem('pqrds_saludo') === '1'; } catch { return false; } };
const guardarSaludoVisto = () => { try { sessionStorage.setItem('pqrds_saludo', '1'); } catch { /* sin almacenamiento */ } };

function hora() {
  return `<div class="msj-hora">${formatoHora.format(new Date())}</div>`;
}

function mensajeBot(html) {
  const fila = document.createElement('div');
  fila.className = 'fila-bot';
  fila.innerHTML = `<img src="${AVATAR}" alt=""><div><div class="msj msj-bot">${html}</div>${hora()}</div>`;
  mensajes.append(fila);
  mensajes.scrollTop = mensajes.scrollHeight;
  return fila.querySelector('.msj');
}

function mensajeUsuario(texto) {
  const m = document.createElement('div');
  m.style.alignSelf = 'flex-end';
  m.style.textAlign = 'right';
  m.innerHTML = `<div class="msj msj-usuario">${esc(texto)}</div>${hora()}`;
  mensajes.append(m);
  mensajes.scrollTop = mensajes.scrollHeight;
}

function sugerencias(lista) {
  if (!lista?.length) return;
  const caja = document.createElement('div');
  caja.className = 'sugerencias';
  caja.innerHTML = lista.map((s) => `<button type="button">${esc(s)}</button>`).join('');
  caja.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    caja.remove();
    enviar(b.textContent);
  });
  mensajes.append(caja);
  mensajes.scrollTop = mensajes.scrollHeight;
}

function menuPrincipal() {
  const m = mensajeBot(`¿En qué le puedo ayudar? Elija una opción o escriba su pregunta.
    <div class="menu-chat">${MENU.map(([ic, texto], i) => `<button type="button" data-opcion="${i}">${icono(ic)}${esc(texto)}</button>`).join('')}</div>`);
  m.addEventListener('click', (e) => {
    const b = e.target.closest('[data-opcion]');
    if (b) enviar(MENU[Number(b.dataset.opcion)][2], MENU[Number(b.dataset.opcion)][1]);
  });
}

async function enviar(pregunta, textoVisible = pregunta) {
  const mensaje = pregunta.trim();
  if (!mensaje) return;
  mensajeUsuario(textoVisible);
  entrada.value = '';
  const pensando = mensajeBot('<span class="escribiendo" aria-label="Ana está escribiendo"><i></i><i></i><i></i></span>');
  try {
    const r = await api('/api/chatbot', { method: 'POST', body: { mensaje } });
    // Solo se permiten enlaces internos del portal
    const accion = r.accion?.url?.startsWith('/') ? `<div><a class="boton boton-chico" href="${esc(r.accion.url)}">${esc(r.accion.texto)}</a></div>` : '';
    pensando.innerHTML = `${esc(r.respuesta)}${accion}`;
    sugerencias(r.sugerencias || ['Volver al menú']);
  } catch (err) {
    pensando.innerHTML = esc(err.message);
  }
  mensajes.scrollTop = mensajes.scrollHeight;
}

function quitarSaludo() {
  raiz.querySelector('.chatbot-saludo')?.remove();
  guardarSaludoVisto();
}

export function abrirChatbot() {
  if (!raiz) return;
  quitarSaludo();
  ventana.hidden = false;
  raiz.querySelector('.chatbot-boton').setAttribute('aria-expanded', 'true');
  entrada.focus();
}

function cerrar() {
  ventana.hidden = true;
  raiz.querySelector('.chatbot-boton').setAttribute('aria-expanded', 'false');
  raiz.querySelector('.chatbot-boton').focus();
}

export function iniciarChatbot() {
  raiz = document.createElement('div');
  raiz.className = 'chatbot';
  raiz.innerHTML = `
    <section class="chatbot-ventana" id="chatbot-ventana" aria-label="Asistente virtual" hidden>
      <div class="chatbot-cabecera">
        <img src="${AVATAR}" alt="">
        <div><strong>Ana, asistente virtual</strong><span>En línea</span></div>
        <button type="button" class="cerrar" aria-label="Cerrar asistente">${icono('x')}</button>
      </div>
      <div class="chatbot-mensajes" aria-live="polite"></div>
      <p class="chatbot-nota">No escriba su número de documento ni datos personales en el chat.</p>
      <form class="chatbot-form">
        <label for="chatbot-entrada" class="sr-only">Escriba su pregunta</label>
        <input id="chatbot-entrada" type="text" maxlength="500" autocomplete="off" placeholder="Escriba su pregunta…">
        <button type="submit" aria-label="Enviar">${icono('send')}</button>
      </form>
    </section>
    <button type="button" class="chatbot-boton" aria-expanded="false" aria-controls="chatbot-ventana">
      <span class="en-linea"><img src="${AVATAR}" alt=""></span><span>¿Necesita ayuda?</span>
    </button>`;
  document.body.append(raiz);

  ventana = raiz.querySelector('.chatbot-ventana');
  mensajes = raiz.querySelector('.chatbot-mensajes');
  entrada = raiz.querySelector('input');

  mensajeBot('¡Hola! Soy <strong>Ana</strong>, la asistente virtual de PQRDS de la Gobernación de Antioquia. Le oriento paso a paso.');
  menuPrincipal();

  raiz.querySelector('.chatbot-boton').addEventListener('click', () => (ventana.hidden ? abrirChatbot() : cerrar()));
  raiz.querySelector('.cerrar').addEventListener('click', cerrar);
  raiz.querySelector('form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (entrada.value.trim().toLowerCase() === 'volver al menú') return menuPrincipal();
    enviar(entrada.value);
  });
  mensajes.addEventListener('click', (e) => {
    const b = e.target.closest('.sugerencias button');
    if (b && b.textContent === 'Volver al menú') {
      e.stopImmediatePropagation();
      b.parentElement.remove();
      menuPrincipal();
    }
  }, true);
  ventana.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') cerrar();
  });

  // Saludo automático a los 3 segundos, una vez por sesión del navegador
  if (!leerSaludoVisto()) {
    setTimeout(() => {
      if (!ventana.hidden) return;
      const saludo = document.createElement('div');
      saludo.className = 'chatbot-saludo';
      saludo.setAttribute('role', 'status');
      saludo.innerHTML = `<strong>¡Hola! Soy Ana</strong>¿Le ayudo a radicar o consultar su solicitud?
        <button type="button" class="cerrar-saludo" aria-label="Cerrar saludo">${icono('x')}</button>`;
      saludo.addEventListener('click', (e) => {
        if (e.target.closest('.cerrar-saludo')) quitarSaludo();
        else abrirChatbot();
      });
      raiz.prepend(saludo);
    }, 3000);
  }
}
