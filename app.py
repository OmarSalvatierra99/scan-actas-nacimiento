import re
import os
import base64
import tempfile
import gc
from io import BytesIO
from threading import RLock
from datetime import datetime
from functools import wraps
import time

import openpyxl
from openpyxl import Workbook
from flask import Flask, render_template, request, jsonify, send_file
import cv2
import numpy as np
import fitz  # PyMuPDF

app = Flask(__name__)

# ===== Configuración de límites =====
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB por archivo
MAX_PDF_PAGES = 100  # Máximo de páginas por PDF para procesamiento
ALLOWED_EXTENSIONS = {'pdf'}

# ===== Config =====
ENCABEZADOS = [
    'Tomo', 'Libro', 'Foja', 'Acta', 'Entidad', 'Municipio',
    'CURP', 'Registrado', 'Padre', 'Madre', 'FechaNacimiento',
    'Sexo', 'FechaRegistro', 'Oficial', 'Folio', 'FechaEscaneo'
]

# Registros en memoria (no se guardan en disco)
REGISTROS = []
_LOCK = RLock()


# ===== Utilidades de validación =====
def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_pdf_file(file):
    """Valida tamaño y formato del archivo PDF."""
    if not file:
        return False, "No se recibió archivo"

    if not allowed_file(file.filename):
        return False, "El archivo debe ser un PDF"

    # Leer el archivo para verificar tamaño
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return False, f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE // (1024*1024)} MB"

    if file_size == 0:
        return False, "El archivo está vacío"

    return True, "OK"


def cleanup_memory():
    """Fuerza la liberación de memoria."""
    gc.collect()


# ===== Utilidades de procesamiento =====
def normalizar_clave(raw_key):
    mapeo_claves = {
        'padre1': 'Padre',
        'padre2': 'Madre',
        'registrado': 'Registrado',
        'curp': 'CURP',
        'tomo': 'Tomo',
        'libro': 'Libro',
        'foja': 'Foja',
        'acta': 'Acta',
        'entidad': 'Entidad',
        'municipio': 'Municipio',
        'fechanacimiento': 'FechaNacimiento',
        'sexo': 'Sexo',
        'fechaimpresion': 'FechaRegistro',
        'impreso en': 'Oficial',
        'cadena': 'Folio'
    }
    return mapeo_claves.get(
        raw_key.lower().replace(' ', '').replace('í', 'i'),
        raw_key
    )


def parsear_qr(data):
    data = re.sub(r'([^,])CURP', r'\1,CURP', data, flags=re.IGNORECASE)
    data = re.sub(r'([^,])Padre', r'\1,Padre', data, flags=re.IGNORECASE)
    patron = re.compile(r'(\b[\w\s]+?):(.+?)(?=\s*[\w\s]+:|$)', re.IGNORECASE)
    matches = patron.findall(data)
    registro = {}
    for k, v in matches:
        clave_normalizada = normalizar_clave(k.strip())
        registro[clave_normalizada] = v.strip(' ,;')
    registro['FechaEscaneo'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return registro


def _clave_registro(registro):
    return registro.get('Folio') or registro.get('CURP')


def guardar_registro(registro):
    """Guarda en memoria. Evita duplicados por Folio o CURP."""
    try:
        clave = _clave_registro(registro)
        if not clave:
            return False, "Error: No se encontró Folio ni CURP en el código QR."

        with _LOCK:
            for r in REGISTROS:
                if (registro.get('Folio') and r.get('Folio') == registro.get('Folio')) or \
                   (registro.get('CURP') and r.get('CURP') == registro.get('CURP')):
                    return False, f"Acta DUPLICADA. Ya existe {('Folio: '+registro.get('Folio')) if registro.get('Folio') else ('CURP: '+registro.get('CURP'))}."

            # normalizar orden de columnas
            fila = {h: registro.get(h, '') for h in ENCABEZADOS}
            REGISTROS.append(fila)

        return True, f"Acta registrada ({'Folio' if registro.get('Folio') else 'CURP'}: {clave}) exitosamente"
    except Exception as e:
        return False, f"Error al guardar: {str(e)}"


def obtener_registros():
    with _LOCK:
        # Más recientes primero por FechaEscaneo
        return sorted(
            REGISTROS,
            key=lambda r: r.get('FechaEscaneo', ''),
            reverse=True
        )


def procesar_imagen_qr(image_data):
    try:
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        image_bytes = base64.b64decode(image_data)
        np_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        if img is None:
            return None
        qr_detector = cv2.QRCodeDetector()
        data, bbox, _ = qr_detector.detectAndDecode(img)
        return data.strip() if data else None
    except Exception:
        return None


def extraer_qr_desde_pdf(pdf_bytes):
    """Extrae códigos QR de un PDF de forma optimizada."""
    temp_path = None
    pdf_document = None
    qr_codes = []

    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = temp_file.name

        # Abrir PDF
        pdf_document = fitz.open(temp_path)

        # Limitar número de páginas
        total_pages = len(pdf_document)
        max_pages = min(total_pages, MAX_PDF_PAGES)

        # Procesar cada página
        for page_num in range(max_pages):
            try:
                page = pdf_document.load_page(page_num)

                # Renderizar con menor resolución para mejorar velocidad
                # Factor 2 es suficiente para QR
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")

                # Liberar memoria de pixmap
                pix = None

                # Decodificar imagen
                np_array = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

                if img is not None:
                    # Detectar QR
                    qr_detector = cv2.QRCodeDetector()
                    data, bbox, _ = qr_detector.detectAndDecode(img)

                    if data and data.strip():
                        qr_codes.append(data.strip())

                        # Si encontramos QR, detener (optimización para actas de 1 página)
                        # Comentar esta línea si las actas pueden tener múltiples páginas con QR
                        break

                # Liberar memoria de imagen
                img = None
                np_array = None

            except Exception as e:
                # Continuar con la siguiente página si hay error
                continue

    except Exception as e:
        return []

    finally:
        # Limpieza garantizada
        if pdf_document:
            pdf_document.close()

        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

        # Forzar liberación de memoria
        cleanup_memory()

    return qr_codes


def convertir_fecha(fecha_str):
    try:
        if '/' in fecha_str:
            d, m, a = fecha_str.split('/')
            return f"{a}-{m}-{d}"
        return fecha_str
    except Exception:
        return fecha_str


def parsear_texto_acta(texto):
    registro = {}
    try:
        patrones = {
            'CURP': r'Clave Única de Registro de Población\s*([A-Z0-9]{18})',
            'Folio': r'Identificador Electrónico\s*(\d+)',
            'Entidad': r'Entidad de Registro\s*([A-ZÁÉÍÓÚÜÑ\s]+)',
            'Municipio': r'Municipio de Registro\s*([A-ZÁÉÍÓÚÜÑ\s]+)',
            'Oficial': r'Oficialía\s*(\d+)',
            'FechaRegistro': r'Fecha de Registro\s*(\d{2}/\d{2}/\d{4})',
            'Libro': r'Libro\s*(\d+)',
            'Acta': r'Número de Acta\s*(\d+)',
            'Registrado': r'Nombre\(s\):\s*([^\n]+)\s*Primer Apellido:\s*([^\n]+)\s*Segundo Apellido:\s*([^\n]+)',
            'Sexo': r'Sexo:\s*([^\n]+)',
            'FechaNacimiento': r'Fecha de Nacimiento:\s*(\d{2}/\d{2}/\d{4})',
        }

        m = re.search(patrones['CURP'], texto)
        if m: registro['CURP'] = m.group(1)

        m = re.search(patrones['Folio'], texto)
        if m: registro['Folio'] = m.group(1)

        m = re.search(patrones['Entidad'], texto)
        if m: registro['Entidad'] = m.group(1).strip()

        m = re.search(patrones['Municipio'], texto)
        if m: registro['Municipio'] = m.group(1).strip()

        m = re.search(patrones['Oficial'], texto)
        if m: registro['Oficial'] = m.group(1)

        m = re.search(patrones['FechaRegistro'], texto)
        if m: registro['FechaRegistro'] = convertir_fecha(m.group(1))

        m = re.search(patrones['Libro'], texto)
        if m: registro['Libro'] = m.group(1)

        m = re.search(patrones['Acta'], texto)
        if m: registro['Acta'] = m.group(1)

        m = re.search(patrones['Registrado'], texto, re.DOTALL)
        if m:
            registro['Registrado'] = f"{m.group(1).strip()} {m.group(2).strip()} {m.group(3).strip()}"

        m = re.search(patrones['Sexo'], texto)
        if m:
            sexo = m.group(1).strip().upper()
            registro['Sexo'] = 'H' if 'HOMB' in sexo else 'M' if 'MUJ' in sexo else sexo

        m = re.search(patrones['FechaNacimiento'], texto)
        if m: registro['FechaNacimiento'] = convertir_fecha(m.group(1))

        registro['Padre'] = registro.get('Padre', '')
        registro['Madre'] = registro.get('Madre', '')
        registro['Tomo'] = registro.get('Tomo', '')
        registro['Foja'] = registro.get('Foja', '')
        registro['FechaEscaneo'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return registro
    except Exception:
        return None


def extraer_datos_desde_texto_pdf(pdf_bytes):
    """Extrae datos de texto de un PDF de forma optimizada."""
    temp_path = None
    pdf_document = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = temp_file.name

        pdf_document = fitz.open(temp_path)

        # Limitar páginas procesadas
        total_pages = len(pdf_document)
        max_pages = min(total_pages, MAX_PDF_PAGES)

        texto = ""
        for page_num in range(max_pages):
            try:
                page = pdf_document.load_page(page_num)
                texto += page.get_text()
            except:
                continue

        return parsear_texto_acta(texto)

    except Exception:
        return None

    finally:
        if pdf_document:
            pdf_document.close()

        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

        cleanup_memory()


def procesar_pdf_con_fallback(pdf_bytes):
    qr_codes = extraer_qr_desde_pdf(pdf_bytes)
    if qr_codes:
        return qr_codes, 'qr'
    registro = extraer_datos_desde_texto_pdf(pdf_bytes)
    if registro:
        return [registro], 'texto'
    return [], 'fallo'


# ===== Rutas =====
@app.route('/')
def index():
    registros = obtener_registros()
    return render_template('index.html', registros=registros, total=len(registros), current_year=datetime.now().year)


@app.route('/procesar_qr', methods=['POST'])
def procesar_qr():
    try:
        data = request.json.get('qr_data', '').strip()
        if not data:
            return jsonify({'success': False, 'message': 'Datos QR vacíos'})
        registro = parsear_qr(data)
        success, message = guardar_registro(registro)
        tabla_html = render_template('_tabla_registros.html', registros=obtener_registros())
        return jsonify({
            'success': success,
            'message': message,
            'total_registros': len(obtener_registros()),
            'tabla_html': tabla_html
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@app.route('/procesar_imagen_qr', methods=['POST'])
def procesar_imagen_qr_route():
    try:
        image_data = request.json.get('image_data', '')
        if not image_data:
            return jsonify({'success': False, 'message': 'No se recibió imagen'})
        qr_text = procesar_imagen_qr(image_data)
        if qr_text:
            registro = parsear_qr(qr_text)
            success, message = guardar_registro(registro)
            tabla_html = render_template('_tabla_registros.html', registros=obtener_registros())
            return jsonify({
                'success': success,
                'message': message,
                'qr_data': qr_text,
                'total_registros': len(obtener_registros()),
                'tabla_html': tabla_html
            })
        return jsonify({'success': False, 'message': 'No se detectó QR'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error procesando imagen: {str(e)}'}), 500


@app.route('/procesar_pdf', methods=['POST'])
def procesar_pdf():
    """
    Procesa un archivo PDF para extraer datos de actas de nacimiento.
    Optimizado para manejar grandes volúmenes.
    """
    try:
        # Validar que se recibió el archivo
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'message': 'No se recibió archivo PDF'})

        pdf_file = request.files['pdf_file']

        # Validar archivo
        valid, error_msg = validate_pdf_file(pdf_file)
        if not valid:
            return jsonify({'success': False, 'message': error_msg})

        # Leer contenido del archivo
        pdf_bytes = pdf_file.read()

        # Validar que el PDF no esté corrupto
        if not pdf_bytes or len(pdf_bytes) < 100:
            return jsonify({'success': False, 'message': 'El archivo PDF parece estar corrupto o vacío'})

        # Procesar PDF con fallback
        hallados, metodo = procesar_pdf_con_fallback(pdf_bytes)

        # Liberar memoria del archivo
        pdf_bytes = None
        cleanup_memory()

        if not hallados:
            return jsonify({'success': False, 'message': 'No se pudo extraer información del PDF. Verifique que sea un acta de nacimiento válida con código QR.'})

        # Procesar registros encontrados
        resultados = []
        ok = 0
        errores = []

        for item in hallados:
            try:
                if metodo == 'qr':
                    registro = parsear_qr(item)
                else:
                    registro = item

                success, message = guardar_registro(registro)
                resultados.append({'metodo': metodo, 'success': success, 'message': message})

                if success:
                    ok += 1
                else:
                    errores.append(message)

            except Exception as e:
                errores.append(f'Error al procesar registro: {str(e)}')

        # Renderizar tabla actualizada
        tabla_html = render_template('_tabla_registros.html', registros=obtener_registros())

        # Construir mensaje de respuesta
        mensaje = f'Procesados {ok} de {len(hallados)} registros exitosamente'
        if errores:
            mensaje += f'. {len(errores)} error(es)'

        return jsonify({
            'success': ok > 0,
            'message': mensaje,
            'metodo_utilizado': metodo,
            'resultados': resultados,
            'total_registros': len(obtener_registros()),
            'tabla_html': tabla_html,
            'procesados': ok,
            'total': len(hallados),
            'errores': len(errores)
        })

    except Exception as e:
        cleanup_memory()
        return jsonify({
            'success': False,
            'message': f'Error procesando PDF: {str(e)}'
        }), 500


@app.route('/descargar_excel')
def descargar_excel():
    """Genera Excel en memoria. No escribe a disco."""
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Actas Escaneadas"
        for col, encabezado in enumerate(ENCABEZADOS, 1):
            c = ws.cell(row=1, column=col, value=encabezado)
            c.font = openpyxl.styles.Font(bold=True)

        for r in obtener_registros():
            ws.append([r.get(h, '') for h in ENCABEZADOS])

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        nombre = f"actas_escaneadas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(
            bio,
            as_attachment=True,
            download_name=nombre,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al descargar: {str(e)}'}), 500


@app.route('/limpiar_registros', methods=['POST'])
def limpiar_registros():
    try:
        with _LOCK:
            REGISTROS.clear()
        tabla_html = render_template('_tabla_registros.html', registros=[])
        return jsonify({'success': True, 'message': 'Registros limpiados', 'tabla_html': tabla_html})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al limpiar: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5045)

