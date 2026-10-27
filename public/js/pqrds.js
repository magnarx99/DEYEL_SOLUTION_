// Menú de tipos de solicitud, con buscador, ejemplos y término legal de respuesta.
import { listo } from './layout.js';
import { $, catalogos, esc, icono, aviso } from './api.js';
import { abrirChatbot } from './chatbot.js';

const lista = $('#lista-tipos');
const filtro = $('#filtro');
let tipos = [];

const normalizar = (t) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

function pintar() {
  const q = normalizar(filtro.value.trim());
  const visibles = tipos.filter((t) => !q || normalizar(`${t.nombre} ${t.descripcion} ${t.ejemplo}`).includes(q));
  if (!visibles.length) {
    lista.innerHTML = `<li class="sin-resultados">No encontramos un tipo de solicitud con "${esc(filtro.value)}".
      <button type="button" class="boton-texto" id="preguntar">Pregúntele al asistente</button></li>`;
    $('#preguntar').addEventListener('click', abrirChatbot);
    return;
  }
  lista.innerHTML = visibles.map((t) => `
    <li class="tipo">
      <div class="tipo-icono">${icono(t.icono)}</div>
      <div>
        <h2>${esc(t.nombre)}
          <button type="button" class="ayuda-tipo" aria-expanded="false" aria-controls="ej-${t.codigo}" aria-label="Ver un ejemplo de ${esc(t.nombre)}">${icono('circle-help')}</button>
        </h2>
        <p>${esc(t.descripcion)}</p>
        <div class="tipo-plazo">${icono('clock')}Respuesta en máximo ${t.dias_habiles_respuesta} días hábiles${t.permite_anonimo ? '. Puede ser anónima' : ''}</div>
      </div>
      <div class="tipo-acciones">
        <a class="boton" href="/radicar.html?tipo=${encodeURIComponent(t.codigo)}">${esc(t.texto_boton)}</a>
      </div>
      <div class="ejemplo-tipo" id="ej-${t.codigo}" hidden><strong>Ejemplo:</strong> ${esc(t.ejemplo)}</div>
    </li>`).join('');
}

lista.addEventListener('click', (e) => {
  const b = e.target.closest('.ayuda-tipo');
  if (!b) return;
  const ej = document.getElementById(b.getAttribute('aria-controls'));
  ej.hidden = !ej.hidden;
  b.setAttribute('aria-expanded', String(!ej.hidden));
});
filtro.addEventListener('input', pintar);

(async () => {
  try {
    tipos = (await catalogos()).tipos;
    pintar();
  } catch (err) {
    lista.innerHTML = `<li class="sin-resultados">${esc(err.message)}</li>`;
  }
  const s = await listo;
  const cedula = sessionStorage.getItem('pqrds_cedula');
  if (cedula && !(s.autenticado && s.usuario.rol === 'CIUDADANO')) {
    aviso($('#aviso-cedula'), `Continuará con la cédula terminada en <strong>${esc(cedula.slice(-4))}</strong>. Elija el tipo de solicitud.`);
    $('#aviso-cedula').style.marginBottom = '20px';
  }
})();
