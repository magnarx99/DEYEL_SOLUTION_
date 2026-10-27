"""Exportación a Excel (.xlsx) sin librerías.

Un archivo .xlsx es en realidad un archivo ZIP con varios archivos XML adentro (formato
Office Open XML). Aquí se arman esos XML con texto y se empaquetan con zipfile.
El libro tiene dos hojas: "PQRDS" y "Ciudadanos", con encabezado azul, filtros y
la primera fila inmovilizada.
"""
import io
import zipfile
from xml.sax.saxutils import escape

from nucleo import bd

ETIQUETA_ESTADO = {'RADICADA': 'Radicada', 'EN_TRAMITE': 'En trámite', 'RESPONDIDA': 'Respondida',
                   'CERRADA': 'Cerrada', 'TRASLADADA': 'Trasladada'}
ETIQUETA_SEMAFORO = {'ATENDIDA': 'Atendida', 'VENCIDA': 'Vencida', 'POR_VENCER': 'Por vencer', 'A_TIEMPO': 'A tiempo'}


def _letra_columna(n):
    """1 -> A, 2 -> B, ..., 27 -> AA"""
    letras = ''
    while n:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _fecha_hora(texto):
    """'2026-10-26T13:15:00-05:00' -> '2026-10-26 13:15'"""
    return texto[:16].replace('T', ' ') if texto else ''


def _hoja(columnas, filas):
    """XML de una hoja. columnas = [(titulo, ancho)], filas = listas de valores."""
    ultima = _letra_columna(len(columnas))
    xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
           '<cols>']
    for i, (_, ancho) in enumerate(columnas, 1):
        xml.append(f'<col min="{i}" max="{i}" width="{ancho}" customWidth="1"/>')
    xml.append('</cols><sheetData>')
    todas = [[t for t, _ in columnas]] + filas
    for r, fila in enumerate(todas, 1):
        estilo = 1 if r == 1 else (2 if r % 2 == 0 else 0)   # 1 = encabezado, 2 = fila sombreada
        xml.append(f'<row r="{r}">')
        for c, valor in enumerate(fila, 1):
            ref = f'{_letra_columna(c)}{r}'
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                xml.append(f'<c r="{ref}" s="{estilo}"><v>{valor}</v></c>')
            else:
                texto = escape('' if valor is None else str(valor))
                xml.append(f'<c r="{ref}" s="{estilo}" t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>')
        xml.append('</row>')
    xml.append(f'</sheetData><autoFilter ref="A1:{ultima}{max(len(todas), 1)}"/></worksheet>')
    return ''.join(xml)


ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2B5C8A"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEEF5FC"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def generar_libro(registros):
    """Devuelve los bytes del archivo .xlsx con las PQRDS recibidas y sus ciudadanos."""
    columnas_pqrds = [('Radicado', 20), ('Fecha de radicación', 18), ('Tipo', 24), ('Dependencia', 38), ('Estado', 14),
                      ('Fecha límite', 13), ('Semáforo', 12), ('Canal', 12), ('Asunto', 45), ('Municipio del hecho', 22),
                      ('Cédula', 14), ('Nombre completo', 32), ('Municipio de residencia', 22), ('Teléfono', 14),
                      ('Correo', 30), ('Funcionario asignado', 28), ('Fecha de respuesta', 18)]
    filas_pqrds = []
    for r in registros:
        anonima = r['es_anonima']
        filas_pqrds.append([
            r['radicado'], _fecha_hora(r['fecha_radicacion']), r['tipo'], r['dependencia'] or 'Por asignar',
            ETIQUETA_ESTADO.get(r['estado'], r['estado']), r['fecha_limite'], ETIQUETA_SEMAFORO.get(r['semaforo'], ''),
            r['canal'], r['asunto'], r['municipio_hecho'], 'ANÓNIMA' if anonima else r['cedula'],
            'Denuncia anónima' if anonima else f"{r['nombres']} {r['apellidos']}", r['municipio'] or '',
            r['telefono'] or '', r['correo'] or '', r['funcionario'] or '', _fecha_hora(r['fecha_respuesta'])])

    # Hoja de ciudadanos: solo los que aparecen en las PQRDS exportadas
    ids = sorted({r['id_ciudadano'] for r in registros if r['id_ciudadano']})
    ciudadanos = []
    if ids:
        marcas = ','.join('?' * len(ids))
        ciudadanos = bd.consultar(f"""SELECT c.*, COUNT(p.id_pqrds) AS total_pqrds
                                        FROM ciudadano c LEFT JOIN pqrds p ON p.id_ciudadano = c.id_ciudadano
                                       WHERE c.id_ciudadano IN ({marcas})
                                       GROUP BY c.id_ciudadano ORDER BY c.apellidos, c.nombres""", ids)
    columnas_ciu = [('Tipo doc.', 10), ('Cédula', 14), ('Nombres', 22), ('Apellidos', 22), ('Fecha de nacimiento', 18),
                    ('Sexo', 13), ('Grupo poblacional', 24), ('Municipio', 22), ('Barrio / vereda', 20), ('Dirección', 30),
                    ('Celular', 14), ('Correo', 30), ('Total PQRDS', 12), ('Registrado desde', 18)]
    filas_ciu = [[c['tipo_documento'], c['cedula'], c['nombres'], c['apellidos'], c['fecha_nacimiento'] or '', c['sexo'] or '',
                  c['grupo_poblacional'] or '', c['municipio'], c['barrio'] or '', c['direccion'] or '', c['telefono'],
                  c['correo'] or '', c['total_pqrds'], c['fecha_creacion'][:10]] for c in ciudadanos]

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   '</Types>')
        z.writestr('_rels/.rels',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr('xl/workbook.xml',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="PQRDS" sheetId="1" r:id="rId1"/><sheet name="Ciudadanos" sheetId="2" r:id="rId2"/></sheets>'
                   '</workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
                   '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '</Relationships>')
        z.writestr('xl/styles.xml', ESTILOS)
        z.writestr('xl/worksheets/sheet1.xml', _hoja(columnas_pqrds, filas_pqrds))
        z.writestr('xl/worksheets/sheet2.xml', _hoja(columnas_ciu, filas_ciu))
    return salida.getvalue()
