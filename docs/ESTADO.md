# Estado de la continuación

Fecha: 12 de octubre de 2026.
Base utilizada: rama `feat/flask-faiss-n8n`, commit `1fe5693`, que contenía avances posteriores a `main` (`67a496c`). Rama de trabajo: `feat/flask-faiss-n8n`.

## Completado

| Módulo | Resultado |
| --- | --- |
| Conexión del portal | Flask sirve frontend y recibe el formulario en el mismo origen; ya no depende del puerto n8n del navegador. |
| Registro | Tickets reales, validación, errores HTTP/JSON y persistencia SQL; no se inventan tickets ante fallos. |
| Reintentos | Nueva tabla idempotente añadida por init-db; misma clave y contenido devuelven el mismo ticket, incluso después de caída de n8n. |
| n8n | Flujo JSON importable, dos credenciales Header Auth, propagación de estado HTTP y respuesta después de guardar el ticket. |
| Configuración | .env.example, generación local de claves y tablas, lectura de entorno por factory y diagnóstico de conexión. |
| DPO | Autenticación, datos reales, paginación/filtros, transiciones válidas, auditoría, PDF y cierre de sesión. |
| Derechos | Acceso, JSON portable, rectificación y anonimización SQL con bloqueo por retención. |
| Supresión | Vinculación de solicitudes anteriores al alta; limpieza de detalles y notas de resolución además de identificador/correo. |
| Redacción | Ocultación asistida de correos, DNI, teléfonos y valores especificados; salida marcada para revisión. |
| Reportes | Constancia PDF del ticket y trazabilidad, sin documento/correo/textos libres. |
| IA | Modelo multilingüe local y FAISS; identidad del modelo por contenido para poder moverlo entre host y Docker. |
| Ejecución | Arranque raíz/backend, eliminación de dependencia de symlink, Docker/Compose y preparación de IA fuera de HTTP. |
| Verificación | Pruebas de API, motor, formularios y panel con Flask real en Windows y Ubuntu; construcción y arranque de Compose en GitHub Actions. |

## Evidencia de verificación

- 53 pruebas de backend pasadas, incluyendo seguridad, idempotencia, fallos de n8n, reportes, supresión y compatibilidad de configuración.
- 6 pruebas del motor pasadas, con NumPy/FAISS reales y encoder determinista, además de identidad portable del modelo.
- 7 pruebas JavaScript/DOM pasadas; la prueba del panel usa Flask real con BD en memoria y verifica registro, autenticación, transiciones, ausencia de inyección HTML, PDF, portabilidad, rectificación, retención, supresión y logout.
- Modelo `paraphrase-multilingual-MiniLM-L12-v2` descargado y preparado; 13 chunks indexados; endpoint vector-search devuelve HTTP 200 y 3 resultados con el modelo real.
- Circuito con n8n 2.42.7 real verificado mediante `scripts/check_n8n.py`: publicación del flujo, petición desde Flask, escritura por API privada, devolución de ticket, reintento sin duplicados y rechazo de webhook sin credencial. Durante la prueba se corrigió una expresión de respuesta incompatible con el evaluador de n8n; ahora se usan expresiones sencillas.
- Sintaxis Python/JS y `git diff --check` verificados.
- GitHub Actions ejecutó las 66 pruebas y `scripts/setup.py --demo` correctamente tanto en `windows-latest` como en `ubuntu-latest`, con Python 3.11 y Node 24. Las guías de instalación usan Python 3.12 en Windows y Python del sistema compatible en Linux.
- Docker/Compose verificado en GitHub Actions: imagen construida con PyTorch CPU, FAISS y SentenceTransformers; Flask arrancado con Gunicorn en modo producción; SQLite inicializado; portal, panel, rechazo de API privada sin clave, registro idempotente y PDF comprobados. El contenedor n8n 2.42.7 respondió a healthz. Esta prueba de Compose no importa el workflow ni descarga el modelo; el circuito n8n y el modelo real se verificaron por separado como se indica arriba.

## Configuración que debes hacer en tu computadora

Para simplificar esos pasos, `python3 iniciar.py --demo` crea/reutiliza el entorno, prepara dependencias y modelo, actualiza el índice, comprueba una búsqueda real y abre el panel. Consulta [Uso sencillo con IA](USO_SENCILLO_IA.md). El panel muestra el estado del modelo y organiza la atención por solicitud: datos del titular, búsqueda de documentos por ID, tarjetas con fuentes y revisión de fragmentos.

1. Instalar dependencias y ejecutar `scripts/setup.py` para generar tus propias claves. Las claves y la BD local usadas en las pruebas no se incluyen en Git.
2. Preparar modelo/índice con `scripts/prepare_ai.py` para usar búsqueda semántica. Tampoco se incluyen los pesos ni el índice en Git.
3. Para modo n8n, importar el flujo, seleccionar las dos credenciales, revisar hostname/puerto, publicar y cambiar DSAR_INTAKE_MODE. El modo directo funciona antes de ese paso.

El código y el flujo fueron probados en el entorno de trabajo y en GitHub Actions. No se accedió a tu instancia local de n8n, tu computadora o tu sesión de Codex. Sigue la guía de [Windows](CONFIGURAR_WINDOWS.md) o [Linux](CONFIGURAR_LINUX.md) para configurar tu instalación.

## Alcance del prototipo

El DPO conserva la verificación de identidad y la decisión de atender el derecho. Las reglas de ocultación requieren revisión y no prueban anonimato irreversible. La supresión afecta a SQL: documentos externos y copias previas de índices requieren revisión y reconstrucción aparte. No se implementó envío de correo ni ZIP de datos del titular; el portal ya no los promete. No había issues abiertos en GitHub al consultar el repositorio. Una lista adicional de tareas en la sesión privada de Codex no está incluida en este repositorio.

## Publicación en GitHub

Repositorio de integración: `JeremyCruzGallegos/agente-dsar-iso27701`. Rama: `feat/flask-faiss-n8n`. Base de la continuación: `1fe5693`, conservada como padre del commit publicado. La incorporación a main se revisa mediante pull request. El repositorio original de Ypss8522 conserva su estado independiente.

El PR #1 fue fusionado en main y su rama se eliminó. La mejora del arranque y panel con IA se desarrolla en `feat/dpo-ia-guiada`, partiendo de main (`1b85010`). Se verificaron 58 pruebas de backend/arranque, 8 de motor y 7 JavaScript/DOM. Con el modelo multilingüe real se comprobaron 5 documentos y 13 fragmentos; la búsqueda por ID `72839102` devolvió 3 fragmentos de su contrato y un ID sin documentos devolvió cero resultados. También se verificó que detener el lanzador libera el puerto de Flask.
