# Protocolo de Conocimiento Hermes (Hermes Knowledge Protocol)

Este documento establece las reglas de gobierno y escalamiento de permisos entre los usuarios humanos (PMs) y los agentes de la serie Hermes (Maha, Antigravity, etc.) sobre la bóveda de Obsidian (`PM-Obsidian`).

## 1. Autoridad Operativa vs. Documental
- **Asana** es la única fuente de verdad **operativa** (fechas, responsables, estado).
- **Obsidian** es la única fuente de verdad **documental** (riesgos elaborados, minutas, decisiones, contexto histórico).

## 2. Invariantes de Sincronización (Regla de Oro)
La sincronización Asana → Obsidian es de **un solo sentido** y está diseñada para nunca destruir el conocimiento humano:
1. Ningún proceso automatizado modificará contenido fuera del bloque `<!-- HERMES:START -->` y `<!-- HERMES:END -->`.
2. La cabecera `## Notas humanas` está estrictamente reservada para el usuario.
3. El motor de sincronización **nunca** borra archivos. Las bajas se gestionan manualmente o archivando el proyecto en Asana.

## 3. Escalamiento de Permisos
Por defecto, los agentes operan con credenciales de **solo lectura** hacia el entorno productivo.
Cualquier escritura masiva (ej. `asana_bulk_status.py` o `mark_completed_from_notes.py`) requiere:
- Ejecución explícita (el usuario provee el flag `--apply`).
- Trazabilidad y validación previa con `dry-run`.

## 4. Estructura y Taxonomía (Fase 1)
- `00 Portafolio`: Índices y dashboards globales (generados y mantenidos por el agente).
- `01 Programas`: Agrupadores estratégicos (Portafolios de Asana).
- `02 Projects`: Notas individuales sincronizadas desde Asana.
- `09 Vistas`: Consultas Dataview estandarizadas (ej. Bloqueados).

## 5. Auditoría de Eliminaciones (Sección 12)
Cuando un PM decide eliminar permanentemente una tarea o proyecto en Asana (en lugar de archivarla, que es lo recomendado), el agente debe usar la herramienta `--record-deletion` para dejar una traza indeleble en la sección `## Notas humanas` del proyecto afectado, documentando la fecha y GID original.

*La adopción de MCP para interacciones ad-hoc está documentada en su propia decisión arquitectónica.*
