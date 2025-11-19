"""
Modelo de datos para registros de actas y su gestión en memoria.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from threading import RLock
from typing import List, Dict, Optional, Tuple
from config import Config
from utils.logger import get_app_logger

logger = get_app_logger()


@dataclass
class RegistroActa:
    """
    Representa un registro de acta de nacimiento escaneada.
    """
    Tomo: str = ''
    Libro: str = ''
    Foja: str = ''
    Acta: str = ''
    Entidad: str = ''
    Municipio: str = ''
    CURP: str = ''
    Registrado: str = ''
    Padre: str = ''
    Madre: str = ''
    FechaNacimiento: str = ''
    Sexo: str = ''
    FechaRegistro: str = ''
    Oficial: str = ''
    Folio: str = ''
    FechaEscaneo: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def to_dict(self) -> Dict[str, str]:
        """Convierte el registro a diccionario."""
        return asdict(self)

    def get_clave_unica(self) -> Optional[str]:
        """Retorna la clave única del registro (Folio o CURP)."""
        return self.Folio or self.CURP

    def __str__(self) -> str:
        """Representación en string del registro."""
        clave = self.get_clave_unica()
        return f"RegistroActa({self.Registrado}, {clave})"


class RegistroManager:
    """
    Gestor de registros en memoria con protección de concurrencia.
    Mantiene una lista de actas escaneadas y previene duplicados.
    """

    def __init__(self):
        """Inicializa el gestor de registros."""
        self._registros: List[RegistroActa] = []
        self._lock = RLock()
        logger.info("RegistroManager inicializado")

    def agregar(self, registro: RegistroActa) -> Tuple[bool, str]:
        """
        Agrega un registro a la lista si no es duplicado.

        Args:
            registro: Instancia de RegistroActa a agregar

        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            clave = registro.get_clave_unica()

            if not clave:
                mensaje = "Error: No se encontró Folio ni CURP en el registro"
                logger.warning(f"Intento de agregar registro sin clave única: {registro}")
                return False, mensaje

            with self._lock:
                # Verificar si hay límite de memoria
                if len(self._registros) >= Config.MAX_REGISTROS_MEMORIA:
                    mensaje = f"Límite de memoria alcanzado ({Config.MAX_REGISTROS_MEMORIA} registros)"
                    logger.error(mensaje)
                    return False, mensaje

                # Verificar duplicados
                for r in self._registros:
                    if (registro.Folio and r.Folio == registro.Folio) or \
                       (registro.CURP and r.CURP == registro.CURP):
                        mensaje = f"Acta DUPLICADA. Ya existe {('Folio: ' + registro.Folio) if registro.Folio else ('CURP: ' + registro.CURP)}"
                        logger.warning(f"Intento de agregar duplicado: {clave}")
                        return False, mensaje

                # Agregar registro
                self._registros.append(registro)
                mensaje = f"Acta registrada ({'Folio' if registro.Folio else 'CURP'}: {clave}) exitosamente"
                logger.info(f"Registro agregado: {clave} - {registro.Registrado}")
                return True, mensaje

        except Exception as e:
            mensaje = f"Error al guardar: {str(e)}"
            logger.error(f"Error al agregar registro: {e}", exc_info=True)
            return False, mensaje

    def obtener_todos(self, ordenar_por_fecha: bool = True) -> List[Dict[str, str]]:
        """
        Obtiene todos los registros como lista de diccionarios.

        Args:
            ordenar_por_fecha: Si True, ordena por FechaEscaneo descendente

        Returns:
            Lista de registros como diccionarios
        """
        with self._lock:
            registros = [r.to_dict() for r in self._registros]

            if ordenar_por_fecha:
                registros = sorted(
                    registros,
                    key=lambda r: r.get('FechaEscaneo', ''),
                    reverse=True
                )

            logger.debug(f"Obtenidos {len(registros)} registros")
            return registros

    def contar(self) -> int:
        """Retorna el número total de registros."""
        with self._lock:
            return len(self._registros)

    def limpiar(self) -> Tuple[bool, str]:
        """
        Limpia todos los registros de la memoria.

        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            with self._lock:
                cantidad = len(self._registros)
                self._registros.clear()
                mensaje = f"Se limpiaron {cantidad} registros de la memoria"
                logger.info(mensaje)
                return True, mensaje
        except Exception as e:
            mensaje = f"Error al limpiar registros: {str(e)}"
            logger.error(mensaje, exc_info=True)
            return False, mensaje

    def crear_desde_dict(self, datos: Dict[str, str]) -> RegistroActa:
        """
        Crea una instancia de RegistroActa desde un diccionario.
        Normaliza el orden de columnas según Config.ENCABEZADOS.

        Args:
            datos: Diccionario con datos del registro

        Returns:
            Instancia de RegistroActa
        """
        # Normalizar orden de columnas
        datos_normalizados = {h: datos.get(h, '') for h in Config.ENCABEZADOS}
        return RegistroActa(**datos_normalizados)
