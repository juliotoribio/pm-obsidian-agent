# JSON Canvas — ejemplos

Compactos y orientados a PM. Esquema y reglas: `SKILL.md`.

## Mapa de dependencias de un programa

Nodos `file` que apuntan a las notas de proyecto (quedan navegables); aristas =
el campo `Dependents:` de las notas de tarea. Color por estado.

```json
{
  "nodes": [
    { "id": "a1000000000000a1", "type": "group", "x": -60, "y": -60,
      "width": 1120, "height": 420, "label": "Programa Zero Trust", "color": "6" },
    { "id": "b1000000000000b1", "type": "file", "x": 0, "y": 0,
      "width": 300, "height": 120, "file": "02 Projects/Landing Zone.md", "color": "4" },
    { "id": "b2000000000000b2", "type": "file", "x": 400, "y": 0,
      "width": 300, "height": 120, "file": "02 Projects/Segmentacion.md", "color": "3" },
    { "id": "b3000000000000b3", "type": "file", "x": 800, "y": 0,
      "width": 300, "height": 120, "file": "02 Projects/Identidad.md", "color": "1" }
  ],
  "edges": [
    { "id": "e1000000000000e1", "fromNode": "b1000000000000b1", "fromSide": "right",
      "toNode": "b2000000000000b2", "toSide": "left", "toEnd": "arrow", "label": "habilita" },
    { "id": "e2000000000000e2", "fromNode": "b2000000000000b2", "fromSide": "right",
      "toNode": "b3000000000000b3", "toSide": "left", "toEnd": "arrow", "label": "bloquea" }
  ]
}
```

Rojo (`"1"`) marca el proyecto bloqueado en ruta crítica → mirar primero. Si una
arista apunta a un nodo con `due` anterior al de su origen, es un **orden de
dependencia imposible**: marcarlo como hallazgo, no auto-corregir fechas.

## Tablero simple (hitos por texto)

```json
{
  "nodes": [
    { "id": "c1000000000000c1", "type": "text", "x": 0, "y": 0,
      "width": 260, "height": 100, "text": "## Kickoff\nAprobado 05/04", "color": "4" },
    { "id": "c2000000000000c2", "type": "text", "x": 360, "y": 0,
      "width": 260, "height": 100, "text": "## Diseño\nEn curso 60%", "color": "3" }
  ],
  "edges": [
    { "id": "e3000000000000e3", "fromNode": "c1000000000000c1",
      "toNode": "c2000000000000c2", "toEnd": "arrow" }
  ]
}
```

IDs: hex 16, únicos entre nodos y aristas. `\n` (simple) para saltos de línea.
