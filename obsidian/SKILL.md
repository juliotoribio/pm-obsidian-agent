---
name: obsidian
description: "Obsidian open-format authoring: Obsidian Flavored Markdown (.md — wikilinks, embeds, callouts, properties, tags), Bases (.base — filtered/grouped/computed views with formulas), and JSON Canvas (.canvas — visual node/edge maps). Use when writing or editing any Obsidian file, building a .base dashboard, authoring a .canvas, or when the user mentions wikilinks, callouts, frontmatter, properties, .base, formulas, or .canvas. Foundation layer: obsidian-pm-context builds the PM portfolio schema ON TOP of this — this skill owns FORMAT syntax, not PM structure."
version: 1.0.0
platforms: [macos, linux]
author: consolidado y recortado de kepano/obsidian-skills (obsidian-markdown + obsidian-bases + json-canvas)
tags: [obsidian, markdown, bases, canvas, format]
---

# Obsidian — formatos abiertos

Fundación para escribir archivos Obsidian bien formados. Cubre los **tres
formatos** que un agente usa de verdad y **cuándo usar cada uno**. No cubre
esquema PM ni rollups de portafolio — eso lo construye `obsidian-pm-context`
encima de este skill. Consolidado y recortado de `kepano/obsidian-skills`
(se dejaron fuera `defuddle` y `knap`, no relevantes aquí).

## Los tres formatos — cuándo usar cada uno

| Formato | Extensión | Para | Regla |
|---|---|---|---|
| **Flavored Markdown** | `.md` | El cuerpo de una nota: contexto, decisiones, enlaces | Conocimiento durable, prosa + WikiLinks |
| **Bases** | `.base` | Vista viva sobre MUCHAS notas: tabla/tarjetas filtrada, agrupada, con fórmulas | Agregación. NO copiar datos — leer frontmatter |
| **JSON Canvas** | `.canvas` | Mapa visual: dependencias, flujo, mapa mental | Relaciones espaciales, no listas |

Una Base **no almacena** datos: consulta el frontmatter de las notas. Si quieres
que algo aparezca en una Base, ponlo como *property* en las notas, no en la Base.

## Fallos que rompen el archivo (leer primero)

- **Comillas en fórmulas `.base`:** comillas simples envolviendo las dobles
  internas — `'if(done, "Sí", "No")'`. Dobles dentro de dobles = error YAML.
- **`displayName` con `:` `{` `[` `,` `#` `|` `-` `>` `=` `!` `%` `@`** va entre
  comillas dobles: `displayName: "Estado: activo"`.
- **Restar fechas da Duration, no número.** Acceder `.days`/`.hours` ANTES de
  redondear: `(date(due) - today()).days.round(0)`. Nunca dividir por `86400000`.
- **Property opcional en fórmula → guardar con `if()`:** `if(due, (date(due) - today()).days, "")`. Sin guarda, la Base falla en silencio.
- **`formula.X` en `order`/`properties` exige `X` definido en `formulas`.**
- **Canvas: `\n` para saltos de línea** en strings JSON (no `\\n`, que Obsidian
  muestra literal). IDs hex de 16 chars, únicos entre nodos Y aristas; toda
  `fromNode`/`toNode` debe referenciar un nodo existente.

---

## 1. Obsidian Flavored Markdown (`.md`)

Extiende CommonMark/GFM. Solo lo específico de Obsidian (el Markdown estándar se
asume).

### WikiLinks (enlaces internos)

```markdown
[[Nota]]                       Enlace a nota
[[Nota|Texto visible]]         Texto personalizado
[[Nota#Encabezado]]            A un encabezado
[[Nota#^block-id]]             A un bloque
[[#Encabezado]]                Encabezado de la misma nota
```

Definir un block ID: sufijo `^block-id` al final de un párrafo; para listas y
citas, en línea aparte tras el bloque. **Usar `[[wikilinks]]` para notas del
vault** (Obsidian rastrea renombres) y `[texto](url)` solo para URLs externas.

### Embeds

```markdown
![[Nota]]                      Embeber nota completa
![[Nota#Encabezado]]           Embeber sección
![[imagen.png|300]]            Imagen con ancho
![[doc.pdf#page=3]]            Página de PDF
![[MiBase.base]]               Embeber una Base
![[MiBase.base#Nombre Vista]]  Una vista específica de la Base
```

### Callouts

```markdown
> [!note]
> Callout básico.

> [!warning] Título propio
> Con título personalizado.

> [!faq]- Colapsado por defecto
> Plegable (- colapsado, + expandido).
```

Tipos: `note`, `tip`, `warning`, `info`, `example`, `quote`, `bug`, `danger`,
`success`, `failure`, `question`, `abstract`, `todo`. Se anidan agregando `>`.

### Properties (frontmatter)

```yaml
---
title: Mi Nota
date: 2026-01-15
tags:
  - proyecto
  - activo
aliases:
  - Nombre alternativo
cssclasses:
  - clase-css
---
```

Por defecto: `tags` (etiquetas buscables), `aliases` (nombres alternos para
sugerencia de enlaces), `cssclasses` (estilo). Tipos de property y reglas de
tags: `references/MARKDOWN_REFERENCE.md`.

### Tags, comentarios, resaltado

```markdown
#tag            #anidado/tag           Etiquetas (letras, números no al inicio, _ - /)
%%oculto%%      %% bloque oculto %%    Comentarios (no se renderizan)
==resaltado==                          Highlight
```

---

## 2. Bases (`.base`)

YAML válido con secciones `filters` / `formulas` / `properties` / `summaries` /
`views`.

### Workflow

1. Crear el `.base` con YAML válido.
2. `filters` — qué notas entran (por tag, carpeta, property o fecha).
3. `formulas` (opcional) — properties calculadas.
4. `views` — una o más (`table`, `cards`, `list`, `map`) con `order` = qué
   properties mostrar.
5. Validar YAML; abrir en Obsidian para confirmar render.

### Esquema

```yaml
filters:                       # global a todas las vistas
  and:                         # objeto recursivo: una sola clave and | or | not
    - 'status == "active"'
    - not:
        - 'file.hasTag("archived")'

formulas:
  nombre: 'expresión'

properties:
  nombre_prop:
    displayName: "Nombre visible"
  formula.nombre:
    displayName: "…"

views:
  - type: table | cards | list | map
    name: "Nombre"
    limit: 10                  # opcional
    groupBy:
      property: nombre_prop
      direction: ASC | DESC
    filters:                   # específicos de la vista, mismas reglas
      and:
        - 'status == "active"'
    order:                     # properties a mostrar, en orden
      - file.name
      - nombre_prop
      - formula.nombre
    summaries:
      nombre_prop: Average
```

### Filtros

Operadores: `==` `!=` `>` `<` `>=` `<=` `&&` `||` `!`. Estructura `and` / `or` /
`not` (anidables). Ejemplos:

```yaml
filters: 'status == "done"'
filters:
  or:
    - file.hasTag("book")
    - and:
        - file.hasTag("article")
        - file.hasLink("Textbook")
```

### Properties: tres tipos

1. **De nota** (frontmatter): `author` o `note.author`.
2. **De archivo**: `file.name`, `file.basename`, `file.path`, `file.folder`,
   `file.ext`, `file.ctime`, `file.mtime`, `file.tags`, `file.links`,
   `file.backlinks`, `file.size`.
3. **Fórmula**: `formula.mi_formula`.

`this` = el propio `.base` en el área principal; **la nota que lo embebe** cuando
está embebido. `this.file.asLink()` es clave para vistas auto-filtradas.

### Fórmulas (esenciales)

```yaml
formulas:
  total: "price * quantity"
  icono: 'if(done, "✅", "⏳")'
  creado: 'file.ctime.format("YYYY-MM-DD")'
  dias_desde: '(now() - file.ctime).days'
  dias_a_due: 'if(due, (date(due) - today()).days, "")'
```

Funciones globales clave: `date()`, `now()`, `today()`, `if()`, `link()`,
`file()`, `min()`, `max()`, `number()`. **Referencia completa de funciones**
(String, Number, List, Date, Duration, File, Link, Object, RegExp):
`references/BASES_FUNCTIONS.md`.

### Summaries por defecto

`Average`, `Min`, `Max`, `Sum`, `Range`, `Median`, `Stddev`, `Earliest`,
`Latest`, `Checked`, `Unchecked`, `Empty`, `Filled`, `Unique`. Custom en la
sección `summaries:` con expresiones sobre `values`.

### Vistas

`table` (con `summaries`), `cards` (galería, primer campo suele ser imagen de
portada), `list`, `map` (requiere lat/lng + plugin Maps).

### Quoting y troubleshooting

- Fórmula con dobles → envolver en simples. displayName con caracteres especiales
  → dobles.
- Duration sin acceder `.days` → error. Property opcional sin `if()` → falla
  silenciosa. `formula.X` sin definir → no renderiza sin avisar.

---

## 3. JSON Canvas (`.canvas`)

`{"nodes": [], "edges": []}` según JSON Canvas Spec 1.0. Orden del array de nodos
= z-index (primero = fondo).

### Nodos

Atributos genéricos: `id` (hex 16, único), `type` (`text`|`file`|`link`|`group`),
`x`, `y`, `width`, `height`, `color` (opcional: preset `"1"`-`"6"` o hex).

```json
{ "id": "6f0ad84f44ce9c17", "type": "text", "x": 0, "y": 0,
  "width": 400, "height": 200, "text": "# Título\n\nContenido **Markdown**." }
```

- **text**: `text` (Markdown; `\n` para saltos).
- **file**: `file` (ruta en el vault), `subpath` opcional (`#encabezado`). Úsalo
  para que un nodo apunte a una nota y quede navegable.
- **link**: `url` (externa).
- **group**: contenedor visual; `label`, `background`, `backgroundStyle`.

### Aristas

`id`, `fromNode`, `toNode` (obligatorios); `fromSide`/`toSide`
(`top`/`right`/`bottom`/`left`), `fromEnd`/`toEnd` (`none`/`arrow`, default
`toEnd: arrow`), `color`, `label`.

```json
{ "id": "0123456789abcdef", "fromNode": "6f0ad84f44ce9c17",
  "fromSide": "right", "toNode": "a1b2c3d4e5f67890", "toSide": "left",
  "toEnd": "arrow", "label": "depende de" }
```

### Colores, layout, validación

- Presets `"1"` rojo · `"2"` naranja · `"3"` amarillo · `"4"` verde · `"5"` cian
  · `"6"` morado (o hex).
- Coordenadas pueden ser negativas; `x`→derecha, `y`→abajo; posición = esquina
  superior izquierda. Espaciar 50–100px; alinear a múltiplos de 10/20.
- **Validar:** IDs únicos (nodos+aristas), toda arista referencia nodos
  existentes, campos requeridos por tipo, JSON parseable, sin `\n` sin escapar.

Ejemplos completos (mapas mentales, tableros, flujos): `references/CANVAS_EXAMPLES.md`.

---

## 4. Obsidian CLI (solo interactivo)

`obsidian <cmd>` interactúa con una instancia **abierta** de Obsidian (no sirve
para pipelines headless). Útil para consulta/apertura rápida cuando el vault está
abierto: `obsidian search query="…"`, `obsidian open file="Nota"`,
`obsidian create name="Nota" content="…"`. Parámetros con `=`, valores con
espacios entre comillas; `vault=<n>` como primer parámetro para elegir vault.
`obsidian help` lista todo. Docs: https://help.obsidian.md/cli

## Verificación

```bash
python3 -c "import yaml; yaml.safe_load(open('X.base')); print('base YAML ok')"
python3 -c "import json; json.load(open('X.canvas')); print('canvas JSON ok')"
# Markers HERMES intactos si editaste una nota generada por sync:
grep -c "HERMES:START" nota.md    # debe ser 1
```
