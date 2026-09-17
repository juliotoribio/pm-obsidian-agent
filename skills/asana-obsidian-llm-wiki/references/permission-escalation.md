# Permission Escalation & Seguridad

Reglas restrictivas sobre lo que el script y el agente tienen permitido hacer.

## 1. Operaciones contra Asana (GET-only)
El script principal `asana_obsidian_sync.py` está estrictamente diseñado para ser **GET-only** contra la API de Asana.
Su función es leer el estado y los metadatos de los portafolios, proyectos y tareas. **No debe** crear tareas, modificar fechas, ni cerrar proyectos directamente. Para hacer escrituras, se deben utilizar scripts atómicos separados (como `mark_completed_from_notes.py`) previa confirmación humana si es necesario.

## 2. Operaciones contra Obsidian (Marker-safe)
La bóveda de Obsidian es un espacio mixto: humano y máquina.
- El agente solo tiene permitido escribir dentro de los bloques delimitados por `<!-- HERMES:START -->` y `<!-- HERMES:END -->`.
- El bloque inferior comúnmente llamado `## Notas humanas` jamás debe ser sobreescrito, modificado o parseado para extracción destructiva.
- Está prohibido borrar archivos del vault automáticamente a menos que un humano lo solicite explícitamente (e.g., usando un script `clean_orphans.py`).
