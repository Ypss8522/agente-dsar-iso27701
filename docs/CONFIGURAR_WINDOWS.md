# Configurar el agente DSAR en Windows

Para preparar IA y abrir el panel con un comando, sigue [Uso sencillo con IA](USO_SENCILLO_IA.md). Esta guía conserva los pasos manuales y la configuración de n8n.

Estas instrucciones usan Windows 10/11 y PowerShell. El proyecto integrado se obtiene desde `main`.

## 1. Python y Node.js

Instala **Python Install Manager** desde https://www.python.org/downloads/windows/ si todavía no tienes Python 3.12. Con el gestor instalado, abre una nueva ventana PowerShell:

```powershell
pymanager install 3.12
py -3.12 --version
```

Si ya tienes Python 3.12 y el segundo comando funciona, puedes continuar.

Instala **Node.js 24 LTS** desde https://nodejs.org/en/download, seleccionando Windows y su instalador MSI. Es compatible con la versión n8n 2.42.7 utilizada en las pruebas. Abre de nuevo PowerShell después de instalar y comprueba:

```powershell
node --version
npm.cmd --version
```

## 2. Descargar la rama correcta

Abre:
https://github.com/JeremyCruzGallegos/agente-dsar-iso27701/tree/main

Selecciona **Code → Download ZIP**. Extrae el contenido del proyecto en `C:\Proyectos\agente-dsar`. Esa carpeta debe contener `app.py`, `backend`, `frontend` y `scripts`, sin una segunda carpeta del proyecto anidada.

Si ya tienes Git instalado, también puedes clonar directamente la rama:

```powershell
git clone --branch main https://github.com/JeremyCruzGallegos/agente-dsar-iso27701.git C:\Proyectos\agente-dsar
```

## 3. Instalar y preparar Flask

En PowerShell:

```powershell
cd C:\Proyectos\agente-dsar
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\setup.py --demo
.\.venv\Scripts\python.exe app.py
```

Se utiliza directamente el ejecutable del entorno virtual en cada comando. Mantén abierta esta ventana mientras usas la aplicación.

Abre http://127.0.0.1:5000. Envía una solicitud de Acceso con el documento ficticio `72839102` y un correo válido. Debe aparecer un ticket real.

Para el panel, abre http://127.0.0.1:5000/dpo. En otra ventana o desde el explorador, abre `backend\.env` con Bloc de notas y copia el valor **DPO_API_KEY**, sin las comillas. Esa es la clave que se introduce en el panel. Las claves se generan automáticamente y permanecen locales.

Para abrir el archivo desde PowerShell en la carpeta del proyecto:

```powershell
notepad backend\.env
```

El modo inicial `DSAR_INTAKE_MODE=direct` permite comprobar Flask y el panel antes de conectar n8n. La configuración y la base se crean sin borrar registros existentes. `--demo` agrega dos titulares ficticios.

## 4. Activar la búsqueda de IA

Detén Flask con **Ctrl+C** en su ventana. Ejecuta:

```powershell
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r ai_engine\requirements.txt
.\.venv\Scripts\python.exe scripts\prepare_ai.py
.\.venv\Scripts\python.exe app.py
```

El modelo se descarga la primera vez. La preparación guarda su ruta en `.env` y crea el índice. En DPO prueba la búsqueda `correo electrónico de Juan Pérez`. Mantén abierta la ventana de Flask.

Si tu conexión usa un proxy SOCKS y aparece un error relacionado con socksio:

```powershell
.\.venv\Scripts\python.exe -m pip install "httpx[socks]"
.\.venv\Scripts\python.exe scripts\prepare_ai.py
```

## 5. Iniciar y configurar n8n

Abre una **segunda ventana de PowerShell** y ejecuta:

```powershell
npx.cmd --yes n8n@2.42.7
```

La primera ejecución descarga n8n. Deja abierta esta ventana. Entra en http://127.0.0.1:5678 y completa la creación de tu cuenta local de n8n.

Crea un workflow e importa `C:\Proyectos\agente-dsar\n8n_workflows\dsar-request.json` usando **Import from File**.

Abre `backend\.env` en tu computadora. Configura las dos credenciales de tipo **Header Auth**:

| Nombre de la credencial | Campo Name | Campo Value |
| --- | --- | --- |
| DSAR Webhook | X-Webhook-Token | Valor de N8N_WEBHOOK_TOKEN |
| DSAR Backend | X-API-Key | Valor de SERVICE_API_KEY |

Copia solamente los valores, sin sus comillas. No uses DPO_API_KEY como clave del servicio.

En los nodos importados:

1. **Recibir DSAR:** selecciona DSAR Webhook.
2. **Crear ticket en Flask:** selecciona DSAR Backend y verifica la URL `http://127.0.0.1:5000/api/requests`.
3. **Responder ticket real:** conserva la respuesta configurada.
4. Guarda y publica/activa el workflow. La ruta permanente es `/webhook/dsar-request`.

## 6. Cambiar el proyecto a modo n8n

Edita `backend\.env` y deja estas líneas así:

```dotenv
DSAR_INTAKE_MODE=n8n
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/dsar-request
```

Conserva las claves generadas. Guarda el archivo. Detén Flask con Ctrl+C y vuelve a iniciarlo:

```powershell
.\.venv\Scripts\python.exe app.py
```

Envía otra solicitud desde el portal. Debe aparecer un ticket que también podrás consultar en DPO. Ahora el circuito utiliza Flask, n8n y la API privada de Flask.

## 7. Diagnóstico y uso posterior

Con Flask y n8n encendidos, abre una tercera PowerShell en la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose.py
```

Debe indicar claves configuradas, base de datos disponible y n8n accesible. El diagnóstico no envía solicitudes ni imprime las claves.

En las siguientes sesiones basta con iniciar:

- Primera ventana, dentro del proyecto: `.\.venv\Scripts\python.exe app.py`.
- Segunda ventana: `npx.cmd --yes n8n@2.42.7`.

| Problema | Acción |
| --- | --- |
| `py` o `pymanager` no reconocido | Instala el gestor de Python y abre una nueva PowerShell. |
| `node` o `npx.cmd` no reconocido | Instala Node 24 y abre una nueva PowerShell. |
| El panel devuelve 401 | Verifica DPO_API_KEY y copia su valor sin comillas. |
| n8n devuelve 404 | Publica el workflow y usa `/webhook/`, no `/webhook-test/`. |
| n8n devuelve 401/403 | Revisa ambas credenciales Header Auth y sus claves correspondientes. |
| n8n 503 o conexión rechazada | Comprueba que ambas ventanas estén abiertas y las URLs usen sus puertos correctos. |
| FAISS devuelve 503 | Prepara el modelo/índice y reinicia Flask. |

Si falla un comando, comparte el texto del error y el paso. Mantén el contenido de `.env` en tu computadora.

Referencias de instalación:
- Python en Windows: https://docs.python.org/3/using/windows.html
- Node.js: https://nodejs.org/en/download
- n8n con npm: https://docs.n8n.io/hosting/installation/npm/
- FAISS CPU: https://pypi.org/project/faiss-cpu/
