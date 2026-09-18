# Roadmap funcional

Estado actual: el sistema **refleja** el portafolio (espejo navegable de Asana con dashboards). El objetivo es que lo **gobierne**: detectar desviación, explicarla y forzar decisión.

Cada punto lleva **Qué**, **Restricciones** y **Aceptación**. La aceptación es el contrato: nada se da por cerrado sin ella.

**Reglas transversales para todo incremento:**

- Un punto por vez. No abrir el siguiente hasta cerrar el anterior.
- El sync (`asana_obsidian_sync.py`) sigue **GET-only** contra Asana.
- Nada se escribe fuera de `<!-- HERMES:START -->` / `<!-- HERMES:END -->` salvo frontmatter y las rutas explícitamente autorizadas aquí.
- `## Notas humanas` intacto byte a byte.
- Todo incremento agrega su test a `test_sync.py` y la suite completa debe pasar.
- Todo incremento se demuestra con `--dry-run` antes de aplicar.

---

## Fase 1 — La dimensión temporal

Sin histórico no hay análisis de desviación, y sin análisis de desviación no hay PMO. Todo lo demás se cuelga de aquí.

### 1. Snapshots históricos y baseline

**Qué**

- En cada `--apply`, escribir `03 Log/YYYY-MM-DD.md` con una fila por proyecto: `asana_gid`, nombre, `status`, `tasks_total`, `tasks_done`, `tasks_blocked`, `due_date`, `pct`. Un archivo por día; si ya existe, sobrescribir.
- Agregar al frontmatter de proyecto:
  - `baseline_due_date` — se fija al crear la nota y **nunca** se vuelve a escribir.
  - `replan_count` — incrementa cuando `due_date` difiere del valor del sync anterior.
  - `slip_days` — diferencia en días entre `due_date` y `baseline_due_date`.

**Restricciones**

- El log vive en `03 Log/`, fuera de `02 Projects`.
- Los tres campos nuevos respetan la preservación de frontmatter existente.
- `baseline_due_date` es inmutable: si ya tiene valor, el sync lo deja.

**Aceptación**

- Test que simule dos syncs con `due_date` distinta y verifique: `baseline_due_date` sin cambio, `replan_count == 1`, `slip_days` correcto, y dos archivos en `03 Log/`.
- Suite completa en verde + `--dry-run` mostrado.

### 2. Status report por corte

**Qué**

- Script `generate_status_report.py <FECHA_DESDE> <FECHA_HASTA>` que compara dos snapshots de `03 Log/` y produce `03 Log/Reporte YYYY-MM-DD.md` con:
  - Qué cambió desde el corte anterior (proyectos que entraron/salieron de riesgo).
  - Proyectos en rojo, con su bloqueador crítico.
  - Fechas que se movieron, con `replan_count` y `slip_days`.
  - Decisiones que requiere el comité.

**Restricciones**

- No abrir hasta que el punto 1 lleve al menos dos cortes **reales** (no sintéticos).
- Solo lee snapshots; nunca consulta Asana.
- Si falta uno de los dos snapshots, falla con mensaje claro y no escribe nada.

**Aceptación**

- Test con dos snapshots fixture que verifique que el reporte detecta: un proyecto que pasó a rojo, una fecha movida y un bloqueador nuevo.
- Reporte generado sobre dos cortes reales del portafolio.

---

## Fase 2 — Señal de alto impacto, bajo costo

### 3. Salud declarada vs calculada (*watermelon detection*)

**Qué**

- Campo `rag_declarado` en el frontmatter (Verde/Ámbar/Rojo), poblado desde `current_status.color` de Asana.
- Fórmula `rag_calculado` derivada de bloqueos, `slip_days` y % de avance.
- Vista `09 Vistas/Discrepancia RAG.base` que liste los proyectos donde declarado = Verde y calculado = Rojo.

**Restricciones**

- Nunca sobrescribir el RAG declarado por el PM: es dato de origen, no derivado.
- La discrepancia se reporta como hallazgo, jamás se "corrige" en Asana.
- `rag_declarado` y `rag_calculado` son independientes y cada uno puede ser gris (sin dato).
- La discrepancia solo se evalúa cuando ambos tienen valor. Nunca inferir uno desde el otro.
- Si falta `rag_declarado`, el proyecto va a una sección aparte —"sin RAG declarado"— que es hallazgo de gobierno, no de riesgo. No cuenta como watermelon.

**Aceptación**

- Test de la fórmula con tres casos: coincidencia, watermelon (verde/rojo) y falso alarmista (rojo/verde).
- Dos casos adicionales: declarado ausente con calculado rojo (debe caer en "sin RAG declarado", no en watermelon), y ambos ausentes (gris, sin ruido).
- El `.base` valida con `yaml.safe_load` y renderiza en Obsidian.

### 4. Hitos

**Qué**

- Agregar `resource_subtype` a los `opt_fields` de `fetch_project_tasks`.
- Campos `milestones_total`, `milestones_done`, `next_milestone`, `next_milestone_date` en el frontmatter.
- Sección de hitos dentro del bloque HERMES, separada de las tareas.

**Restricciones**

- Un hito es una tarea con `resource_subtype == "milestone"`; se cuenta en hitos **y** en el total de tareas.
- La reconciliación desde notas (`Completed: TRUE`) aplica igual a hitos.

**Aceptación**

- Test con un proyecto mixto (tareas + hitos) que verifique conteos separados y `next_milestone` correcto.

---

## Fase 3 — Módulos nuevos

### 5. Capa de personas

**Qué**

- Carpeta `03 People/` con una nota por persona: `type: persona`, nombre, proyectos donde aparece.
- Campos agregados por persona: tareas abiertas, vencidas, bloqueadas, proyectos activos.
- Vista `09 Vistas/Carga por persona.base` ordenada por tareas abiertas.
- Señal de bus factor: proyectos con un único assignee en toda su ruta crítica.

**Restricciones**

- El sync ya trae `assignee.name` y hoy lo descarta; usarlo.
- Las notas de persona se crean si no existen y nunca se sobrescriben fuera del bloque HERMES.
- Sin datos sensibles: solo nombre, carga y vínculos de proyecto.

**Aceptación**

- Test con tres proyectos y dos personas que verifique conteos correctos por persona y detección de bus factor.

### 6. Dimensión financiera

**Qué**

- Campos manuales en el frontmatter de proyecto: `capex_budget`, `opex_budget`, `spend_ytd`, `capitalization_status`.
- Agregación en `00 Portafolio.base`: suma por programa y total de portafolio.
- Vista de proyectos con CAPEX sin `capitalization_status` definido.

**Restricciones**

- Asana no es fuente de estos datos: son manuales y el sync **nunca** los pisa.
- Tratarlos como opcionales: las fórmulas llevan guarda `if()` o la Base falla en silencio.

**Aceptación**

- Test que verifique que dos syncs consecutivos preservan los cuatro campos intactos.
- Base con sumas por programa validada en Obsidian.

### 7. Registro de riesgos

**Qué**

- Carpeta `06 Risks/` con una nota por riesgo: `type: riesgo`, `proyecto` (wikilink), `probabilidad`, `impacto`, `owner`, `mitigacion`, `estado`, `fecha_revision`.
- Vista `09 Vistas/Riesgos abiertos.base` ordenada por exposición (probabilidad × impacto).

**Restricciones**

- Los riesgos son **notas humanas**, no generados por el sync. El sync solo enlaza desde la nota de proyecto.
- El bloque "Riesgos y bloqueos" del sync sigue siendo lo que Asana señala; el registro formal es otra cosa y no se mezclan.

**Aceptación**

- Plantilla de riesgo + Base que agregue por proyecto y por exposición.
- Test de que el sync no toca `06 Risks/`.

---

## Fase 4 — Alcance y proactividad

### 8. Multi-workspace / multi-OpCo

**Qué**

- `plan_sync` hoy toma `workspaces[0]`. Soportar N workspaces, con `workspace` en el frontmatter como dimensión de agrupación.
- Flag `--workspace` acepta varios, o `--all-workspaces`.

**Restricciones**

- Identidad sigue siendo `asana_gid`; dos workspaces no pueden colisionar.
- Los Bases agrupan por programa dentro de workspace, no entre workspaces.

**Aceptación**

- Test con dos workspaces mockeados que verifique que no hay colisión de notas ni de programas.

### 9. Digest proactivo

**Qué**

- Script que, tras cada corte, emita un resumen accionable: proyectos sin movimiento en N días, owners sobrecargados, hitos en riesgo, discrepancias RAG.
- Salida a Telegram (el gateway ya existe en el stack).

**Restricciones**

- **Registrar un hallazgo ≠ autorización para ejecutarlo.** El digest informa y propone; nunca actúa.
- Sin acciones de escritura hacia Asana desde este camino.

**Aceptación**

- Digest generado sobre datos reales, revisado a mano antes de conectarlo al gateway.

### 10. Gestión de demanda (producto aparte)

**Qué**

- Todo lo anterior asume proyectos ya en ejecución. La demanda vive antes: solicitudes, priorización, aprobación, conversión a proyecto.
- Módulo propio: `08 Demanda/` con estados de intake y criterios de priorización.

**Restricciones**

- No mezclar con el sync de Asana: una solicitud no es un proyecto hasta que se aprueba.
- Evaluar antes si el intake debe vivir en Asana o fuera.

**Aceptación**

- Definir el modelo de datos antes de escribir código.

---

## Orden recomendado

1. **Punto 1** — desbloquea todo lo demás.
2. **Punto 2** — solo tras dos cortes reales.
3. **Puntos 3 y 4** — baratos, visibles, alto impacto ante comité.
4. **Puntos 5, 6, 7** — módulos nuevos, en ese orden.
5. **Puntos 8 y 9** — cuando el modelo esté estable.
6. **Punto 10** — producto aparte, decisión de alcance previa.
