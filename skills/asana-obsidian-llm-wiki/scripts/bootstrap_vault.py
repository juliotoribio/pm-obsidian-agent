#!/usr/bin/env python3
"""
Bootstrap Obsidian Vault for Hermes PM Agent.

Creates the foundational folder structure and standard rollup notes (00 Portafolio.base,
01 Programas/X.md, 09 Vistas/Bloqueados.base).

Usage:
  python bootstrap_vault.py <VAULT_PATH> [--apply]
"""

import argparse
import os
import sys

FOLDERS = [
    "01 Programas",
    "02 Projects",
    "03 People",
    "04 Log",
    "05 Knowledge",
    "09 Vistas",
]

PORTFOLIO_BASE = """---
type: index
---
# 00 Portafolio

Este es el punto de entrada principal para el portafolio completo.
Hermes agrupa los proyectos aquí automáticamente.

![[LLM Wiki Index]]
"""

BLOQUEADOS_BASE = """---
type: query
---
# Proyectos Bloqueados

Listado de proyectos que presentan la palabra "bloqueo" o similar en sus tareas.

```dataview
TABLE status as Estado, critical_blocker as Bloqueo
FROM "02 Projects"
WHERE tasks_blocked > 0
```
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", help="Path to the Obsidian vault")
    parser.add_argument("--apply", action="store_true", help="Actually write the files")
    args = parser.parse_args()

    vault = args.vault
    if not os.path.isdir(vault):
        sys.exit(f"ERROR: {vault} no es un directorio válido.")

    print(f"Bootstrapping vault en: {vault}")
    
    for folder in FOLDERS:
        path = os.path.join(vault, folder)
        if not os.path.exists(path):
            print(f"  + Crear carpeta: {folder}")
            if args.apply:
                os.makedirs(path, exist_ok=True)
        else:
            print(f"  = Carpeta existente: {folder}")

    def write_file(rel_path, content):
        path = os.path.join(vault, rel_path)
        if not os.path.exists(path):
            print(f"  + Crear archivo: {rel_path}")
            if args.apply:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
        else:
            print(f"  = Archivo existente: {rel_path}")

    write_file("00 Portafolio.base.md", PORTFOLIO_BASE)
    
    # Asegurar que 09 Vistas existe antes de escribir
    if args.apply:
        os.makedirs(os.path.join(vault, "09 Vistas"), exist_ok=True)
    write_file("09 Vistas/Bloqueados.base.md", BLOQUEADOS_BASE)

    if not args.apply:
        print("\n[DRY-RUN] No se escribió nada. Usa --apply para ejecutar.")
    else:
        print("\n¡Bootstrap completado!")

if __name__ == "__main__":
    main()
