---
name: obsidian-pm-context
description: "Structure Asana-sourced project knowledge in an Obsidian vault as a 3-level portfolio (Programa -> Proyecto -> Tarea) using Obsidian-native formats: a leveled frontmatter schema, Bases (.base) for live rollups, wikilink parent-child edges, and a per-program JSON Canvas dependency map. Use when designing the vault note schema, adding a portfolio or program dashboard, wiring progress rollups that survive a stale board, or turning flat synced project notes into a navigable, self-aggregating wiki. DEPENDS ON the `obsidian` skill for all .md/.base/.canvas syntax; complements asana-obsidian-llm-wiki (sync mechanics) — this skill owns PM STRUCTURE, `obsidian` owns FORMAT, those own SYNC."
version: 1.0.0
platforms: [macos, linux]
author: adaptado de kepano/obsidian-skills (obsidian-markdown + obsidian-bases + json-canvas)
tags: [pm, obsidian, bases, portfolio, asana, spanish]
---

# Obsidian PM Context — Portafolio de 3 capas

Da **estructura de conocimiento** al vault: convierte notas de proyecto planas en
un portafolio navegable y auto-agregado. Este skill NO sincroniza (eso es
`asana-obsidian-llm-wiki`) — define
**cómo se modela la información de Programas, Proyectos y Tareas** para que
Obsidian la agregue solo, con Bases, sin scripts de reporte.

Adaptado de `kepano/obsidian-skills` (formatos `obsidian-markdown`,
`obsidian-bases`, `json-canvas`). No es una copia: el esquema, las fórmulas y la
integración marker-safe son específicos de esta arquitectura Asana -> Obsidian.

## Qué añade sobre kepano (y qué descarté)

- **Esquema atado al modelo PM de 3 niveles** e identidad por `asana_gid` — los
  Bases de kepano son genéricos; aquí filtran y agrupan por `type` y por el
  up-link `programa`, y los WikiLinks nunca se rompen al renombrar en Asana.
- **El progreso viene de las notas reconciliadas, no del flag crudo.** Las
  fórmulas leen `tasks_done`/`tasks_total` que el sync deriva de
  `Completed: TRUE` en las notas de tarea (patrón import MS Project). Esto mata
  el bug del "0/N tablero desactualizado" documentado en `pm-reporting.md`.
- **Fórmulas con guardas `if()`** en todo dato opcional (fechas faltantes en el
  portafolio) — kepano advierte que sin guarda la Base falla en silencio.
- **Integración marker-safe:** Bases y el up-link viven FUERA del bloque
  `<!-- HERMES:START -->…<!-- HERMES:END -->`; `## Notas humanas` intacto.
- **`obsidian-cli` descartado del path de sync** — exige Obsidian abierto; el
  sync es headless (escritura de archivos). Se usa solo como ayuda de consulta
  interactiva cuando el vault está abierto (`obsidian search`, `obsidian open`).

## Modelo de 3 capas — dónde vive cada nivel

```
📦 Programa   → nota .md  (contexto, objetivo, riesgos; agrega sus proyectos)
🎯 Proyecto   → nota .md  (frontmatter rico + conteos reconciliados + up-link)
✅ Tarea      → NO es nota. Vive en Asana (verdad operativa).
               Se refleja dentro del bloque HERMES del proyecto y se cuenta
               en el frontmatter del proyecto (tasks_total/done/blocked).
```

**Regla de reparto (no duplicar estado):** Asana es verdad para estado de
tareas; Obsidian es verdad para contexto/decisiones/riesgos. Materializar cada
tarea como nota rompería esa regla y duplicaría estado que cambia a diario. Las
Bases agregan a nivel Proyecto y Programa a partir de conteos, no de notas por
tarea.

Estructura de carpetas sugerida:

```
00 Portafolio.base            # dashboard raíz — todos los proyectos
01 Programas/<Programa>.md     # nota de programa + ![[<Programa>.base]] embebido
01 Programas/<Programa>.base   # vista de sus proyectos
01 Programas/<Programa>.canvas # (opcional) mapa de dependencias
02 Projects/<Proyecto>.md      # nota de proyecto (la que ya genera el sync)
09 Vistas/Bloqueados.base      # bloqueadores primero, todo el portafolio
```

## Contrato de frontmatter por nivel

Es lo que el sync debe poblar. Sin esto, las Bases no tienen de dónde agregar.

### Proyecto (`02 Projects/<Proyecto>.md`)

```yaml
---
type: proyecto
source: asana
asana_gid:               # identidad permanente — nunca agrupar por nombre
asana_url:
programa: "[[Programa X]]"   # UP-LINK escrito por el sync (Portfolio, o "[[Programa General]]" si no hay)
programa_manual:             # respaldo humano OPCIONAL — SOLO aplica si Asana no tiene Portfolio; Asana manda si existe
owner:
status:                  # En curso | Bloqueado | No iniciado | Completado
start_date:              # YYYY-MM-DD
due_date:                # YYYY-MM-DD
tasks_total:             # nº de tareas en Asana
tasks_done:              # DERIVADO de notas reconciliadas (Completed: TRUE), no del flag
tasks_blocked:           # tareas cuyo Status: nota == Bloqueado
next_due:                # fecha de la próxima tarea abierta (YYYY-MM-DD)
critical_blocker:        # nombre de la tarea Bloqueada en ruta crítica, si hay
last_synced_at:
source_hash:
---
```

### Programa (`01 Programas/<Programa>.md`)

```yaml
---
type: programa
source: asana
asana_gid:
owner:
status:                  # En curso | Bloqueado | No iniciado | Completado
objetivo:                # una línea
---
```

El programa **no repite** conteos: su avance lo calcula el Base agregando sus
proyectos (`programa == this`). Menos que mantener, cero desincronización.

**De dónde sale `programa` (precedencia, la resuelve el sync):**
**Asana Portfolio** que contiene el proyecto > `programa_manual` (humano, respaldo
solo si Asana no lo agrupa) > `[[Programa General]]` (bucket genérico). Asana
manda: si existe el Portfolio, de ahí sale. Los Portfolios son tier Advanced: si
no está pagado, Asana responde 402/403 y todo cae al bucket genérico hasta que
lo ordenes con `programa_manual`. No hay capa Programa en los datos por defecto —
un proyecto llamado `Programa_X` sigue siendo un proyecto, no un contenedor.

> [!important] El sync ya reconcilia: `task_is_done()` cuenta una tarea como
> hecha si su nota dice `Completed: TRUE`, aunque el flag de Asana siga en
> false. Por eso `tasks_done` es correcto en el frontmatter sin correr nada
> antes. `mark_completed_from_notes.py` sigue sirviendo para arreglar el flag
> EN Asana (que el tablero y otros reportes vean lo mismo), pero las Bases ya
> no dependen de correrlo primero.

## Bases — la capa de agregación

**Sintaxis `.base` completa en el skill `obsidian`** (filtros, fórmulas, vistas,
funciones, reglas de comillas). Aquí solo el esquema PM. Recordatorio de los tres
fallos que aplican abajo: fórmulas con comillas simples envolviendo dobles;
restar fechas da **Duration** (acceder `.days` antes de redondear); guardar todo
opcional con `if()`.

### `00 Portafolio.base` — dashboard raíz

```yaml
filters:
  and:
    - 'type == "proyecto"'

formulas:
  pct: 'if(tasks_total, (tasks_done / tasks_total * 100).round(0), 0)'
  vencida: 'if(due_date, date(due_date) < today() && !(tasks_total && tasks_done == tasks_total), false)'
  dias_para_due: 'if(due_date, (date(due_date) - today()).days, "")'
  salud: 'if(tasks_blocked > 0, "🔴", if(tasks_total && tasks_done == tasks_total, "✅", if(tasks_total && tasks_done / tasks_total >= 0.5, "🟢", "🟡")))'

properties:
  formula.salud:
    displayName: ""
  formula.pct:
    displayName: "% avance"
  formula.dias_para_due:
    displayName: "Días a vencer"
  status:
    displayName: Estado

views:
  - type: table
    name: "Portafolio por programa"
    groupBy:
      property: programa
      direction: ASC
    order:
      - formula.salud
      - file.name
      - status
      - formula.pct
      - tasks_blocked
      - due_date
      - formula.dias_para_due
      - owner
    summaries:
      formula.pct: Average
      tasks_blocked: Sum

  - type: table
    name: "En riesgo"
    filters:
      or:
        - 'tasks_blocked > 0'
        - 'formula.vencida == true'
    order:
      - file.name
      - programa
      - status
      - formula.pct
      - due_date
```

### `01 Programas/<Programa>.base` — vista de un programa (embebible)

Se embebe en la nota del programa con `![[<Programa>.base]]`. Usa `this` para
autofiltrarse: al embeber, `this` es la nota que la embebe (el programa).

```yaml
filters:
  and:
    - 'type == "proyecto"'
    - 'programa == this.file.asLink()'

formulas:
  pct: 'if(tasks_total, (tasks_done / tasks_total * 100).round(0), 0)'

views:
  - type: table
    name: "Proyectos del programa"
    order:
      - file.name
      - status
      - formula.pct
      - tasks_blocked
      - due_date
      - owner
    summaries:
      formula.pct: Average
```

### `09 Vistas/Bloqueados.base` — bloqueadores primero

Materializa la regla de `pm-reporting.md`: reportar primero el bloqueador real,
no el conteo de vencidas.

```yaml
filters:
  and:
    - 'type == "proyecto"'
    - 'tasks_blocked > 0'

views:
  - type: table
    name: "Bloqueados en todo el portafolio"
    order:
      - file.name
      - programa
      - critical_blocker
      - due_date
      - owner
```

## Canvas por programa (opcional)

`json-canvas`: un `.canvas` por programa como mapa de dependencias / ruta
crítica. Nodos = proyectos (o tareas clave); aristas = el campo `Dependents:` de
las notas de tarea. Sirve para lo que `pm-reporting.md` pide: ver la ruta
crítica y detectar **órdenes de dependencia imposibles** (un dependiente con
`due` anterior al de su bloqueador).

- `.canvas` = `{"nodes": [], "edges": []}`. IDs hex de 16 chars, únicos.
- Nodo tipo `file` apuntando a la nota del proyecto (`"file": "02 Projects/X.md"`)
  para que el canvas quede navegable, o tipo `text` para hitos.
- Arista `fromNode`/`toNode` = borde de dependencia. Etiquetar con `label` la
  dependencia si aporta.
- **No auto-corregir fechas en el canvas.** Si detectas un orden imposible,
  márcalo como hallazgo y pregunta cuál lado está mal (schedule vs edge) — igual
  que en `asana-obsidian-llm-wiki`.

Generarlo desde el `Dependents:` de las notas es scripting one-off; mantener el
canvas es manual salvo que valga automatizarlo. Empezar solo en el programa con
más dependencias cruzadas.

## Integración marker-safe con el sync existente

No romper la disciplina de `asana-obsidian-llm-wiki`:

- **El sync puebla el frontmatter** (`tasks_total`, `tasks_done` reconciliado,
  `tasks_blocked`, `next_due`, `programa`). Las Bases solo LEEN ese frontmatter.
- **Bases y up-link viven FUERA** del bloque `<!-- HERMES:START -->…END`. El
  bloque HERMES sigue siendo lo único que el sync reescribe.
- `## Notas humanas` **intacto byte a byte**.
- El script de sync sigue **GET-only** contra Asana.
- Identidad por `asana_gid` en el frontmatter; el nombre del archivo/H1 puede
  cambiar sin crear duplicados.
- `tasks_done` lo reconcilia el **propio sync** (`task_is_done` lee
  `Completed: TRUE` de la nota), así que las Bases no mienten aunque el flag de
  Asana esté desactualizado. El sync también escribe `programa`, `tasks_blocked`,
  `next_due` y `critical_blocker`, y mete el estado reconciliado en el
  `source_hash` (editar una nota a `Completed: TRUE` dispara re-render).

## Pitfalls (kepano + este caso)

- **YAML quoting en fórmulas:** comillas simples envolviendo las dobles internas
  — `'if(done, "Sí", "No")'`. displayName con `:` va entre comillas dobles.
- **Duration ≠ número:** `(date(due_date) - today()).days` (acceder `.days`
  antes de `.round()`). Nunca dividir por `86400000`.
- **Guardar los opcionales:** `if(due_date, …, "")`. El portafolio tiene fechas
  faltantes; sin guarda la Base falla en silencio.
- **`formula.X` en `order`/`properties` exige definir `X` en `formulas`.** Si
  no, no renderiza y no avisa.
- **Agrupar por `programa` (up-link), no por texto.** El nombre del programa
  cambia; el WikiLink no. En el proyecto: `programa: "[[Programa X]]"`.
- **No agrupar por `asana_gid` en la vista** — es identidad, no dimensión legible.
  Agrupar por `programa`, mostrar `file.name`.
- **No materializar tareas como notas.** Duplica estado operativo y rompe el
  reparto de verdad. Tareas = Asana; Obsidian agrega por conteo.
- **`obsidian-cli` requiere Obsidian abierto** — no usarlo en el sync headless.

## Instalar en un agente PM de Hermes

El skill es un directorio con `SKILL.md` (más `references/` si crece). Va en el
directorio de skills del perfil:

```bash
export PATH="$HOME/.hermes/hermes-agent/venv/bin:$PATH"   # el binario NO está en PATH
cp -R obsidian-pm-context $HOME/.hermes/skills/           # ruta ABSOLUTA (en sesión $HOME es el perfil)
hermes skills list | grep obsidian-pm-context
```

Crear/replicar el perfil PM: ver "Replicating this for a new agent" en
`asana-obsidian-llm-wiki` (bot Telegram único por perfil, `check_telegram_conflicts.py`,
`launchctl list | grep hermes` para confirmar PID real). No repetir aquí.

Orden de carga de skills en el agente PM: `obsidian` (formatos, fundación) +
`asana-obsidian-llm-wiki` (sync) + `obsidian-pm-context`
(estructura PM). `obsidian-pm-context` no funciona bien sin `obsidian` cargado.

## Verificación

```bash
# 1. Frontmatter poblado por el sync (tasks_done ya reconciliado desde notas)
python3 asana_obsidian_sync.py --query <PROJECT_GID>   # ver qué escribió; o --dry-run

# 2. Base valida como YAML
python3 -c "import yaml,sys; yaml.safe_load(open('00 Portafolio.base')); print('YAML ok')"

# 3. Abrir el .base en Obsidian: la tabla agrupa por programa y suma % — si da
#    error YAML, revisar comillas de fórmulas. Si una columna sale vacía,
#    falta la guarda if() o el frontmatter no trae ese campo.

# 4. Marcadores intactos tras poblar frontmatter
grep -rc "HERMES:START" "02 Projects" | grep -v ":1"   # sin salida = todas con 1
```
