---
name: asana-obsidian-llm-wiki
description: "Sync Asana projects into an Obsidian LLM Wiki, and read/write Asana project state via REST. Orchestrates one-way synchronization (Asana -> Obsidian) via marker-safe note generation, incremental sync, and notes-driven progress reconciliation. Depends on the 'obsidian' skill for syntax and 'obsidian-pm-context' for PM structure."
version: 2.0.0
platforms: [macos, linux]
tags: [asana, obsidian, sync, pm, automation]
---

# Asana → Obsidian LLM Wiki

Este skill es el motor operativo que conecta **Asana** (fuente de verdad operativa: tareas, due dates, owners) con una **Bóveda de Obsidian** (fuente de verdad documental: minutas, contexto, decisiones).

La premisa de arquitectura es: **El agente orquesta la información desde Asana hacia Obsidian, nunca al revés para la estructura.**

## Uso del Script de Sincronización

El script `asana_obsidian_sync.py` es el núcleo de este skill. 
Lee desde la API de Asana y escribe/actualiza notas `.md` en la bóveda, inyectando propiedades de frontmatter y contenido estructurado.

```bash
# Reporte de cambios (Dry Run por defecto)
python3 scripts/asana_obsidian_sync.py --dry-run

# Aplicar escritura
python3 scripts/asana_obsidian_sync.py --apply

# Consultar la sincronización para un solo proyecto
python3 scripts/asana_obsidian_sync.py --query <GID>
```

### Invariantes del Script (Reglas de Seguridad)
1. **GET-Only contra Asana:** El script principal NUNCA escribe en Asana.
2. **Marker-Safe:** El script de sincronización escribe en Obsidian **exclusivamente** entre los delimitadores `<!-- HERMES:START -->` y `<!-- HERMES:END -->`.
3. **No Tocar Notas Humanas:** Todo lo que esté fuera de los marcadores (especialmente bajo `## Notas humanas`) se preserva bit-a-bit.
4. **Cero Eliminación:** El script no borra archivos en Obsidian (falla cerrado).

## Scripts de Operación Masiva (REST)

Cuando se requiera escribir en Asana (e.g. actualizar estado de tareas), se utilizan scripts atómicos que operan sobre REST, no sobre el MCP de Asana.

- **Cerrar tareas a partir de notas (Importación de MS Project):**
  `python3 scripts/mark_completed_from_notes.py <PROJECT_GID> --apply`
  Lee `Completed: TRUE` en el texto de las tareas de Obsidian para forzar el cierre en Asana. *(Ver `references/pm-reporting.md`)*.
- **Actualizar estatus masivo por fechas:**
  `python3 scripts/asana_bulk_status.py --project <GID> --complete-overdue --apply`
- **Cerrar tareas por nombre específico:**
  `python3 scripts/close_task.py <PROJECT_GID> "parte del nombre" --apply`

## Guías y Políticas de Operación

Antes de operar este skill, asegúrate de haber leído las guías técnicas en la carpeta `references/`:

- **[pm-reporting.md](references/pm-reporting.md):** Lógica sobre cómo extraer progreso real, el patrón de importación de MS Project, dependencias circulares y priorización de "Bloqueados".
- **[credential-handling.md](references/credential-handling.md):** Cómo manejar el `ASANA_ACCESS_TOKEN` y por qué debes evitar el redactor de secretos de Hermes leyendo directamente desde el archivo `.env`.
- **[runbook-asana-obsidian.md](references/runbook-asana-obsidian.md):** Guía de resolución de fallos silenciosos de gateways, conflictos de tokens de Telegram y diagnóstico con `asana_test_connection.py`.
