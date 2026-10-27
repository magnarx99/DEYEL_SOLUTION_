// Bitácora de auditoría (solo administrador).
import { iniciarPanel } from './admin.js';
import { $, api, esc, fechaHora } from './api.js';

const ETIQUETAS = {
  CONSULTA_CEDULA: 'Consulta por cédula', BUSCAR_CEDULA: 'Búsqueda al radicar', VER_PQRDS: 'Ver solicitud',
  GESTIONAR_PQRDS: 'Gestionar solicitud', EXPORTAR_EXCEL: 'Exportar Excel', ACTUALIZAR_CIUDADANO: 'Actualizar ciudadano',
  RADICAR_EN_NOMBRE: 'Radicar en nombre', DESCARGAR_ADJUNTO: 'Descargar adjunto', CREAR_USUARIO: 'Crear usuario',
  ACTUALIZAR_USUARIO: 'Actualizar usuario', CREAR_CIUDADANO: 'Crear ciudadano',
};
let pagina = 1;

async function cargar() {
  const q = new URLSearchParams({ pagina, accion: $('#accion').value });
  const r = await api(`/api/admin/auditoria?${q}`);
  $('#filas').innerHTML = r.registros.map((a) => `
    <tr>
      <td style="white-space:nowrap">${esc(fechaHora(a.fecha))}</td>
      <td>${a.usuario ? `${esc(a.usuario)}<br><small class="texto-suave">${esc(a.rol)}</small>` : '<span class="texto-suave">Visitante</span>'}</td>
      <td>${esc(ETIQUETAS[a.accion] || a.accion)}</td>
      <td>${esc(a.detalle || '')}</td>
      <td><small class="texto-suave">${esc(a.ip || '')}</small></td>
    </tr>`).join('') || '<tr><td colspan="5" class="vacia">Sin registros.</td></tr>';
  const paginas = Math.max(1, Math.ceil(r.total / 25));
  $('#pagina-texto').textContent = `${r.total} registros. Página ${pagina} de ${paginas}`;
  $('#anterior').disabled = pagina <= 1;
  $('#siguiente').disabled = pagina >= paginas;
}

$('#accion').addEventListener('change', () => { pagina = 1; cargar(); });
$('#anterior').addEventListener('click', () => { pagina -= 1; cargar(); });
$('#siguiente').addEventListener('click', () => { pagina += 1; cargar(); });
iniciarPanel('auditoria').then((s) => { if (s.autenticado) cargar(); });
