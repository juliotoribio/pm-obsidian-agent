---
name: asana-obsidian-llm-wiki
description: "Sincroniza proyectos de Asana hacia notas de Obsidian respetando bloques de contenido manual humano. Usa los scripts de python en `scripts/` para la integración de doble vía. DEPENDENCIES: requiere configuración previa del token de asana en el .env de Hermes."
version: 1.0.0
platforms: [macos, linux]
author: PM Agent Team
tags: [asana, obsidian, sync, api, python]
---

# Asana Obsidian Sync

Este skill define la lógica operativa para que el agente PM pueda sincronizar el estado de Asana con la base de conocimiento de Obsidian.

## Responsabilidades Principales
1. Ejecutar el script `asana_obsidian_sync.py` para materializar nuevos proyectos de Asana en la bóveda.
2. Leer y escribir notas dentro de la bóveda **ESTRICTAMENTE** dentro de los marcadores `<!-- HERMES:START -->` y `<!-- HERMES:END -->`.
3. Validar variables de entorno (`ASANA_ACCESS_TOKEN`, `OBSIDIAN_VAULT_PATH`).
4. Utilizar scripts complementarios (como `mark_completed_from_notes.py`) para cerrar el ciclo hacia Asana.

## Reglas Críticas
- **Seguridad y Tono**: Revisa los lineamientos en `references/pm-workflow.md` para entender el estilo de comunicación de este agente.
- **Manejo de Credenciales**: No uses `os.environ` directo para leer el token en Python; consulta `references/credential-handling.md` para entender cómo opera el lector del `.env`.
- **Manejo de Permisos (GET-only)**: La sincronización estándar de Asana hacia Obsidian es `GET-only` contra Asana. Revisa `references/permission-escalation.md`.
- **Reporting y Agrupación**: Lee `references/pm-reporting.md` para entender por qué la verdad de las tareas completadas viene de las notas de Obsidian (`Completed: TRUE`) y no del flag nativo de Asana.
- **Runbook / Troubleshooting**: Si encuentras errores 403 o fallas de YAML, consulta `references/runbook.md`.

## Uso del Script Principal
```bash
python scripts/asana_obsidian_sync.py --vault "Ruta/A/Boveda"
```
El script generará un plan de actualización en la terminal. Ninguna modificación al archivo local fuera de los bloques de marcadores será realizada.
