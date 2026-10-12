# Configurar el agente DSAR en Linux

El backend, el portal, el panel DPO y la conexión con n8n se pueden ejecutar en Linux y Windows. Esta guía usa Bash y una instalación local de Flask y n8n. La rama de trabajo es `feat/flask-faiss-n8n`; main recibe los cambios al fusionar el PR.

## 1. Instalar Python y Git

En Ubuntu 24.04 LTS o Debian 12, instala los paquetes del sistema:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
python3 --version
```

El proyecto requiere Python 3.11 o superior; se ha comprobado con 3.11 y 3.12. Ubuntu 24.04 ofrece Python 3.12 y Debian 12 ofrece Python 3.11. En otra distribución, instala Python y su módulo `venv` con su gestor de paquetes. Si `python3 --version` muestra una versión inferior a 3.11, instala una versión compatible antes de continuar y úsala para crear el entorno.

## 2. Obtener el proyecto y preparar Flask

Para una instalación nueva:

```bash
mkdir -p ~/Proyectos
cd ~/Proyectos
git clone --branch feat/flask-faiss-n8n https://github.com/JeremyCruzGallegos/agente-dsar-iso27701.git agente-dsar
cd agente-dsar
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python scripts/setup.py --demo
.venv/bin/python app.py
```

Si ya tienes un clon, entra en su carpeta y utiliza la rama indicada; no necesitas clonarlo de nuevo. Mantén abierta la terminal de Flask mientras usas la aplicación. Los comandos utilizan directamente el Python del entorno virtual, sin necesitar activarlo ni instalar paquetes con `sudo pip`.

Abre http://127.0.0.1:5000 en el navegador de esa computadora. Envía una solicitud de Acceso con el documento ficticio `72839102` y un correo válido. Debe aparecer un ticket real.

Abre http://127.0.0.1:5000/dpo. Con tu editor de texto, abre `backend/.env` y copia el valor de **DPO_API_KEY**, sin las comillas, en el panel. Conserva las claves en tu computadora.

La preparación genera las claves y crea las tablas que faltan sin borrar registros existentes. `--demo` agrega dos titulares ficticios. El modo inicial `DSAR_INTAKE_MODE=direct` permite registrar solicitudes antes de configurar n8n.

## 3. Activar la búsqueda de IA

Detén Flask con **Ctrl+C**. Desde la carpeta del proyecto:

```bash
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r ai_engine/requirements.txt
.venv/bin/python scripts/prepare_ai.py
.venv/bin/python app.py
```

La primera preparación descarga el modelo, guarda su ruta en `.env` y crea el índice FAISS. Prueba en DPO la búsqueda `correo electrónico de Juan Pérez`. Si cambias documentos o modelo, vuelve a ejecutar la preparación y reinicia Flask.

Si tienes un modelo ya descargado, puedes prepararlo sin descargarlo otra vez:

```bash
.venv/bin/python scripts/prepare_ai.py --local-model /ruta/al/modelo
```

Si tu proxy SOCKS provoca un error relacionado con `socksio`, instala `.venv/bin/python -m pip install "httpx[socks]"` y repite la preparación.

## 4. Instalar Node.js y arrancar n8n

Para n8n utiliza **Node.js 24 LTS**. En https://nodejs.org/en/download selecciona Linux, la serie 24 LTS y el método de instalación correspondiente a tu distribución. Si ya usas `nvm`, puedes seleccionar esta versión con:

```bash
nvm install 24
nvm use 24
```

Abre otra terminal y verifica la versión instalada:

```bash
node --version
npm --version
npx --yes n8n@2.42.7
```

`node --version` debe mostrar `v24.x`. Si usas `nvm` y otra versión aparece en una terminal nueva, ejecuta `nvm use 24` en esa terminal antes de iniciar n8n. La versión n8n 2.42.7 es la utilizada en la verificación de la integración. No necesita instalación global ni `sudo npm`.

Deja abierta esta segunda terminal. Abre http://127.0.0.1:5678 y crea tu cuenta local de n8n. Esta cuenta es independiente de la clave del panel DPO.

## 5. Importar y conectar el workflow

Crea un workflow e importa `n8n_workflows/dsar-request.json` desde la carpeta del proyecto con **Import from File**. Crea estas dos credenciales de tipo **Header Auth** usando los valores de tu archivo `backend/.env`:

| Nombre de la credencial | Campo Name | Campo Value |
| --- | --- | --- |
| DSAR Webhook | X-Webhook-Token | Valor de N8N_WEBHOOK_TOKEN |
| DSAR Backend | X-API-Key | Valor de SERVICE_API_KEY |

Copia solamente los valores, sin sus comillas. En **Recibir DSAR**, selecciona DSAR Webhook. En **Crear ticket en Flask**, selecciona DSAR Backend y verifica la URL `http://127.0.0.1:5000/api/requests`. Conserva el nodo **Responder ticket real** y guarda y publica/activa el workflow.

Edita estas líneas en `backend/.env`, manteniendo las claves generadas:

```dotenv
DSAR_INTAKE_MODE=n8n
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/dsar-request
```

Detén Flask con Ctrl+C y vuelve a iniciarlo:

```bash
cd ~/Proyectos/agente-dsar
.venv/bin/python app.py
```

Envía otra solicitud desde el portal y comprueba el ticket en DPO. El circuito utiliza Flask, n8n y la API privada de Flask. La URL permanente utiliza `/webhook/`; `/webhook-test/` sólo funciona durante una prueba manual del workflow.

## 6. Diagnóstico y siguientes sesiones

Con ambos servicios encendidos, desde otra terminal en la carpeta del proyecto:

```bash
.venv/bin/python scripts/diagnose.py
```

El diagnóstico comprueba configuración, base, API y conexión con n8n sin imprimir las claves ni enviar solicitudes. Para volver a usar el proyecto:

- Primera terminal en el proyecto: `.venv/bin/python app.py`.
- Segunda terminal con Node 24: `npx --yes n8n@2.42.7`.

| Problema | Acción |
| --- | --- |
| `No module named venv` o `ensurepip is not available` | Instala el paquete `venv` correspondiente a tu Python y vuelve a crear el entorno. |
| `externally-managed-environment` | Usa `.venv/bin/python -m pip`, como en esta guía. |
| `node` o `npx` no encontrado | Termina la instalación de Node 24 y abre otra terminal. |
| El panel devuelve 401 | Copia DPO_API_KEY sin comillas. |
| n8n devuelve 404 | Publica el workflow y revisa `/webhook/dsar-request`. |
| n8n devuelve 401/403 | Revisa las dos credenciales Header Auth y sus claves. |
| Conexión rechazada o 503 | Mantén ambos servicios abiertos y verifica los puertos 5000 y 5678. |
| FAISS devuelve 503 | Instala las dependencias, prepara el modelo/índice y reinicia Flask. |

Si cambias de Windows a Linux, crea un entorno `.venv` nuevo e instala las dependencias en Linux. Los entornos virtuales no se copian entre sistemas. Prepara de nuevo la IA para actualizar las rutas locales. El repositorio no incluye tu `.env`, base de datos ni documentos privados: pasar a otra computadora no transfiere esos datos automáticamente.

Docker también está disponible como alternativa en [Inicio rápido](INICIO_RAPIDO.md#5-docker-opcional). Esta guía describe el uso local; para un servidor accesible desde otras computadoras hace falta configurar el despliegue, HTTPS y el acceso al servicio.

Referencias:
- Entornos virtuales Python: https://docs.python.org/3/library/venv.html
- Paquete en Ubuntu 24.04: https://packages.ubuntu.com/noble/python3-venv
- Paquete en Debian 12: https://packages.debian.org/bookworm/python3-venv
- Node.js para Linux: https://nodejs.org/en/download
- n8n con npm: https://docs.n8n.io/hosting/installation/npm/
