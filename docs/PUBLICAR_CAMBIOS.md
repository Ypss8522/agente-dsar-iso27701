# Trabajar en la rama de integración

Repositorio del equipo en la cuenta del propietario JeremyCruzGallegos:
https://github.com/JeremyCruzGallegos/agente-dsar-iso27701

Para obtener la versión corregida:

```bash
git clone --branch main https://github.com/JeremyCruzGallegos/agente-dsar-iso27701.git
cd agente-dsar-iso27701
```

Sigue `docs/USO_SENCILLO_IA.md` para iniciar con IA local. `docs/INICIO_RAPIDO.md` explica la instalación manual y n8n.

Para publicar nuevas modificaciones, con GitHub autenticado y acceso de escritura:

```bash
git pull --ff-only origin main
git switch -c feat/mi-mejora
git add ARCHIVOS_MODIFICADOS
git commit -m "Describe el cambio"
git push -u origin feat/mi-mejora
```

La revisión hacia main se realiza en:
https://github.com/JeremyCruzGallegos/agente-dsar-iso27701/compare/main...feat/mi-mejora

Los colaboradores se añaden desde Settings → Collaborators y deben aceptar su invitación. Las claves, bases locales, pesos del modelo e índices no se incluyen en Git. El ZIP inicial y su parche son una entrega independiente anterior a esta publicación.
