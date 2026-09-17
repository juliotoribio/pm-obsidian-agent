# Obsidian Flavored Markdown — detalle

## Tipos de property (frontmatter)

Obsidian infiere el tipo por el valor; el tipo se fija en Settings → Properties.

| Tipo | Ejemplo YAML |
|---|---|
| Text | `estado: activo` |
| Number | `prioridad: 2` |
| Checkbox | `hecho: true` |
| Date | `fecha: 2026-01-15` |
| Date & time | `visto: 2026-01-15T09:30:00` |
| List | `tags:` con guiones debajo |
| Link (WikiLink en property) | `programa: "[[Programa X]]"` (entre comillas) |

- Un WikiLink dentro de una property **va entre comillas**: `"[[Nota]]"`. Sin
  comillas, YAML lo interpreta como lista anidada.
- Listas de enlaces: cada ítem `- "[[Nota]]"`.

## Reglas de tags

- Caracteres válidos: letras, números (no como primer carácter), `_`, `-`, `/`.
- Anidados con `/`: `#area/ti/ciberseguridad`.
- En frontmatter bajo `tags:` (sin `#`) o inline en el cuerpo (con `#`).

## Callouts — lista completa

`note` · `abstract`/`summary`/`tldr` · `info` · `todo` · `tip`/`hint`/`important`
· `success`/`check`/`done` · `question`/`help`/`faq` · `warning`/`caution`/`attention`
· `failure`/`fail`/`missing` · `danger`/`error` · `bug` · `example` · `quote`/`cite`.

- Título propio: `> [!warning] Texto del título`.
- Plegable: `> [!faq]-` (colapsado) / `> [!faq]+` (expandido).
- Anidar: agregar `>` extra por nivel.

## Embeds — variantes

```markdown
![[Nota]]                 nota completa
![[Nota#Encabezado]]      sección
![[Nota#^block-id]]       bloque
![[imagen.png|300]]       imagen con ancho
![[imagen.png|100x80]]    imagen ancho x alto
![[audio.mp3]]            audio
![[video.mp4]]            video
![[doc.pdf#page=3]]       página de PDF
![[MiBase.base#Vista]]    vista de una Base
```

Imagen externa: `![alt|ancho](https://…)`.
