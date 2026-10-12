# Usar el proyecto con IA local

El asistente ayuda al DPO a encontrar documentos y revisar cada solicitud. Usa un modelo multilingüe de SentenceTransformers y FAISS en tu computadora. Muestra fragmentos y sus fuentes; el responsable revisa la información y decide la actuación.

## Iniciar en Linux Mint

Desde la carpeta del proyecto, detén el Flask anterior con Ctrl+C y ejecuta:

```bash
cd ~/Proyectos/agente-dsar
python3 iniciar.py --demo
```

El comando crea o reutiliza `.venv`, instala las dependencias necesarias, prepara configuración y tablas, descarga el modelo la primera vez, actualiza el índice y comprueba la IA con una búsqueda real. Luego inicia Flask y abre el panel DPO. La primera preparación requiere Internet y puede tardar. En los siguientes inicios reutiliza las dependencias y el modelo locales.

`--demo` agrega titulares ficticios sin borrar datos existentes. Omítelo para trabajar sin ejemplos. La clave DPO se muestra sólo en la terminal interactiva local: cópiala en el panel y pulsa Entrar al panel. También está en `backend/.env`; no se incluye en Git ni en la URL. La terminal debe permanecer abierta; Ctrl+C detiene el proyecto. Si el puerto 5000 está ocupado, detén la instancia anterior o usa `--port 5001`.

Si Python indica que falta `venv`, instala `sudo apt install python3-venv`. Si el navegador no se abre, utiliza http://127.0.0.1:5000/dpo. Para iniciar sin abrirlo automáticamente, añade `--no-browser`.

En Windows, desde la carpeta del proyecto:

```powershell
py -3.12 iniciar.py --demo
```

Este flujo local permite usar el portal y la IA antes de configurar n8n. Si ya tienes configurado el modo n8n, conserva esa configuración y mantén n8n encendido. Las instrucciones de n8n están en las guías de [Linux](CONFIGURAR_LINUX.md) y [Windows](CONFIGURAR_WINDOWS.md).

## Atender una solicitud

1. Abre el portal del titular en http://127.0.0.1:5000 y registra una solicitud de prueba con ID `72839102`, correo `juan@example.com` y derecho Acceso.
2. En el panel DPO, abre Solicitudes y pulsa Revisar. Se carga el documento, los datos registrados y una orientación según el derecho solicitado.
3. Pulsa Buscar documentos con IA. La búsqueda queda limitada a documentos indexados que mencionan el ID seleccionado. Cada tarjeta muestra fuente, fragmento y similitud temática. El indicador IA lista confirma que el modelo y el índice se pudieron cargar.
4. Cambia la consulta o utiliza las sugerencias para encontrar información de contacto, publicidad o conservación. Puedes desmarcar el filtro del titular para una búsqueda general autorizada.
5. Para revisar un fragmento antes de entregar información, pulsa Revisar y ocultar datos de este fragmento y luego Ocultar coincidencias. Los nombres se añaden automáticamente si el titular está registrado. Revisa el resultado y los datos de terceros.
6. En Datos del titular consulta los datos, descarga el JSON portable o realiza la rectificación/supresión autorizada. Regresa a Solicitudes para guardar la nota, actualizar el estado y descargar la constancia PDF.

La similitud no es una probabilidad de certeza. El filtro encuentra documentos por una mención literal del ID: un documento puede mencionar más de una persona y debe revisarse. Si el ID no aparece en los documentos indexados, se muestra un resultado vacío, sin sustituirlo por documentos de otro titular. La recepción de una solicitud no da de alta automáticamente un titular en la base.

## Usar tus propios documentos

Guarda archivos `.txt` en UTF-8 o PDF con texto seleccionable en `ai_engine/documentos`. Los PDF escaneados requieren obtener su texto antes; el proyecto no incluye OCR. Para que una solicitud encuentre sus documentos con el filtro activado, éstos deben mencionar su documento/ID completo. Guarda sólo información que corresponda procesar en este proyecto.

Detén Flask y vuelve a ejecutar `python3 iniciar.py` para actualizar el índice. El modelo ya descargado se reutiliza. Una ruta de modelo local existente configurada en `EMBEDDING_MODEL` se conserva. También puedes comprobar la IA sin arrancar el portal:

```bash
python3 iniciar.py --solo-preparar
```

La búsqueda utiliza el índice local. Después de borrar o modificar documentos, vuelve a preparar el índice: la supresión SQL no borra archivos ni copias anteriores del índice. No se envían las consultas o los documentos a una API de IA externa. La primera descarga del modelo sí necesita acceso a Internet.

## Verificación y límites

Se verificaron el arranque, el estado autenticado de IA, una consulta con el modelo real y el filtro por ID. Las pruebas automatizadas cubren el panel guiado, renderizado seguro de fragmentos, resultados vacíos, fallos y limpieza al cerrar sesión. La autorización de actuaciones sigue a cargo del DPO. El ZIP del expediente y el envío por correo son funciones pendientes.
