"""
Configuración centralizada del sistema de escaneo de actas.
Todas las constantes y parámetros configurables del sistema.
"""
import os


class Config:
    """Configuración principal de la aplicación."""

    # Configuración de Flask
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5045))
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Configuración de la aplicación
    APP_NAME = "Escáner de Actas OFS Tlaxcala"
    APP_VERSION = "2.0"

    # Columnas del registro de actas (orden en Excel)
    ENCABEZADOS = [
        'Tomo', 'Libro', 'Foja', 'Acta', 'Entidad', 'Municipio',
        'CURP', 'Registrado', 'Padre', 'Madre', 'FechaNacimiento',
        'Sexo', 'FechaRegistro', 'Oficial', 'Folio', 'FechaEscaneo'
    ]

    # Configuración de procesamiento de PDF
    PDF_MAX_SIZE = 50 * 1024 * 1024  # 50 MB máximo por PDF
    PDF_RENDER_SCALE = 2  # Escala para renderizar PDF a imagen (mayor = mejor calidad QR)

    # Configuración de procesamiento QR
    QR_TIMEOUT = 10  # Timeout en segundos para detectar QR
    QR_ATTEMPTS = 3  # Intentos de lectura de QR

    # Límites de la aplicación
    MAX_REGISTROS_MEMORIA = 10000  # Máximo de registros en memoria

    # Configuración de archivos temporales
    TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp')


class KeyMapping:
    """Mapeo de claves del QR a nombres estándar de columnas."""

    MAPEO_CLAVES = {
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

    @classmethod
    def normalizar_clave(cls, raw_key: str) -> str:
        """
        Normaliza una clave del QR al nombre estándar.

        Args:
            raw_key: Clave sin procesar del QR

        Returns:
            Nombre estándar de la columna
        """
        clave_normalizada = raw_key.lower().replace(' ', '').replace('í', 'i')
        return cls.MAPEO_CLAVES.get(clave_normalizada, raw_key)


class RegexPatterns:
    """Patrones regex para extraer datos de texto de actas."""

    CURP = r'Clave Única de Registro de Población\s*([A-Z0-9]{18})'
    FOLIO = r'Identificador Electrónico\s*(\d+)'
    ENTIDAD = r'Entidad de Registro\s*([A-ZÁÉÍÓÚÜÑ\s]+)'
    MUNICIPIO = r'Municipio de Registro\s*([A-ZÁÉÍÓÚÜÑ\s]+)'
    OFICIAL = r'Oficialía\s*(\d+)'
    FECHA_REGISTRO = r'Fecha de Registro\s*(\d{2}/\d{2}/\d{4})'
    LIBRO = r'Libro\s*(\d+)'
    ACTA = r'Número de Acta\s*(\d+)'
    REGISTRADO = r'Nombre\(s\):\s*([^\n]+)\s*Primer Apellido:\s*([^\n]+)\s*Segundo Apellido:\s*([^\n]+)'
    SEXO = r'Sexo:\s*([^\n]+)'
    FECHA_NACIMIENTO = r'Fecha de Nacimiento:\s*(\d{2}/\d{2}/\d{4})'
