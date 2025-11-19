"""
Sistema de logging centralizado y robusto para el escáner de actas.
Crea siempre archivos de logs en la carpeta logs/ con rotación automática.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


class LoggerConfig:
    """Configuración centralizada del sistema de logging."""

    # Directorio de logs
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

    # Niveles de log
    LOG_LEVEL = logging.INFO

    # Formato de logs
    LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # Configuración de rotación
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB por archivo
    BACKUP_COUNT = 10  # Mantener 10 archivos de backup

    @classmethod
    def ensure_log_directory(cls):
        """Asegura que el directorio de logs exista."""
        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR)
            print(f"✓ Directorio de logs creado: {cls.LOG_DIR}")


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Configura y retorna un logger con archivo rotativo.

    Args:
        name: Nombre del logger (usualmente __name__ del módulo)
        log_file: Nombre del archivo de log (opcional, por defecto usa el nombre del módulo)

    Returns:
        Logger configurado
    """
    # Asegurar que existe el directorio
    LoggerConfig.ensure_log_directory()

    # Crear logger
    logger = logging.getLogger(name)
    logger.setLevel(LoggerConfig.LOG_LEVEL)

    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger

    # Determinar nombre del archivo de log
    if log_file is None:
        log_file = f"{name.replace('.', '_')}.log"

    log_path = os.path.join(LoggerConfig.LOG_DIR, log_file)

    # Handler para archivo con rotación
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=LoggerConfig.MAX_BYTES,
        backupCount=LoggerConfig.BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(LoggerConfig.LOG_LEVEL)

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Solo warnings y errores en consola

    # Formato
    formatter = logging.Formatter(LoggerConfig.LOG_FORMAT, LoggerConfig.DATE_FORMAT)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Agregar handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_app_logger() -> logging.Logger:
    """Retorna el logger principal de la aplicación."""
    return setup_logger('actas_scanner', 'app.log')


def get_qr_logger() -> logging.Logger:
    """Retorna el logger para procesamiento de QR."""
    return setup_logger('qr_processor', 'qr_processing.log')


def get_pdf_logger() -> logging.Logger:
    """Retorna el logger para procesamiento de PDF."""
    return setup_logger('pdf_processor', 'pdf_processing.log')


def get_data_logger() -> logging.Logger:
    """Retorna el logger para parseo de datos."""
    return setup_logger('data_parser', 'data_parsing.log')


# Crear un log de inicio del sistema
def log_system_start():
    """Registra el inicio del sistema."""
    logger = get_app_logger()
    logger.info("=" * 80)
    logger.info("SISTEMA DE ESCANEO DE ACTAS - INICIO")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Directorio de logs: {LoggerConfig.LOG_DIR}")
    logger.info("=" * 80)


# Inicializar el directorio de logs al importar el módulo
LoggerConfig.ensure_log_directory()
