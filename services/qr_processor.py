"""
Servicio de procesamiento de códigos QR desde imágenes.
"""
import base64
import cv2
import numpy as np
from typing import Optional
from utils.logger import get_qr_logger

logger = get_qr_logger()


class QRProcessor:
    """Procesa imágenes para detectar y decodificar códigos QR."""

    @staticmethod
    def procesar_imagen(image_data: str) -> Optional[str]:
        """
        Procesa una imagen en base64 y extrae el código QR si existe.

        Args:
            image_data: Imagen en formato base64 (con o sin prefijo data:image)

        Returns:
            String con los datos del QR o None si no se detectó
        """
        try:
            logger.info("Iniciando procesamiento de imagen para detección de QR")

            # Remover prefijo de base64 si existe
            if 'base64,' in image_data:
                image_data = image_data.split('base64,')[1]

            # Decodificar imagen
            image_bytes = base64.b64decode(image_data)
            np_array = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

            if img is None:
                logger.warning("No se pudo decodificar la imagen")
                return None

            logger.debug(f"Imagen decodificada: {img.shape}")

            # Detectar y decodificar QR
            qr_detector = cv2.QRCodeDetector()
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(img)

            if data and data.strip():
                logger.info(f"QR detectado exitosamente (longitud: {len(data)})")
                logger.debug(f"Primeros 100 caracteres del QR: {data[:100]}")
                return data.strip()
            else:
                logger.warning("No se detectó código QR en la imagen")
                return None

        except base64.binascii.Error as e:
            logger.error(f"Error al decodificar base64: {e}")
            return None
        except cv2.error as e:
            logger.error(f"Error de OpenCV al procesar imagen: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al procesar imagen QR: {e}", exc_info=True)
            return None

    @staticmethod
    def procesar_desde_array(img_array: np.ndarray) -> Optional[str]:
        """
        Procesa un array de numpy (imagen) y extrae el código QR.

        Args:
            img_array: Array de numpy con la imagen

        Returns:
            String con los datos del QR o None si no se detectó
        """
        try:
            if img_array is None or img_array.size == 0:
                logger.warning("Array de imagen vacío o None")
                return None

            logger.debug(f"Procesando array de imagen: {img_array.shape}")

            # Detectar y decodificar QR
            qr_detector = cv2.QRCodeDetector()
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(img_array)

            if data and data.strip():
                logger.info(f"QR detectado en array (longitud: {len(data)})")
                return data.strip()
            else:
                logger.debug("No se detectó QR en el array de imagen")
                return None

        except cv2.error as e:
            logger.error(f"Error de OpenCV al procesar array: {e}")
            return None
        except Exception as e:
            logger.error(f"Error al procesar array de imagen: {e}", exc_info=True)
            return None
