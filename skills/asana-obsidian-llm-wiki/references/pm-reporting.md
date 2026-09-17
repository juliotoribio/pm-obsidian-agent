# PM Reporting (Métricas y Reportes)

## 1. El falso "0/N Tablero Desactualizado" (Importaciones MS Project)
Cuando los proyectos en Asana provienen de importaciones (e.g. MS Project), el progreso se inscribe como texto plano en el cuerpo de las notas de la tarea, mientras que el flag nativo `completed` de Asana suele quedarse en `false`.

**Regla de Oro:** NUNCA reportes un proyecto como "estancado", "abandonado" o al 0% sin haber revisado primero las notas de las tareas.
Utiliza el script `mark_completed_from_notes.py <GID>` para reconciliar esta discrepancia. El script leerá el texto buscando `Completed: TRUE` y forzará el cierre de la tarea en Asana.

## 2. Bloqueadores vs Tareas Vencidas
Al armar reportes de estado o priorizar tareas:
- **Tareas Vencidas:** No siempre detienen el proyecto.
- **Bloqueadores Reales:** Una tarea abierta que tenga la propiedad `Status: Bloqueado` en sus notas es un cuello de botella.
Siempre resalta y reporta los bloqueadores primero antes de listar el volumen de tareas vencidas.

## 3. Dependencias e Inconsistencias
Extrae la información del campo de nota `Dependents:`. Si una tarea dependiente tiene una fecha de entrega (`due_on`) *anterior* a su tarea bloqueadora, reporta el hallazgo como "orden de dependencia imposible" para intervención humana.
NO modifiques ni ajustes fechas automáticamente en Asana para cuadrar esto.
