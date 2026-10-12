# Poner en marcha el agente DSAR

Instalación por sistema: [Windows](CONFIGURAR_WINDOWS.md) · [Linux](CONFIGURAR_LINUX.md).

## 1. Abrir el proyecto

Usa Python 3.11 o superior. Desde la carpeta del proyecto:

```bash
python -m venv .venv
```

Activar en Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activar en Linux/macOS:

```bash
source .venv/bin/activate
```

## 2. Preparar y arrancar Flask

```bash
python -m pip install -r backend/requirements.txt
python scripts/setup.py --demo
python app.py
```

`setup.py` crea `backend/.env` con claves aleatorias, crea las tablas que faltan y conserva las tablas/datos existentes. `--demo` agrega dos titulares ficticios; omítelo si no quieres ejemplos.

- Portal: http://127.0.0.1:5000/
- Panel DPO: http://127.0.0.1:5000/dpo
- Estado del backend: http://127.0.0.1:5000/api/health

Abre `backend/.env` localmente y copia **DPO_API_KEY** en el panel. El panel mantiene esa clave sólo en memoria, la borra al cerrar sesión y no incluye claves en los archivos publicados. **SERVICE_API_KEY** se usa sólo en servicios internos. El modo inicial `DSAR_INTAKE_MODE=direct` registra solicitudes sin depender de n8n. La recepción no ejecuta automáticamente borrados ni entrega datos a un correo sin verificar.

Prueba un envío con el documento `72839102`, un correo válido y derecho `Acceso`. El ticket aparece en el portal y en el panel. En DPO selecciona **Revisar**, avanza a **En proceso** y luego a **Completado**. Descarga el PDF. El titular `45120987` tiene retención: su supresión debe ser rechazada.

## 3. Preparar la búsqueda semántica

En otra terminal con el entorno activado:

```bash
python -m pip install -r ai_engine/requirements.txt
python scripts/prepare_ai.py
```

Esto descarga explícitamente el modelo multilingüe, crea el índice y guarda su ruta en `.env`. Reinicia Flask. Luego busca `correo electrónico de Juan Pérez` en el panel DPO.

Si tienes un modelo ya descargado, sin conexión a Internet:

```bash
python scripts/prepare_ai.py --local-model RUTA_AL_MODELO
```

Las peticiones HTTP nunca descargan modelos ni crean índices. Si cambias documentos o modelo, reconstruye el índice y reinicia Flask. En entornos con proxy SOCKS puede hacer falta `python -m pip install "httpx[socks]"`.

## 4. Conectar n8n

1. Con Node.js 24 LTS, inicia n8n con `npx --yes n8n@2.42.7` (`npx.cmd --yes n8n@2.42.7` en PowerShell) o con el servicio Docker descrito abajo. Abre http://127.0.0.1:5678 y configura su cuenta local.
2. Importa `n8n_workflows/dsar-request.json` con **Import from File**.
3. Crea una credencial **Header Auth** llamada **DSAR Webhook**:
   - Name: `X-Webhook-Token`.
   - Value: el valor **N8N_WEBHOOK_TOKEN** de `backend/.env`.
4. Crea otra credencial **Header Auth** llamada **DSAR Backend**:
   - Name: `X-API-Key`.
   - Value: **SERVICE_API_KEY** de `backend/.env`.
5. En **Recibir DSAR**, selecciona la credencial DSAR Webhook. En **Crear ticket en Flask**, selecciona DSAR Backend. Los IDs de las credenciales en el JSON son marcadores: debes seleccionarlas después de importar.
6. Revisa la URL del nodo HTTP:
   - Ambos procesos en tu computadora: `http://127.0.0.1:5000/api/requests`.
   - Ambos servicios en este Compose: `http://backend:5000/api/requests`.
   - Sólo n8n en Docker y Flask en el host: `http://host.docker.internal:5000/api/requests`. En Linux añade `host.docker.internal:host-gateway` al contenedor y configura Flask para escuchar en una interfaz accesible.
7. Guarda y **publica/activa** el flujo. La URL permanente usa `/webhook/dsar-request`. `/webhook-test/` sólo funciona mientras se escucha una ejecución manual.
8. Cambia en `.env`:

```dotenv
DSAR_INTAKE_MODE=n8n
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/dsar-request
```

9. Reinicia Flask y envía otra solicitud desde el portal. El recorrido será **navegador → Flask → n8n → API privada de Flask → ticket confirmado**. El navegador ya no necesita conectar directamente a otro puerto ni tener la clave de servicio.

El flujo registra el ticket y lo devuelve, sin ejecutar derechos sensibles automáticamente. La verificación de identidad y la autorización corresponden al DPO. Las acciones de acceso, portabilidad, rectificación y supresión se operan desde su panel. El PDF es una constancia sin PII, no el expediente de datos del titular. El envío de correo y la creación de ZIP de datos no están implementados: el portal dejó de prometerlos.

## 5. Docker opcional

Prepara `.env` con el paso 2. Luego:

```bash
docker compose up --build -d
```

Abre Flask en el puerto 5000 y n8n en el 5678. La configuración de credenciales/importación del paso 4 sigue siendo necesaria. El Compose conserva las bases en volúmenes separados, limita los puertos al host y desactiva el guardado de datos de ejecuciones de n8n. No usa la BD SQLite local previa: si necesitas reutilizarla, respáldala y configura un montaje explícito.

La imagen de Flask instala el backend, PDF y FAISS/SentenceTransformers con PyTorch de CPU. Prepara modelo e índice en el host con el paso 3 antes de usar la búsqueda en Docker. Los montajes de modelo/índice son de sólo lectura y la ruta interna del modelo ya está configurada. La identidad del modelo se comprueba por contenido para admitir copiarlo a otro directorio. Índices de versiones anteriores deben reconstruirse con `prepare_ai.py`. La construcción inicial descarga dependencias de IA y puede demorar.

## 6. Diagnosticar conexión

Con Flask encendido:

```bash
python scripts/diagnose.py
```

Si usas otro puerto:

```bash
python scripts/diagnose.py --url http://127.0.0.1:5123
```

| Síntoma | Qué revisar |
| --- | --- |
| El portal no abre | Ejecuta `python app.py`; revisa host/puerto. No abras el HTML con `file://`. |
| `database_not_initialized` | Ejecuta `python scripts/setup.py`. En una BD anterior crea la tabla adicional sin borrar registros. |
| El DPO responde 401 | Copia DPO_API_KEY, no SERVICE_API_KEY; reinicia Flask tras cambiar `.env`. |
| `n8n_unreachable` / 503 | n8n apagado, puerto o hostname incorrecto. Dentro de Docker, `localhost` identifica el propio contenedor. |
| n8n HTTP 404 | Publica el flujo y usa `/webhook/`; verifica la ruta exacta. |
| n8n HTTP 401 | Credencial DSAR Webhook no coincide con N8N_WEBHOOK_TOKEN. |
| n8n HTTP 401/403 desde Flask | Credencial DSAR Backend no coincide con SERVICE_API_KEY. |
| Timeout / 504 | Revisa la ejecución n8n. Reintenta manteniendo el formulario: se conserva la clave de idempotencia. |
| Respuesta n8n sin ticket | Conecta los tres nodos y usa Respond to Webhook después de registrar; no uses respuesta inmediata del Webhook. |
| FAISS 503 | Instala dependencias, prepara modelo/índice y reinicia Flask. |
| Problemas de origen/CORS | Usa el portal servido por Flask. Para un frontend separado, añade su origen exacto a CORS_ORIGINS. |

Los reintentos con la misma clave devuelven el ticket existente, incluso si n8n se cayó después de guardarlo. Cambiar los datos crea otra clave. Tras recargar/cerrar el portal, comprueba el panel antes de reenviar: la clave del formulario no persiste entre recargas.

## 7. Pruebas reproducibles

Las pruebas JavaScript requieren Node 22.22.2+ de la serie 22, Node 24.15+ de la serie 24 o Node 26+.

```bash
python -m pytest backend/tests -q
python -m unittest ai_engine.test_search_engine -v
npm ci
npm test
python -m compileall -q app.py backend ai_engine scripts
```

La prueba DOM inicia un Flask aislado en el puerto 5137, usa datos de demostración y no modifica tu base local. El motor se prueba con FAISS real y un encoder determinista; adicionalmente se verificó el modelo multilingüe real. Consulta `docs/ESTADO.md` para el alcance de las verificaciones.


Para verificar el circuito con una instalación de n8n real, con una base temporal independiente:

```bash
python scripts/check_n8n.py --n8n-bin RUTA_AL_EJECUTABLE_N8N
```

La verificación importa credenciales ficticias y el flujo en un directorio temporal, lo publica, levanta n8n en el puerto 5679 (broker 5681) y Flask en el 5141. Comprueba recepción, respuesta, autenticación e idempotencia y detiene ambos servicios. No utiliza tu instancia habitual de n8n.
