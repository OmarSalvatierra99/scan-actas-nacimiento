"""
Aplicación Flask para escaneo y procesamiento de actas de nacimiento.
Sistema oficial de digitalización OFS Tlaxcala.

Funcionalidades:
- Escaneo de QR desde cámara, scanner USB o imágenes
- Procesamiento de PDFs con extracción de QR o texto
- Generación de reportes en Excel
- Gestión de registros en memoria con protección de duplicados

Autor: Omar Gabriel Salvatierra García
Año: 2025
"""
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

# Configuración y utilidades
from config import Config
from utils.logger import get_app_logger, log_system_start

# Modelos
from models import RegistroManager

# Servicios
from services import DataParser, QRProcessor, PDFProcessor, ExcelGenerator

# ===== Inicialización =====
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Logger principal
logger = get_app_logger()

# Registrar inicio del sistema
log_system_start()

# Gestor de registros global
registro_manager = RegistroManager()

logger.info(f"Aplicación {Config.APP_NAME} v{Config.APP_VERSION} inicializada")
logger.info(f"Configuración: DEBUG={Config.DEBUG}, HOST={Config.HOST}, PORT={Config.PORT}")


# ===== Rutas =====

@app.route('/')
def index():
    """Página principal de la aplicación."""
    try:
        logger.info("Acceso a página principal")
        registros = registro_manager.obtener_todos()
        total = registro_manager.contar()

        logger.debug(f"Renderizando index con {total} registro(s)")

        return render_template(
            'index.html',
            registros=registros,
            total=total,
            current_year=datetime.now().year
        )

    except Exception as e:
        logger.error(f"Error al renderizar página principal: {e}", exc_info=True)
        return f"Error interno del servidor: {str(e)}", 500


@app.route('/procesar_qr', methods=['POST'])
def procesar_qr():
    """
    Procesa datos de QR recibidos como texto (desde scanner USB).

    Espera JSON: {"qr_data": "..."}
    Retorna JSON con resultado del procesamiento.
    """
    try:
        logger.info("=== Procesando QR desde texto ===")

        data = request.json.get('qr_data', '').strip()

        if not data:
            logger.warning("Recibidos datos QR vacíos")
            return jsonify({'success': False, 'message': 'Datos QR vacíos'})

        logger.info(f"Datos QR recibidos (longitud: {len(data)})")

        # Parsear datos del QR
        datos_parseados = DataParser.parsear_qr(data)

        # Crear registro
        registro = registro_manager.crear_desde_dict(datos_parseados)

        # Guardar
        success, message = registro_manager.agregar(registro)

        # Renderizar tabla actualizada
        tabla_html = render_template(
            '_tabla_registros.html',
            registros=registro_manager.obtener_todos()
        )

        logger.info(f"QR procesado: {success} - {message}")

        return jsonify({
            'success': success,
            'message': message,
            'total_registros': registro_manager.contar(),
            'tabla_html': tabla_html
        })

    except Exception as e:
        logger.error(f"Error al procesar QR: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@app.route('/procesar_imagen_qr', methods=['POST'])
def procesar_imagen_qr():
    """
    Procesa una imagen en base64 para extraer código QR.

    Espera JSON: {"image_data": "data:image/png;base64,..."}
    Retorna JSON con resultado del procesamiento.
    """
    try:
        logger.info("=== Procesando imagen para detección de QR ===")

        image_data = request.json.get('image_data', '')

        if not image_data:
            logger.warning("No se recibió imagen")
            return jsonify({'success': False, 'message': 'No se recibió imagen'})

        # Procesar imagen
        qr_text = QRProcessor.procesar_imagen(image_data)

        if qr_text:
            logger.info("QR detectado en imagen")

            # Parsear y guardar
            datos_parseados = DataParser.parsear_qr(qr_text)
            registro = registro_manager.crear_desde_dict(datos_parseados)
            success, message = registro_manager.agregar(registro)

            # Renderizar tabla
            tabla_html = render_template(
                '_tabla_registros.html',
                registros=registro_manager.obtener_todos()
            )

            return jsonify({
                'success': success,
                'message': message,
                'qr_data': qr_text,
                'total_registros': registro_manager.contar(),
                'tabla_html': tabla_html
            })
        else:
            logger.warning("No se detectó QR en la imagen")
            return jsonify({'success': False, 'message': 'No se detectó QR en la imagen'})

    except Exception as e:
        logger.error(f"Error al procesar imagen QR: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error procesando imagen: {str(e)}'}), 500


@app.route('/procesar_pdf', methods=['POST'])
def procesar_pdf():
    """
    Procesa un archivo PDF para extraer datos de actas.

    Intenta primero extraer códigos QR, luego texto si no hay QR.
    Espera: multipart/form-data con campo 'pdf_file'
    Retorna JSON con resultado del procesamiento.
    """
    try:
        logger.info("=" * 80)
        logger.info("=== Procesando PDF ===")

        # Validar que se recibió archivo
        if 'pdf_file' not in request.files:
            logger.warning("No se recibió archivo PDF en la petición")
            return jsonify({'success': False, 'message': 'No se recibió archivo PDF'})

        pdf_file = request.files['pdf_file']

        # Validar extensión
        if not pdf_file.filename.lower().endswith('.pdf'):
            logger.warning(f"Archivo recibido no es PDF: {pdf_file.filename}")
            return jsonify({'success': False, 'message': 'El archivo debe ser un PDF'})

        logger.info(f"Procesando PDF: {pdf_file.filename}")

        # Leer bytes del PDF
        pdf_bytes = pdf_file.read()
        logger.info(f"PDF leído: {len(pdf_bytes)} bytes")

        # Procesar con fallback (QR -> texto)
        hallados, metodo = PDFProcessor.procesar_pdf_con_fallback(pdf_bytes)

        if not hallados:
            logger.warning("No se pudo extraer información del PDF")
            return jsonify({
                'success': False,
                'message': 'No se encontró QR ni texto procesable en el PDF'
            })

        logger.info(f"Método utilizado: {metodo}, elementos encontrados: {len(hallados)}")

        # Procesar cada elemento encontrado
        resultados = []
        exitosos = 0

        for item in hallados:
            if metodo == 'qr':
                # Item es string del QR
                datos_parseados = DataParser.parsear_qr(item)
                registro = registro_manager.crear_desde_dict(datos_parseados)
            else:
                # Item ya es diccionario
                registro = registro_manager.crear_desde_dict(item)

            success, message = registro_manager.agregar(registro)
            resultados.append({
                'metodo': metodo,
                'success': success,
                'message': message
            })

            if success:
                exitosos += 1

        # Renderizar tabla
        tabla_html = render_template(
            '_tabla_registros.html',
            registros=registro_manager.obtener_todos()
        )

        mensaje_final = f'Procesados {exitosos}/{len(hallados)} registro(s) usando {metodo}'
        logger.info(f"PDF procesado: {mensaje_final}")
        logger.info("=" * 80)

        return jsonify({
            'success': True,
            'message': mensaje_final,
            'metodo_utilizado': metodo,
            'resultados': resultados,
            'total_registros': registro_manager.contar(),
            'tabla_html': tabla_html
        })

    except Exception as e:
        logger.error(f"Error al procesar PDF: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error procesando PDF: {str(e)}'}), 500


@app.route('/descargar_excel')
def descargar_excel():
    """
    Genera y descarga archivo Excel con todos los registros.

    El archivo se genera en memoria (no se escribe a disco).
    Retorna archivo Excel o JSON con error.
    """
    try:
        logger.info("=== Generando Excel para descarga ===")

        registros = registro_manager.obtener_todos()
        logger.info(f"Generando Excel con {len(registros)} registro(s)")

        if not registros:
            logger.warning("Intento de descargar Excel sin registros")
            return jsonify({
                'success': False,
                'message': 'No hay registros para exportar'
            }), 400

        # Generar Excel en memoria
        excel_file = ExcelGenerator.generar_excel(registros)
        nombre_archivo = ExcelGenerator.generar_nombre_archivo()

        logger.info(f"Excel generado exitosamente: {nombre_archivo}")

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"Error al generar Excel: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error al descargar: {str(e)}'}), 500


@app.route('/limpiar_registros', methods=['POST'])
def limpiar_registros():
    """
    Limpia todos los registros de la memoria.

    Retorna JSON con resultado de la operación.
    """
    try:
        logger.info("=== Limpiando registros ===")

        success, message = registro_manager.limpiar()

        # Renderizar tabla vacía
        tabla_html = render_template('_tabla_registros.html', registros=[])

        logger.info(f"Limpieza completada: {message}")

        return jsonify({
            'success': success,
            'message': message,
            'tabla_html': tabla_html
        })

    except Exception as e:
        logger.error(f"Error al limpiar registros: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error al limpiar: {str(e)}'}), 500


# ===== Punto de entrada =====

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info(f"Iniciando servidor Flask en {Config.HOST}:{Config.PORT}")
    logger.info(f"Modo DEBUG: {Config.DEBUG}")
    logger.info("=" * 80)

    app.run(
        debug=Config.DEBUG,
        host=Config.HOST,
        port=Config.PORT
    )
