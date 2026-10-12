# Trabajar en la rama de integración

Repositorio del equipo en la cuenta del propietario JeremyCruzGallegos:
https://github.com/JeremyCruzGallegos/agente-dsar-iso27701

Para obtener la versión corregida:

```bash
git clone --branch feat/flask-faiss-n8n https://github.com/JeremyCruzGallegos/agente-dsar-iso27701.git
cd agente-dsar-iso27701
```

Sigue `docs/INICIO_RAPIDO.md` para instalar dependencias, generar configuración local, preparar el modelo y conectar n8n.

Para publicar nuevas modificaciones, con GitHub autenticado y acceso de escritura:

```bash
git pull --ff-only origin feat/flask-faiss-n8n
git add ARCHIVOS_MODIFICADOS
git commit -m "Describe el cambio"
git push origin feat/flask-faiss-n8n
```

La revisión hacia main se realiza en:
https://github.com/JeremyCruzGallegos/agente-dsar-iso27701/compare/main...feat/flask-faiss-n8n

Los colaboradores se añaden desde Settings → Collaborators y deben aceptar su invitación. Las claves, bases locales, pesos del modelo e índices no se incluyen en Git. El ZIP inicial y su parche son una entrega independiente anterior a esta publicación.
