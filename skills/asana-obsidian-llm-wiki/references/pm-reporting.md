# PM Reporting (Métricas y Lógica)

Este documento detalla la filosofía de recolección de métricas y reporte de progreso de los proyectos en Obsidian.

## 1. El Bug del "0/N Tablero Desactualizado"
En Asana, el flag nativo de `completed` en una tarea de alto nivel suele estar desactualizado porque la gente olvida marcarlo, aunque escriban en las notas de la tarea que el trabajo ya fue entregado.
Para solucionar esto, nuestra fuente de verdad es la **nota textual**. El script lee las notas de la tarea buscando la cadena `Completed: TRUE` (generada mediante importación de MS Project o anotada por humanos). Si existe, el script cuenta la tarea como finalizada (`tasks_done`), independientemente de si la interfaz de Asana dice que está abierta.

## 2. Bloqueadores (Blockers)
Nuestra regla principal en el reporte ejecutivo (Portafolio) es **reportar el bloqueador real antes que el conteo de vencidas**.
- Una tarea vencida no siempre detiene un proyecto.
- Una tarea etiquetada o anotada como `Status: Bloqueado` es crítica.
- La vista de Bases siempre filtra y ordena primero por `tasks_blocked > 0`.

## 3. Dependencias Imposibles
El mapeo de dependencias extrae el campo `Dependents:` de las notas. No alteramos fechas automáticamente en Asana. Si detectamos dependencias circulares, o una tarea bloqueante que tiene una fecha de entrega *posterior* a su dependiente, reportamos el hallazgo como "orden imposible" para intervención humana.
