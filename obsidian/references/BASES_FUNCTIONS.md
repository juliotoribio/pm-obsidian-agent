# Bases — referencia de funciones

Se carga solo cuando una fórmula lo necesita. Reglas de comillas y guardas: ver
`SKILL.md`.

## Globales

| Función | Firma | Nota |
|---|---|---|
| `date()` | `date(string): date` | Parsear (`YYYY-MM-DD HH:mm:ss`) |
| `duration()` | `duration(string): duration` | Parsear duración |
| `now()` / `today()` | `: date` | Ahora / hoy (00:00:00) |
| `if()` | `if(cond, siVerdad, siFalso?)` | Condicional |
| `min()` / `max()` | `(n1, n2, …): number` | Menor / mayor |
| `number()` | `number(any): number` | A número |
| `link()` | `link(path, display?): Link` | Crear enlace |
| `list()` | `list(el): List` | Envolver en lista |
| `file()` | `file(path): file` | Objeto archivo |
| `icon()` / `image()` / `html()` | — | Render de icono Lucide / imagen / HTML |

## Fechas y Duration

Campos de fecha: `.year .month .day .hour .minute .second .millisecond`.
`date.format("patrón")` (Moment.js), `date.relative()`, `date.date()` (quita hora).

**Restar fechas → Duration.** Campos: `.days .hours .minutes .seconds
.milliseconds`. Duration NO soporta `.round()/.floor()/.ceil()` directo — acceder
un campo numérico primero.

```yaml
"(date(due) - today()).days"            # número de días
"(now() - file.ctime).days.round(0)"    # redondeado
"today() + \"7d\""                       # aritmética: y/M/d/w/h/m/s
# MAL: "((date(due) - today()) / 86400000).round(0)"
```

## String

Campo `.length`. `contains() containsAll() containsAny() startsWith()
endsWith() isEmpty() lower() title() trim() replace(pat, rep) repeat() reverse()
slice(ini, fin?) split(sep, n?)`.

## Number

`abs() ceil() floor() round(digitos?) toFixed(prec) isEmpty()`.

## List

Campo `.length`. `contains() containsAll() containsAny() filter(expr) map(expr)
reduce(expr, ini) flat() join(sep) reverse() slice() sort() unique() isEmpty()`.
En `filter/map/reduce` se usan `value`, `index`, `acc`.

## File

`asLink(display?) hasLink(otro) hasTag(...tags) hasProperty(nombre)
inFolder(carpeta)`. `inFolder` incluye subcarpetas; `hasTag` es OR de las tags.

## Link / Object / RegExp

- Link: `asFile()`, `linksTo(file)`.
- Object: `isEmpty() keys() values()`.
- RegExp: `regexp.matches(string): boolean` — ej. `/^\d{4}-\d{2}-\d{2}$/.matches(file.basename)`.

## Any

`isTruthy() isType(tipo) toString()`.
