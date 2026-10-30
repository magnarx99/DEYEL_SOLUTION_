// Flujo de radicación con reconocimiento por cédula (principio de una sola vez).
//  1. Identificación: se busca la cédula. Si existe, los datos se cargan solos; si no, se piden una sola vez.
//  2. Detalle del caso.  3. Revisión y radicación.  Luego: "Registrar otra solicitud" sin volver a digitar datos.
import { listo } from './layout.js';
import {
  $, $$, api, esc, icono, fecha, catalogos, llenarSelect, aviso, mostrarErrores, limpiarErrores, conCarga, tamano,
} from './api.js';
import {
  CEDULA_REGEX, soloDigitos, validarGrupo, validacionEnVivo, contador, bloqueIdentificacion, bloquePersonal,
  bloqueContacto, bloqueAutorizacion, cargarMunicipios, leerCiudadano, rellenar, configurarCita,
} from './formularios.js';

const form = $('#form-radicar');
const inputCedula = $('#cedula');
const resultado = $('#resultado');
const estadoBusqueda = $('#estado-busqueda');
const botonContinuar = $('#ir-paso-2');

const NOMBRES_PASO = { 1: 'Identificación', 2: 'Detalle del caso', 3: 'Revisar y radicar' };
const MAX_ARCHIVOS = 5;
const MAX_BYTES = 5 * 1024 * 1024;
const TIPOS_ARCHIVO = ['application/pdf', 'image/jpeg', 'image/png'];

const estado = {
  sesion: null,
  tipos: [],
  tipo: null,
  modo: null,          // completo | verificar | verificado | nuevo | anonimo
  ciudadano: null,     // datos mostrados (completos o enmascarados)
  token: null,         // token temporal de verificación para visitantes
  archivos: [],
  esPersonal: false,
};

// ---------------------------------------------------------------------
// Pasos
// ---------------------------------------------------------------------
function irAPaso(n) {
  for (const p of [1, 2, 3]) $(`#paso-${p}`).hidden = p !== n;
  $('#paso-actual').textContent = n;
  $('#paso-nombre').textContent = NOMBRES_PASO[n];
  $('#barra').style.width = `${(n / 3) * 100}%`;
  $('.pasos-barra').setAttribute('aria-valuenow', n);
  $$('.pasos-lista li').forEach((li) => {
    const k = Number(li.dataset.paso);
    li.className = k === n ? 'actual' : k < n ? 'hecho' : '';
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
  $(`#t-paso-${n}`).setAttribute('tabindex', '-1');
  $(`#t-paso-${n}`).focus({ preventScroll: true });
}

function permitirContinuar(si) {
  botonContinuar.disabled = !si;
}

// ---------------------------------------------------------------------
// Paso 1: reconocimiento por cédula
// ---------------------------------------------------------------------
const filaDato = (etiqueta, valor) => `<div><dt>${esc(etiqueta)}</dt><dd>${esc(valor || '—')}</dd></div>`;

function fichaHtml(c, { titulo, editable }) {
  return `
    <div class="ficha">
      <div class="ficha-cabecera">
        <h3>${icono('circle-check')}${esc(titulo)}</h3>
        ${editable ? `<button type="button" class="boton-texto" id="editar-datos">${icono('pencil')} Actualizar mis datos</button>` : ''}
      </div>
      <dl class="ficha-datos">
        ${filaDato('Nombre', `${c.nombres} ${c.apellidos}`)}
        ${c.cedula ? filaDato('Documento', `${c.tipo_documento} ${c.cedula}`) : ''}
        ${filaDato('Municipio', c.municipio)}
        ${filaDato('Celular', c.telefono)}
        ${filaDato('Correo', c.correo)}
        ${c.direccion !== undefined ? filaDato('Dirección', [c.direccion, c.barrio].filter(Boolean).join(', ')) : ''}
      </dl>
    </div>`;
}

/** Ciudadano reconocido con datos completos (titular con sesión o funcionario). */
function mostrarCompleto(c) {
  estado.modo = 'completo';
  estado.ciudadano = c;
  const propio = estado.sesion?.usuario?.rol === 'CIUDADANO';
  aviso(estadoBusqueda, propio
    ? 'Sus datos ya están cargados. Solo debe describir el nuevo caso.'
    : 'Ciudadano encontrado: sus datos ya están cargados.', 'exito');
  resultado.innerHTML = `${fichaHtml(c, { titulo: `${c.nombres} ${c.apellidos}`, editable: true })}<div id="edicion"></div>`;
  $('#editar-datos').addEventListener('click', abrirEdicion);
  permitirContinuar(true);
}

/** Permite corregir datos sin salir del flujo (PUT /api/ciudadanos/:id). */
function abrirEdicion() {
  const caja = $('#edicion');
  if (caja.innerHTML) {
    caja.innerHTML = '';
    return;
  }
  caja.innerHTML = `
    <div class="panel" style="margin-top:16px;box-shadow:none">
      <h3>Actualizar datos</h3>
      <p class="texto-suave texto-chico">El documento y su fecha de expedición no se pueden cambiar.</p>
      ${bloquePersonal()}<div style="height:16px"></div>${bloqueContacto()}
      <div id="error-edicion" style="margin-top:16px"></div>
      <div class="acciones">
        <button type="button" class="boton" id="guardar-datos" data-cargando="Guardando…">Guardar cambios</button>
        <button type="button" class="boton boton-secundario" id="cancelar-edicion">Cancelar</button>
      </div>
    </div>`;
  cargarMunicipios(caja).then(() => rellenar(form, estado.ciudadano));
  soloDigitos($('#f-telefono'));
  permitirContinuar(false);
  $('#cancelar-edicion').addEventListener('click', () => {
    caja.innerHTML = '';
    permitirContinuar(true);
  });
  $('#guardar-datos').addEventListener('click', async (e) => {
    if (!validarGrupo(caja)) return;
    const datos = leerCiudadano(form);
    try {
      const r = await conCarga(e.currentTarget, () => api(`/api/ciudadanos/${estado.ciudadano.id_ciudadano}`, { method: 'PUT', body: datos }));
      mostrarCompleto(r.ciudadano);
      aviso(estadoBusqueda, 'Datos actualizados. Ya puede continuar con su solicitud.', 'exito');
    } catch (err) {
      mostrarErrores(caja, err.detalles);
      aviso($('#error-edicion'), esc(err.message), 'error');
    }
  });
}

/** Visitante sin sesión: se muestran datos enmascarados y se pide confirmar identidad. */
function mostrarVerificacion(c) {
  estado.modo = 'verificar';
  estado.ciudadano = c;
  aviso(estadoBusqueda, 'Encontramos un registro con esta cédula. Por seguridad, solo mostramos parte de los datos.', 'info');
  resultado.innerHTML = `
    ${fichaHtml(c, { titulo: 'Registro encontrado', editable: false })}
    <div class="panel" style="margin-top:16px;box-shadow:none" id="caja-verificar">
      <h3>Confirme que es usted</h3>
      <p class="texto-suave texto-chico">Responda un dato que solo usted conoce. Así protegemos su información (Ley 1581 de 2012).</p>
      <div class="opciones" role="radiogroup" aria-label="Dato para confirmar identidad" style="margin-bottom:16px">
        <label class="opcion"><input type="radio" name="metodo_verificacion" value="fecha" checked> Fecha de expedición de la cédula</label>
        ${c.tiene_correo ? '<label class="opcion"><input type="radio" name="metodo_verificacion" value="correo"> Correo registrado</label>' : ''}
      </div>
      <div class="cedula-caja">
        <div class="campo">
          <label for="dato-verificacion" id="etiqueta-verificacion">Fecha de expedición</label>
          <input id="dato-verificacion" type="date" autocomplete="off">
        </div>
        <button type="button" class="boton" id="verificar" data-cargando="Verificando…">Confirmar</button>
      </div>
      <div id="error-verificacion" style="margin-top:12px"></div>
      <p class="texto-chico texto-suave" style="margin:16px 0 0">¿Tiene cuenta? <a href="/login.html?volver=${encodeURIComponent(location.pathname + location.search)}">Inicie sesión</a> para ver sus datos completos.</p>
    </div>`;
  const dato = $('#dato-verificacion');
  $$('input[name="metodo_verificacion"]').forEach((r) => r.addEventListener('change', () => {
    const porCorreo = r.value === 'correo' && r.checked;
    dato.type = porCorreo ? 'email' : 'date';
    dato.value = '';
    $('#etiqueta-verificacion').textContent = porCorreo ? 'Correo registrado' : 'Fecha de expedición';
  }));
  $('#verificar').addEventListener('click', async (e) => {
    const metodo = $('input[name="metodo_verificacion"]:checked').value;
    if (!dato.value) {
      aviso($('#error-verificacion'), 'Escriba el dato solicitado.', 'error');
      dato.focus();
      return;
    }
    try {
      const r = await conCarga(e.currentTarget, () => api(`/api/ciudadanos/${inputCedula.value}/verificar`, {
        method: 'POST', body: metodo === 'correo' ? { correo: dato.value } : { fecha_expedicion: dato.value },
      }));
      estado.token = r.token;
      estado.modo = 'verificado';
      aviso(estadoBusqueda, 'Identidad confirmada. Sus datos se usarán sin necesidad de escribirlos de nuevo.', 'exito');
      resultado.innerHTML = fichaHtml(r.ciudadano, { titulo: 'Identidad confirmada', editable: false });
      permitirContinuar(true);
      botonContinuar.focus();
    } catch (err) {
      aviso($('#error-verificacion'), esc(err.message), 'error');
    }
  });
  permitirContinuar(false);
}

/** Primera vez: se piden los datos personales una sola vez. */
function mostrarFormularioNuevo() {
  estado.modo = 'nuevo';
  estado.ciudadano = null;
  aviso(estadoBusqueda, estado.esPersonal
    ? 'Esta cédula no está registrada. Registre los datos del ciudadano una sola vez.'
    : 'Es su primera solicitud: complete sus datos una sola vez. La próxima vez solo tendrá que escribir su cédula.', 'info');
  resultado.innerHTML = `
    <p class="leyenda-obligatorio" style="margin-top:16px">Los campos marcados con <span class="obligatorio">*</span> son obligatorios.</p>
    <fieldset><legend>Identificación</legend>${bloqueIdentificacion({ sinCedula: true })}</fieldset>
    <fieldset><legend>Datos personales</legend>${bloquePersonal()}</fieldset>
    <fieldset><legend>Ubicación y contacto</legend>${bloqueContacto()}</fieldset>
    <fieldset><legend>Autorización</legend>${bloqueAutorizacion()}</fieldset>`;
  cargarMunicipios(resultado);
  soloDigitos($('#f-telefono'));
  soloDigitos($('#f-telefono_fijo'));
  permitirContinuar(true);
}

async function buscarCedula() {
  const cedula = inputCedula.value.trim();
  const caja = inputCedula.closest('.campo');
  if (!CEDULA_REGEX.test(cedula)) {
    caja.classList.add('con-error');
    inputCedula.focus();
    return;
  }
  caja.classList.remove('con-error');
  try {
    const r = await conCarga($('#buscar'), () => api(`/api/ciudadanos/${cedula}`));
    sessionStorage.setItem('pqrds_cedula', cedula);
    if (r.completo) mostrarCompleto(r.ciudadano);
    else mostrarVerificacion(r.ciudadano);
  } catch (err) {
    if (err.status === 404) mostrarFormularioNuevo();
    else aviso(estadoBusqueda, esc(err.message), 'error');
  }
}

function reiniciarIdentificacion() {
  estado.modo = null;
  estado.token = null;
  estado.ciudadano = null;
  resultado.innerHTML = '';
  estadoBusqueda.innerHTML = '';
  permitirContinuar(false);
}

function alternarAnonima() {
  const anonima = $('#anonima').checked;
  $('#caja-busqueda').hidden = anonima;
  $('#caja-medio').hidden = anonima;
  $('#f-tipo').disabled = anonima;
  if (anonima) {
    reiniciarIdentificacion();
    estado.modo = 'anonimo';
    aviso(estadoBusqueda, 'Su denuncia será anónima. Al radicar recibirá un código para consultar el estado: guárdelo, porque no podremos contactarlo.', 'alerta');
    permitirContinuar(true);
  } else {
    reiniciarIdentificacion();
    if (inputCedula.value) buscarCedula();
  }
}

// ---------------------------------------------------------------------
// Paso 2: detalle del caso
// ---------------------------------------------------------------------
function tieneCorreo() {
  if (estado.modo === 'nuevo') return Boolean($('#f-correo')?.value.trim());
  if (estado.modo === 'completo') return Boolean(estado.ciudadano?.correo);
  if (estado.modo === 'verificado' || estado.modo === 'verificar') return Boolean(estado.ciudadano?.tiene_correo || estado.ciudadano?.correo);
  return false;
}

function prepararPaso2() {
  const nombre = estado.modo === 'anonimo'
    ? 'Denuncia anónima'
    : estado.modo === 'nuevo'
      ? `${$('#f-nombres').value} ${$('#f-apellidos').value}`
      : `${estado.ciudadano.nombres} ${estado.ciudadano.apellidos}`;
  aviso($('#resumen-identidad'), estado.modo === 'anonimo'
    ? 'Está presentando una <strong>denuncia anónima</strong>.'
    : `Solicitud a nombre de <strong>${esc(nombre)}</strong>, cédula terminada en ${esc(inputCedula.value.slice(-4))}.`);
  $('#resumen-identidad').style.marginBottom = '24px';

  const correo = form.querySelector('input[name="medio_respuesta"][value="CORREO"]');
  const correoDisponible = tieneCorreo();
  correo.disabled = !correoDisponible;
  correo.closest('.opcion').title = correoDisponible ? '' : 'No tiene un correo registrado';
  if (!correoDisponible) form.querySelector('input[name="medio_respuesta"][value="FISICO"]').checked = true;
}

function actualizarTipo() {
  const t = estado.tipos.find((x) => x.codigo === $('#f-tipo').value);
  estado.tipo = t;
  $('#plazo-tipo').textContent = t ? `Respuesta en máximo ${t.dias_habiles_respuesta} días hábiles.` : '';
  $('#caja-cita').hidden = t?.codigo !== 'CITA';
  $('#imagen-tipo').src = t?.codigo === 'CITA' ? '/img/ilustracion-cita.svg' : '/img/ilustracion-radicar.svg';
  $('#titulo').textContent = t ? `Radicar: ${t.nombre}` : 'Radicar solicitud';
  document.title = `${t ? t.nombre : 'Radicar solicitud'} | PQRDS Gobernación de Antioquia`;
}

// --- Adjuntos ---
function pintarArchivos() {
  $('#lista-archivos').innerHTML = estado.archivos.map((a, i) => `
    <li>${icono(a.type === 'application/pdf' ? 'file-search' : 'paperclip')}
      <span>${esc(a.name)}</span><small class="texto-suave">${tamano(a.size)}</small>
      <button type="button" class="boton-texto" data-quitar="${i}" aria-label="Quitar ${esc(a.name)}">${icono('trash-2')}</button>
    </li>`).join('');
}

function agregarArchivos(lista) {
  const errores = [];
  for (const a of lista) {
    if (estado.archivos.length >= MAX_ARCHIVOS) { errores.push(`Solo puede adjuntar ${MAX_ARCHIVOS} archivos.`); break; }
    if (!TIPOS_ARCHIVO.includes(a.type)) { errores.push(`"${a.name}" no es PDF, JPG o PNG.`); continue; }
    if (a.size > MAX_BYTES) { errores.push(`"${a.name}" pesa más de 5 MB.`); continue; }
    if (estado.archivos.some((x) => x.name === a.name && x.size === a.size)) continue;
    estado.archivos.push(a);
  }
  aviso($('#error-archivos'), errores.map(esc).join('<br>'), 'error');
  pintarArchivos();
}

function configurarAdjuntos() {
  const zona = $('#zona-archivos');
  const input = $('#archivos');
  zona.addEventListener('click', () => input.click());
  zona.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => { agregarArchivos([...input.files]); input.value = ''; });
  ['dragenter', 'dragover'].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add('arrastrando'); }));
  ['dragleave', 'drop'].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove('arrastrando'); }));
  zona.addEventListener('drop', (e) => agregarArchivos([...e.dataTransfer.files]));
  $('#lista-archivos').addEventListener('click', (e) => {
    const b = e.target.closest('[data-quitar]');
    if (!b) return;
    estado.archivos.splice(Number(b.dataset.quitar), 1);
    pintarArchivos();
  });
}

// ---------------------------------------------------------------------
// Paso 3: revisión y envío
// ---------------------------------------------------------------------
function textoSeleccionado(select) {
  return select.selectedOptions[0]?.textContent || '—';
}

function pintarResumen() {
  const medio = form.querySelector('input[name="medio_respuesta"]:checked')?.value;
  const filas = [
    ['Solicitante', $('#resumen-identidad').textContent.trim()],
    ['Tipo de solicitud', estado.tipo?.nombre],
    ['Dependencia', textoSeleccionado($('#f-id_dependencia'))],
    ['Municipio del hecho', $('#f-municipio_hecho').value],
  ];
  if (estado.tipo?.codigo === 'CITA') {
    filas.push(['Cita', `${fecha($('#f-fecha_cita_preferida').value)}, ${form.querySelector('input[name="modalidad_cita"]:checked')?.value === 'VIRTUAL' ? 'virtual' : 'presencial'}`]);
  }
  filas.push(['Asunto', $('#f-asunto').value], ['Descripción', $('#f-descripcion').value]);
  filas.push(['Adjuntos', estado.archivos.length ? estado.archivos.map((a) => a.name).join('\n') : 'Ninguno']);
  if (estado.modo !== 'anonimo') filas.push(['Respuesta por', medio === 'CORREO' ? 'Correo electrónico' : 'Dirección física']);
  if (estado.esPersonal) filas.push(['Canal', textoSeleccionado($('#f-canal'))]);
  filas.push(['Plazo de respuesta', `${estado.tipo?.dias_habiles_respuesta} días hábiles desde mañana`]);
  $('#resumen').innerHTML = filas.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
}

function construirEnvio() {
  const f = new FormData();
  const v = (n) => form.elements[n]?.value?.trim?.() ?? '';
  f.append('tipo', $('#f-tipo').value);
  if (v('id_dependencia')) f.append('id_dependencia', v('id_dependencia'));
  f.append('municipio_hecho', v('municipio_hecho'));
  f.append('asunto', v('asunto'));
  f.append('descripcion', v('descripcion'));
  if (estado.tipo?.codigo === 'CITA') {
    f.append('fecha_cita_preferida', v('fecha_cita_preferida'));
    f.append('modalidad_cita', form.querySelector('input[name="modalidad_cita"]:checked')?.value || '');
  }
  if (estado.modo === 'anonimo') {
    f.append('anonima', 'true');
  } else {
    f.append('medio_respuesta', form.querySelector('input[name="medio_respuesta"]:checked')?.value || 'FISICO');
    if (estado.esPersonal) {
      f.append('cedula', inputCedula.value);
      f.append('canal', v('canal'));
    }
    if (estado.modo === 'verificado') f.append('token_verificacion', estado.token);
    if (estado.modo === 'nuevo') f.append('ciudadano', JSON.stringify({ ...leerCiudadano(form), cedula: inputCedula.value }));
  }
  estado.archivos.forEach((a) => f.append('adjuntos', a, a.name));
  return f;
}

async function radicar(e) {
  e.preventDefault();
  const envio = $('#error-envio');
  envio.innerHTML = '';
  limpiarErrores(form);
  try {
    const r = await conCarga($('#radicar'), () => api('/api/pqrds', { method: 'POST', form: construirEnvio() }));
    mostrarConfirmacion(r);
  } catch (err) {
    aviso(envio, esc(err.message), 'error');
    const campos = Object.keys(err.detalles || {});
    if (campos.some((c) => $(`#paso-1 [name="${c}"]`))) { irAPaso(1); mostrarErrores($('#paso-1'), err.detalles); }
    else if (campos.length) { irAPaso(2); mostrarErrores($('#paso-2'), err.detalles); }
  }
}

function mostrarConfirmacion(r) {
  const s = estado.sesion;
  const ciudadanoConCuenta = s?.autenticado && s.usuario.rol === 'CIUDADANO';
  form.hidden = true;
  $('#pasos').hidden = true;
  const conf = $('#confirmacion');
  conf.hidden = false;
  conf.innerHTML = `
    <div class="sello">${icono('circle-check')}</div>
    <h2 id="t-confirmacion">Su ${esc(r.tipo.toLowerCase())} fue radicada</h2>
    <p class="texto-suave">Guarde este número para consultar el estado de su solicitud.</p>
    <div class="numero-radicado">${esc(r.radicado)}</div>
    <div class="datos-confirmacion">
      <div><span>Fecha de radicación</span><strong>${esc(fecha(r.fecha_radicacion))}</strong></div>
      <div><span>Fecha límite de respuesta</span><strong>${esc(fecha(r.fecha_limite))}</strong></div>
      <div><span>Adjuntos recibidos</span><strong>${r.adjuntos}</strong></div>
    </div>
    <div style="max-width:560px;margin:0 auto;text-align:left" id="avisos-confirmacion"></div>
    <div class="acciones no-imprimir">
      <button type="button" class="boton" id="otra">${icono('plus')}Registrar otra solicitud</button>
      <button type="button" class="boton boton-secundario" id="imprimir">${icono('printer')}Imprimir comprobante</button>
      ${ciudadanoConCuenta
        ? `<a class="boton boton-secundario" href="/mis-solicitudes.html">${icono('inbox')}Ir a mis solicitudes</a>`
        : `<a class="boton boton-secundario" href="/seguimiento.html">${icono('search')}Consultar radicado</a>`}
    </div>`;

  const avisos = [];
  if (r.codigo_anonimo) {
    avisos.push(`<div class="aviso aviso-alerta" style="margin-top:16px">${icono('lock')}<div>Código de consulta de su denuncia anónima: <strong style="font-size:1.25rem;letter-spacing:.08em">${esc(r.codigo_anonimo)}</strong><br>Anótelo ahora. Es la única forma de consultar el estado y no se puede recuperar.</div></div>`);
  }
  if (r.ciudadano_nuevo) {
    avisos.push(`<div class="aviso aviso-exito" style="margin-top:16px">${icono('shield-check')}<div>Sus datos quedaron registrados. La próxima vez solo tendrá que escribir su número de cédula.</div></div>`);
  }
  if (!s?.autenticado && !r.codigo_anonimo) {
    avisos.push(`<div class="aviso" style="margin-top:16px">${icono('user-plus')}<div>¿Quiere ver todas sus solicitudes en un solo lugar? <a href="/registro.html">Cree una cuenta</a> con la misma cédula.</div></div>`);
  }
  $('#avisos-confirmacion').innerHTML = avisos.join('');

  // Desde ahora el ciudadano queda reconocido: la siguiente solicitud no pide sus datos otra vez
  if (estado.modo === 'nuevo') {
    const datos = { ...leerCiudadano(form), cedula: inputCedula.value };
    estado.ciudadano = { ...datos, tiene_correo: Boolean(datos.correo) };
    estado.modo = r.token_verificacion ? 'verificado' : 'completo';
    resultado.innerHTML = fichaHtml(estado.ciudadano, { titulo: 'Datos registrados', editable: false });
    aviso(estadoBusqueda, 'Sus datos quedaron registrados.', 'exito');
  }
  if (r.token_verificacion) estado.token = r.token_verificacion;
  $('#otra').addEventListener('click', registrarOtra);
  $('#imprimir').addEventListener('click', () => window.print());
  conf.focus();
}

/** Nueva solicitud para el mismo ciudadano: no vuelve a digitar sus datos. */
function registrarOtra() {
  ['asunto', 'descripcion', 'fecha_cita_preferida'].forEach((n) => { form.elements[n].value = ''; });
  form.querySelectorAll('input[name="modalidad_cita"]').forEach((r) => { r.checked = false; });
  estado.archivos = [];
  pintarArchivos();
  $('#error-envio').innerHTML = '';
  $('#confirmacion').hidden = true;
  form.hidden = false;
  $('#pasos').hidden = false;
  $('#cont-asunto').textContent = '0 / 150';
  $('#cont-descripcion').textContent = '0 / 3.000';
  prepararPaso2();
  irAPaso(2);
}

// ---------------------------------------------------------------------
// Inicio
// ---------------------------------------------------------------------
(async () => {
  const [s, cat] = await Promise.all([listo, catalogos()]);
  estado.sesion = s;
  estado.tipos = cat.tipos;
  estado.esPersonal = s.autenticado && ['FUNCIONARIO', 'ADMIN'].includes(s.usuario.rol);

  const params = new URLSearchParams(location.search);
  const tipo = cat.tipos.find((t) => t.codigo === params.get('tipo'));
  if (!tipo) {
    location.replace('/pqrds.html');
    return;
  }
  llenarSelect($('#f-tipo'), cat.tipos, { vacio: null, valor: (t) => t.codigo, texto: (t) => t.nombre });
  $('#f-tipo').value = tipo.codigo;
  llenarSelect($('#f-id_dependencia'), cat.dependencias, { vacio: 'No sé, que la entidad la asigne', valor: (d) => d.id_dependencia, texto: (d) => d.nombre });
  llenarSelect($('#f-municipio_hecho'), cat.municipios, { vacio: 'Seleccione el municipio' });
  configurarCita(cat.cita);
  $('#f-fecha_cita_preferida').min = cat.cita.fecha_minima;
  $('#ayuda-cita').textContent = `La entidad tiene hasta ${cat.cita.dias_habiles} días hábiles para responder, por eso la cita `
    + `puede ser desde el ${fecha(cat.cita.fecha_minima)} (solo días hábiles). La dependencia le confirmará la fecha y la hora.`;
  actualizarTipo();

  contador($('#f-asunto'), $('#cont-asunto'));
  contador($('#f-descripcion'), $('#cont-descripcion'));
  soloDigitos(inputCedula);
  configurarAdjuntos();
  validacionEnVivo(form);

  if (tipo.permite_anonimo && !estado.esPersonal) {
    $('#caja-anonima').classList.remove('oculto');
    $('#anonima').addEventListener('change', alternarAnonima);
  }
  if (estado.esPersonal) {
    $('#caja-canal').classList.remove('oculto');
    $('#desc-paso-1').textContent = 'Busque al ciudadano por su número de cédula. Si ya está registrado, sus datos se cargan automáticamente; si no, regístrelos una sola vez.';
    $('#subtitulo').textContent = 'Está radicando en nombre de un ciudadano. Esta acción queda registrada en la bitácora de auditoría.';
  }

  $('#buscar').addEventListener('click', buscarCedula);
  inputCedula.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); buscarCedula(); }
  });
  inputCedula.addEventListener('blur', () => {
    if (CEDULA_REGEX.test(inputCedula.value) && !estado.modo && !inputCedula.readOnly) buscarCedula();
  });
  inputCedula.addEventListener('input', () => {
    if (estado.modo && estado.modo !== 'anonimo') reiniciarIdentificacion();
    inputCedula.closest('.campo').classList.remove('con-error');
  });

  botonContinuar.addEventListener('click', () => {
    if (estado.modo === 'nuevo' && !validarGrupo(resultado)) return;
    prepararPaso2();
    irAPaso(2);
  });
  $('#f-tipo').addEventListener('change', actualizarTipo);
  $('#ir-paso-3').addEventListener('click', () => {
    if (!validarGrupo($('#paso-2'))) return;
    pintarResumen();
    irAPaso(3);
  });
  $$('[data-ir]').forEach((b) => b.addEventListener('click', () => irAPaso(Number(b.dataset.ir))));
  form.addEventListener('submit', radicar);
  irAPaso(1);
  window.scrollTo(0, 0);

  // Ciudadano con sesión: su cédula se carga sola y no necesita buscar
  if (s.autenticado && s.usuario.rol === 'CIUDADANO' && s.ciudadano) {
    inputCedula.value = s.ciudadano.cedula;
    inputCedula.readOnly = true;
    $('#buscar').hidden = true;
    mostrarCompleto(s.ciudadano);
  } else if (params.get('anonima') === '1' && tipo.permite_anonimo && !estado.esPersonal) {
    $('#anonima').checked = true;
    alternarAnonima();
  } else if (estado.esPersonal && sessionStorage.getItem('pqrds_cedula_funcionario')) {
    // Viene de "Radicar en su nombre" en la consulta por cédula
    inputCedula.value = sessionStorage.getItem('pqrds_cedula_funcionario');
    sessionStorage.removeItem('pqrds_cedula_funcionario');
    buscarCedula();
  } else if (sessionStorage.getItem('pqrds_cedula') && !estado.esPersonal) {
    inputCedula.value = sessionStorage.getItem('pqrds_cedula');
    buscarCedula();
  } else {
    inputCedula.focus();
  }
})();
