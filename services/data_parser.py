"""
Servicio de parseo de datos de actas desde QR o texto.
"""
import re
from typing import Dict, Optional
from datetime import datetime
from config import KeyMapping, RegexPatterns
from utils.logger import get_data_logger

logger = get_data_logger()


class DataParser:
    """Parsea datos de actas desde códigos QR o texto extraído."""

    @staticmethod
    def parsear_qr(data: str) -> Dict[str, str]:
        """
        Parsea datos del código QR de un acta.

        El formato del QR varía, pero generalmente contiene pares clave:valor
        separados por comas o puntos.

        Args:
            data: String con los datos del QR

        Returns:
            Diccionario con los datos parseados y normalizados
        """
        try:
            logger.info(f"Parseando QR de longitud {len(data)}")

            # Normalizar separadores comunes
            data = re.sub(r'([^,])CURP', r'\1,CURP', data, flags=re.IGNORECASE)
            data = re.sub(r'([^,])Padre', r'\1,Padre', data, flags=re.IGNORECASE)

            # Patrón para extraer pares clave:valor
            patron = re.compile(r'(\b[\w\s]+?):(.+?)(?=\s*[\w\s]+:|$)', re.IGNORECASE)
            matches = patron.findall(data)

            registro = {}
            for k, v in matches:
                clave_normalizada = KeyMapping.normalizar_clave(k.strip())
                valor_limpio = v.strip(' ,;')
                registro[clave_normalizada] = valor_limpio

            # Agregar timestamp
            registro['FechaEscaneo'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            logger.info(f"QR parseado exitosamente. Campos extraídos: {len(registro)}")
            logger.debug(f"Datos parseados: {registro}")

            return registro

        except Exception as e:
            logger.error(f"Error al parsear QR: {e}", exc_info=True)
            return {'FechaEscaneo': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    @staticmethod
    def parsear_texto_acta(texto: str) -> Optional[Dict[str, str]]:
        """
        Parsea datos de un acta desde texto extraído del PDF.

        Utiliza patrones regex para extraer campos específicos cuando
        no hay código QR disponible.

        Args:
            texto: Texto extraído del PDF del acta

        Returns:
            Diccionario con los datos parseados o None si falla
        """
        try:
            logger.info(f"Parseando texto de acta (longitud: {len(texto)})")

            registro = {}

            # CURP
            m = re.search(RegexPatterns.CURP, texto)
            if m:
                registro['CURP'] = m.group(1)
                logger.debug(f"CURP encontrado: {registro['CURP']}")

            # Folio
            m = re.search(RegexPatterns.FOLIO, texto)
            if m:
                registro['Folio'] = m.group(1)
                logger.debug(f"Folio encontrado: {registro['Folio']}")

            # Entidad
            m = re.search(RegexPatterns.ENTIDAD, texto)
            if m:
                registro['Entidad'] = m.group(1).strip()

            # Municipio
            m = re.search(RegexPatterns.MUNICIPIO, texto)
            if m:
                registro['Municipio'] = m.group(1).strip()

            # Oficial
            m = re.search(RegexPatterns.OFICIAL, texto)
            if m:
                registro['Oficial'] = m.group(1)

            # Fecha de Registro
            m = re.search(RegexPatterns.FECHA_REGISTRO, texto)
            if m:
                registro['FechaRegistro'] = DataParser._convertir_fecha(m.group(1))

            # Libro
            m = re.search(RegexPatterns.LIBRO, texto)
            if m:
                registro['Libro'] = m.group(1)

            # Acta
            m = re.search(RegexPatterns.ACTA, texto)
            if m:
                registro['Acta'] = m.group(1)

            # Registrado (nombre completo)
            m = re.search(RegexPatterns.REGISTRADO, texto, re.DOTALL)
            if m:
                registro['Registrado'] = f"{m.group(1).strip()} {m.group(2).strip()} {m.group(3).strip()}"

            # Sexo
            m = re.search(RegexPatterns.SEXO, texto)
            if m:
                sexo = m.group(1).strip().upper()
                registro['Sexo'] = 'H' if 'HOMB' in sexo else 'M' if 'MUJ' in sexo else sexo

            # Fecha de Nacimiento
            m = re.search(RegexPatterns.FECHA_NACIMIENTO, texto)
            if m:
                registro['FechaNacimiento'] = DataParser._convertir_fecha(m.group(1))

            # Campos por defecto
            registro.setdefault('Padre', '')
            registro.setdefault('Madre', '')
            registro.setdefault('Tomo', '')
            registro.setdefault('Foja', '')
            registro['FechaEscaneo'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Validar que se extrajeron datos mínimos
            if not registro.get('CURP') and not registro.get('Folio'):
                logger.warning("No se encontraron datos mínimos (CURP o Folio) en el texto")
                return None

            logger.info(f"Texto parseado exitosamente. Campos extraídos: {len(registro)}")
            return registro

        except Exception as e:
            logger.error(f"Error al parsear texto de acta: {e}", exc_info=True)
            return None

    @staticmethod
    def _convertir_fecha(fecha_str: str) -> str:
        """
        Convierte fecha de formato DD/MM/YYYY a YYYY-MM-DD.

        Args:
            fecha_str: Fecha en formato DD/MM/YYYY

        Returns:
            Fecha en formato YYYY-MM-DD o la misma si no se puede convertir
        """
        try:
            if '/' in fecha_str:
                d, m, a = fecha_str.split('/')
                return f"{a}-{m}-{d}"
            return fecha_str
        except Exception as e:
            logger.warning(f"Error al convertir fecha '{fecha_str}': {e}")
            return fecha_str
