#!/usr/bin/env python3
"""
Bootstrap Obsidian Vault for Hermes PM Agent.

Creates the foundational folder structure and standard rollup notes (00 Portafolio.base,
01 Programas/Programa General.base, 09 Vistas/Bloqueados.base).

Usage:
  python bootstrap_vault.py <VAULT_PATH> [--apply]
"""

import argparse
import os
import sys

FOLDERS = [
    "01 Programas",
    "02 Projects",
    "03 Log",
    "04 Decisions",
    "05 Knowledge",
    "07 Agents",
    "09 Vistas",
    "99 System/Templates"
]

PORTFOLIO_BASE = """filters:
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
"""

BLOQUEADOS_BASE = """filters:
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
"""

PROGRAMA_BASE = """filters:
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
"""

PROGRAMA_MD = """---
type: programa
---
# Programa General

Agrupador genérico para proyectos sin portafolio.

![[Programa General.base]]
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

    write_file("00 Portafolio.base", PORTFOLIO_BASE)
    
    if args.apply:
        os.makedirs(os.path.join(vault, "09 Vistas"), exist_ok=True)
    write_file("09 Vistas/Bloqueados.base", BLOQUEADOS_BASE)

    if args.apply:
        os.makedirs(os.path.join(vault, "01 Programas"), exist_ok=True)
    write_file("01 Programas/Programa General.base", PROGRAMA_BASE)
    write_file("01 Programas/Programa General.md", PROGRAMA_MD)

    if not args.apply:
        print("\n[DRY-RUN] No se escribió nada. Usa --apply para ejecutar.")
    else:
        print("\n¡Bootstrap completado!")

if __name__ == "__main__":
    main()
