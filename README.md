# Agente DSAR — proyecto académico ISO/IEC 27701

Portal para registrar solicitudes de derechos del titular, panel DPO y API Flask con SQLite, auditoría, retención configurable y búsqueda semántica local con FAISS/SentenceTransformers.

## Arranque rápido

Desde la raíz, con Python 3.11+:

```bash
python3 iniciar.py --demo
```

En Windows usa `py -3.12 iniciar.py --demo`. El comando prepara el entorno, las dependencias, el modelo y el índice, comprueba una búsqueda real y abre el panel. La primera ejecución requiere Internet; las siguientes reutilizan el modelo. La clave DPO aparece sólo en la terminal interactiva local y también está en `backend/.env`. Los datos existentes se conservan. El registro funciona inicialmente sin n8n.

**[Uso sencillo con IA: iniciar y revisar una solicitud](docs/USO_SENCILLO_IA.md)**

**[Configuración en Windows](docs/CONFIGURAR_WINDOWS.md)** · **[Configuración en Linux](docs/CONFIGURAR_LINUX.md)** · **[Instrucciones completas, n8n, Docker y solución de conexión](docs/INICIO_RAPIDO.md)** · **[Estado y validaciones](docs/ESTADO.md)**

## Funciones disponibles

- Portal con tickets reales, errores visibles y reintentos idempotentes.
- DPO autenticado con lista/paginación/filtros, cambios de estado y auditoría.
- Acceso, portabilidad JSON, rectificación y anonimización de registros SQL sujeta a retención.
- Constancias PDF sin reproducir datos personales ni detalles libres del expediente.
- Panel guiado por solicitud, datos legibles y búsqueda de documentos con IA local, filtro por ID, tarjetas de resultados y paso a ocultación asistida de PII.
- Flujo n8n importable y autenticado para registrar solicitudes. La conexión pasa por Flask para mantener las credenciales de servicios fuera del navegador.
- Scripts de configuración, preparación de IA, diagnóstico y pruebas en GitHub Actions.

La recepción no acredita identidad ni ejecuta borrados automáticos. El DPO debe verificar y autorizar cada actuación. La supresión SQL no elimina documentos externos ni copias previas del índice: requieren tratamiento y reconstrucción del índice por el responsable. El plazo de respuesta es un parámetro interno, no una determinación legal universal. La ocultación por reglas requiere revisión humana. Este proyecto no constituye una certificación ISO.

## Estructura

```text
frontend/         Portal, panel DPO y pruebas JS/DOM
backend/          API, modelos, servicios, pruebas y .env.example
ai_engine/        Embeddings locales, índice FAISS y documentos ficticios
n8n_workflows/    dsar-request.json importable
scripts/          setup.py, prepare_ai.py y diagnose.py
iniciar.py        Preparación de IA y arranque con un comando
docs/             Inicio rápido y estado verificado
app.py            Arranque desde la raíz
Dockerfile        Backend con Gunicorn y soporte PDF
compose.yaml      Backend y n8n con volúmenes persistentes
```

## API

| Ruta | Acceso | Uso |
| --- | --- | --- |
| GET `/api/health` | Público | Conexión SQL y tablas inicializadas |
| POST `/api/intake` | Público, Idempotency-Key requerido | Registro desde el portal; sólo devuelve ticket |
| POST/GET `/api/requests` | Servicio / DPO | Registro interno y listado |
| GET `/api/requests/<ticket>` | Servicio / DPO | Detalle |
| PATCH `/api/requests/<ticket>/status` | Servicio / DPO | Transiciones validadas |
| GET `/api/requests/<ticket>/report.pdf` | DPO | Constancia y trazabilidad |
| GET `/api/user-data?user_id=...` | Servicio / DPO | Acceso; `format=portable` para JSON portable |
| POST `/api/users` | Servicio / DPO | Alta de titular |
| PATCH `/api/rectify-user` | Servicio / DPO | Cambios de nombre/correo |
| POST `/api/delete-user` | Servicio / DPO | Anonimización con control de retención |
| POST `/api/vector-search` | Servicio / DPO | `{"query":"texto","k":5}`; índice/modelo deben estar preparados |
| GET `/api/ai/status` | DPO | Comprueba modelo/índice reales; muestra disponibilidad y recuentos |
| POST `/api/redact` | Servicio / DPO | `{"text":"texto","values":["nombre"]}`; revisión obligatoria |
| GET `/api/audit-log` | DPO | Bitácora con filtros y paginación |

Las rutas privadas usan `X-API-Key`. La auditoría referencia documentos con HMAC; no almacena las consultas semánticas ni el texto procesado por redacción. Conserva metadatos operativos, incluido actor y dirección IP. No incluye las claves en el código cliente. Configuración en `backend/.env`, excluida de Git.

## Modelo local

```bash
python -m pip install -r ai_engine/requirements.txt
python scripts/prepare_ai.py
```

Reinicia Flask y utiliza la búsqueda del panel. Una respuesta 503 identifica modelo/índice/dependencias ausentes; no se sustituyen los resultados por datos inventados.

La API vector-search admite `user_id` opcional para ordenar sólo fragmentos de documentos que mencionan literalmente ese ID. El filtro no acredita identidad ni evita que un archivo contenga datos de terceros; el DPO revisa los resultados. Con `iniciar.py`, la preparación y actualización del índice se realizan antes de arrancar.
