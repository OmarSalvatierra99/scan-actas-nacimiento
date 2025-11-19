"""
Servicio de procesamiento de archivos PDF de actas.
Extrae códigos QR o texto de PDFs.
"""
import os
import tempfile
import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from config import Config
from services.qr_processor import QRProcessor
from services.data_parser import DataParser
from utils.logger import get_pdf_logger

logger = get_pdf_logger()


class PDFProcessor:
    """Procesa archivos PDF para extraer códigos QR o datos de texto."""

    @staticmethod
    def extraer_qr_desde_pdf(pdf_bytes: bytes) -> List[str]:
        """
        Extrae todos los códigos QR de un PDF.

        Renderiza cada página del PDF como imagen y busca códigos QR.

        Args:
            pdf_bytes: Bytes del archivo PDF

        Returns:
            Lista de strings con los datos de los QR encontrados
        """
        temp_path = None
        try:
            logger.info(f"Iniciando extracción de QR desde PDF ({len(pdf_bytes)} bytes)")

            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name

            logger.debug(f"PDF escrito en archivo temporal: {temp_path}")

            qr_codes = []
            pdf_document = fitz.open(temp_path)
            total_paginas = len(pdf_document)

            logger.info(f"PDF abierto: {total_paginas} página(s)")

            for page_num in range(total_paginas):
                logger.debug(f"Procesando página {page_num + 1}/{total_paginas}")

                page = pdf_document.load_page(page_num)

                # Renderizar página como imagen con escala configurable
                pix = page.get_pixmap(matrix=fitz.Matrix(Config.PDF_RENDER_SCALE, Config.PDF_RENDER_SCALE))
                img_data = pix.tobytes("png")

                # Convertir a formato OpenCV
                np_array = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

                if img is not None:
                    # Buscar QR en la imagen
                    qr_data = QRProcessor.procesar_desde_array(img)
                    if qr_data:
                        qr_codes.append(qr_data)
                        logger.info(f"QR encontrado en página {page_num + 1}")
                else:
                    logger.warning(f"No se pudo convertir página {page_num + 1} a imagen")

            pdf_document.close()
            logger.info(f"Extracción completada: {len(qr_codes)} QR(s) encontrado(s)")

            return qr_codes

        except Exception as e:
            logger.error(f"Error al extraer QR desde PDF: {e}", exc_info=True)
            return []
        finally:
            # Limpiar archivo temporal
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Archivo temporal eliminado: {temp_path}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar archivo temporal {temp_path}: {e}")

    @staticmethod
    def extraer_texto_desde_pdf(pdf_bytes: bytes) -> Optional[Dict[str, str]]:
        """
        Extrae y parsea texto de un PDF cuando no hay códigos QR.

        Args:
            pdf_bytes: Bytes del archivo PDF

        Returns:
            Diccionario con los datos parseados o None si falla
        """
        temp_path = None
        try:
            logger.info(f"Iniciando extracción de texto desde PDF ({len(pdf_bytes)} bytes)")

            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name

            logger.debug(f"PDF escrito en archivo temporal: {temp_path}")

            pdf_document = fitz.open(temp_path)
            texto_completo = ""

            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                texto_completo += page.get_text()

            pdf_document.close()

            logger.info(f"Texto extraído ({len(texto_completo)} caracteres)")

            # Parsear texto
            registro = DataParser.parsear_texto_acta(texto_completo)

            if registro:
                logger.info("Texto parseado exitosamente")
            else:
                logger.warning("No se pudo parsear el texto extraído")

            return registro

        except Exception as e:
            logger.error(f"Error al extraer texto desde PDF: {e}", exc_info=True)
            return None
        finally:
            # Limpiar archivo temporal
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Archivo temporal eliminado: {temp_path}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar archivo temporal {temp_path}: {e}")

    @staticmethod
    def procesar_pdf_con_fallback(pdf_bytes: bytes) -> Tuple[List, str]:
        """
        Procesa un PDF intentando primero extraer QR, luego texto.

        Esta es la función principal para procesar PDFs.

        Args:
            pdf_bytes: Bytes del archivo PDF

        Returns:
            Tupla (lista_de_datos, método_usado)
            - método_usado puede ser: 'qr', 'texto', 'fallo'
        """
        try:
            logger.info("=" * 60)
            logger.info("Iniciando procesamiento de PDF con fallback")

            # Intentar extracción de QR primero
            qr_codes = PDFProcessor.extraer_qr_desde_pdf(pdf_bytes)

            if qr_codes:
                logger.info(f"PDF procesado exitosamente vía QR: {len(qr_codes)} código(s)")
                return qr_codes, 'qr'

            logger.info("No se encontraron QR, intentando extracción de texto...")

            # Fallback: extracción de texto
            registro = PDFProcessor.extraer_texto_desde_pdf(pdf_bytes)

            if registro:
                logger.info("PDF procesado exitosamente vía texto")
                return [registro], 'texto'

            logger.warning("No se pudo extraer información del PDF (ni QR ni texto)")
            return [], 'fallo'

        except Exception as e:
            logger.error(f"Error crítico al procesar PDF: {e}", exc_info=True)
            return [], 'fallo'
