# Arquitectura del Sistema

## Estructura del Proyecto

```
Scan-Actas-Nacimiento/
├── app.py                      # Aplicación Flask principal (rutas HTTP)
├── config.py                   # Configuración centralizada
├── requirements.txt            # Dependencias Python
├── README.md                   # Documentación del proyecto
├── ARCHITECTURE.md            # Este archivo - documentación de arquitectura
├── .gitignore                 # Archivos ignorados por git
│
├── models/                     # Modelos de datos
│   ├── __init__.py
│   └── registro.py            # Modelo RegistroActa y RegistroManager
│
├── services/                   # Servicios de procesamiento
│   ├── __init__.py
│   ├── data_parser.py         # Parseo de datos QR y texto
│   ├── qr_processor.py        # Procesamiento de códigos QR
│   ├── pdf_processor.py       # Procesamiento de archivos PDF
│   └── excel_generator.py     # Generación de archivos Excel
│
├── utils/                      # Utilidades
│   ├── __init__.py
│   └── logger.py              # Sistema de logging centralizado
│
├── templates/                  # Templates HTML (Flask)
│   ├── index.html
│   └── _tabla_registros.html
│
├── static/                     # Archivos estáticos
│   ├── css/
│   │   └── style.css
│   └── img/
│       ├── ofs_logo.png
│       └── avatar_default.png
│
└── logs/                       # Logs del sistema (creados automáticamente)
    ├── .gitkeep               # Mantiene directorio en git
    ├── app.log                # Log principal de la aplicación
    ├── qr_processing.log      # Log de procesamiento QR
    ├── pdf_processing.log     # Log de procesamiento PDF
    └── data_parsing.log       # Log de parseo de datos
```

## Módulos del Sistema

### 1. `app.py` - Aplicación Flask Principal
**Responsabilidad:** Gestión de rutas HTTP y coordinación de servicios.

**Rutas:**
- `GET /` - Página principal
- `POST /procesar_qr` - Procesa datos QR desde scanner USB
- `POST /procesar_imagen_qr` - Procesa imagen con QR desde cámara
- `POST /procesar_pdf` - Procesa archivo PDF
- `GET /descargar_excel` - Descarga Excel con registros
- `POST /limpiar_registros` - Limpia registros de memoria

### 2. `config.py` - Configuración Centralizada
**Responsabilidad:** Constantes y parámetros configurables.

**Clases:**
- `Config` - Configuración general de Flask y la aplicación
- `KeyMapping` - Mapeo de claves QR a nombres estándar
- `RegexPatterns` - Patrones regex para extracción de texto

### 3. `models/registro.py` - Modelos de Datos
**Responsabilidad:** Estructuras de datos y gestión de registros.

**Clases:**
- `RegistroActa` - Dataclass que representa un acta escaneada
- `RegistroManager` - Gestor de registros con protección de concurrencia

**Características:**
- Thread-safe (usa RLock)
- Prevención de duplicados (por Folio o CURP)
- Límite configurable de registros en memoria

### 4. `services/data_parser.py` - Parseo de Datos
**Responsabilidad:** Extracción y normalización de datos.

**Métodos:**
- `parsear_qr(data)` - Parsea string del código QR
- `parsear_texto_acta(texto)` - Extrae datos desde texto del PDF
- `_convertir_fecha(fecha_str)` - Convierte formato de fechas

### 5. `services/qr_processor.py` - Procesamiento QR
**Responsabilidad:** Detección y decodificación de códigos QR.

**Métodos:**
- `procesar_imagen(image_data)` - Procesa imagen base64
- `procesar_desde_array(img_array)` - Procesa array numpy

**Tecnología:** OpenCV (cv2.QRCodeDetector)

### 6. `services/pdf_processor.py` - Procesamiento PDF
**Responsabilidad:** Extracción de datos desde PDFs.

**Métodos:**
- `extraer_qr_desde_pdf(pdf_bytes)` - Busca QR en cada página
- `extraer_texto_desde_pdf(pdf_bytes)` - Extrae y parsea texto
- `procesar_pdf_con_fallback(pdf_bytes)` - Intenta QR, luego texto

**Características:**
- Usa archivos temporales seguros (tempfile)
- Limpieza automática de archivos temporales
- Fallback inteligente: QR → Texto → Fallo

**Tecnología:** PyMuPDF (fitz)

### 7. `services/excel_generator.py` - Generación Excel
**Responsabilidad:** Crear archivos Excel con registros.

**Métodos:**
- `generar_excel(registros)` - Genera Excel en memoria (BytesIO)
- `generar_nombre_archivo()` - Crea nombre único con timestamp
- `_ajustar_anchos_columnas(ws)` - Ajusta anchos de columnas

**Características:**
- Generación en memoria (no escribe a disco)
- Formato profesional con estilos
- Nombres únicos con timestamp

**Tecnología:** openpyxl

### 8. `utils/logger.py` - Sistema de Logging
**Responsabilidad:** Logging centralizado y robusto.

**Características:**
- Archivos de log rotativos (10 MB máximo, 10 backups)
- Logs separados por módulo
- Formato estructurado con timestamps
- Creación automática del directorio logs/

**Loggers disponibles:**
- `get_app_logger()` - Log principal
- `get_qr_logger()` - Log de procesamiento QR
- `get_pdf_logger()` - Log de procesamiento PDF
- `get_data_logger()` - Log de parseo de datos

## Flujo de Procesamiento

### Escaneo desde QR (Scanner USB o Cámara)
```
1. Usuario escanea QR
2. Datos llegan a /procesar_qr o /procesar_imagen_qr
3. QRProcessor.procesar_imagen() (si es imagen)
4. DataParser.parsear_qr() → Dict
5. RegistroManager.crear_desde_dict() → RegistroActa
6. RegistroManager.agregar() → Validación y guardado
7. Respuesta JSON + tabla HTML actualizada
```

### Procesamiento de PDF
```
1. Usuario sube PDF
2. PDFProcessor.procesar_pdf_con_fallback()
   a. Intenta extraer_qr_desde_pdf()
      - Renderiza cada página como imagen
      - Busca QR con OpenCV
   b. Si falla, intenta extraer_texto_desde_pdf()
      - Extrae texto con PyMuPDF
      - DataParser.parsear_texto_acta()
3. Por cada resultado encontrado:
   - DataParser.parsear_qr() (si método=qr)
   - RegistroManager.agregar()
4. Respuesta JSON con resultados
```

### Generación de Excel
```
1. Usuario hace clic en "Descargar Excel"
2. RegistroManager.obtener_todos()
3. ExcelGenerator.generar_excel(registros)
   - Crea Workbook en memoria
   - Aplica estilos y formato
   - Guarda en BytesIO
4. Flask send_file() descarga el archivo
```

## Sistema de Logging

Todos los módulos registran sus operaciones en archivos de log:

- **Nivel INFO:** Operaciones normales (inicio, éxito, contadores)
- **Nivel WARNING:** Situaciones anormales pero manejables (QR no detectado, duplicados)
- **Nivel ERROR:** Errores que impiden completar operación
- **Nivel DEBUG:** Información detallada para debugging

**Formato de logs:**
```
2025-11-19 00:42:14 | INFO | actas_scanner | funcion:linea | Mensaje
```

**Rotación automática:**
- Máximo 10 MB por archivo
- Mantiene 10 archivos de backup
- Archivos antiguos se comprimen automáticamente

## Mejoras Implementadas (v2.0)

### ✅ Sistema de Logging Robusto
- Logs automáticos en todas las operaciones
- Archivos separados por módulo
- Rotación automática de logs

### ✅ Arquitectura Modular
- Separación clara de responsabilidades
- Código organizado por funcionalidad
- Fácil mantenimiento y testing

### ✅ Configuración Centralizada
- Todos los parámetros en config.py
- Fácil ajuste sin modificar código
- Soporte para variables de entorno

### ✅ Manejo de Errores Mejorado
- Logging específico de errores
- Mensajes descriptivos
- Stack traces completos en logs

### ✅ Documentación Completa
- Docstrings en todas las funciones
- Comentarios descriptivos
- Arquitectura documentada

### ✅ Thread Safety
- RegistroManager con RLock
- Operaciones concurrentes seguras

### ✅ Código Limpio
- Eliminado código duplicado
- Nombres descriptivos
- Estructura clara

## Configuración

### Variables de Entorno (Opcional)
```bash
export FLASK_DEBUG=true          # Modo debug
export FLASK_HOST=0.0.0.0        # Host
export FLASK_PORT=5045           # Puerto
export SECRET_KEY=tu-clave-secreta  # Clave secreta de Flask
```

### Parámetros Configurables (config.py)
- `ENCABEZADOS` - Columnas del Excel
- `PDF_RENDER_SCALE` - Calidad de renderizado PDF (mayor = mejor detección QR)
- `MAX_REGISTROS_MEMORIA` - Límite de registros en memoria
- Patrones regex para extracción de texto

## Tecnologías Utilizadas

- **Flask 3.0.3** - Framework web
- **OpenCV 4.10** - Procesamiento de imágenes y QR
- **PyMuPDF 1.24** - Procesamiento de PDF
- **openpyxl 3.1.5** - Generación de Excel
- **NumPy 1.26** - Procesamiento numérico

## Mantenimiento

### Agregar nuevo campo al registro
1. Agregar a `Config.ENCABEZADOS` en config.py
2. Agregar a dataclass `RegistroActa` en models/registro.py
3. Actualizar patrón regex en `RegexPatterns` si aplica

### Modificar formato de logs
1. Editar `LoggerConfig` en utils/logger.py
2. Ajustar `LOG_FORMAT` y `LOG_LEVEL`

### Cambiar límites del sistema
1. Editar valores en `Config` en config.py

## Notas de Seguridad

- Los archivos temporales se eliminan inmediatamente después de usar
- Los registros se mantienen solo en memoria (no se persisten)
- Los logs no contienen información sensible de las actas
- Validación de extensiones de archivo (.pdf)
- Protección contra duplicados

---
**Versión:** 2.0
**Autor:** Omar Gabriel Salvatierra García
**Fecha:** 2025
**Organización:** Órgano de Fiscalización Superior de Tlaxcala
