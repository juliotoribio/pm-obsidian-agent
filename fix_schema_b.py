import re
with open("skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py", "r") as f:
    text = f.read()

old_resolve = """def resolve_programa(existing_fm, program_map, gid, ws_name=None):
    \"\"\"Precedencia: Portfolio de Asana > override humano (programa_manual) > workspace > genérico.

    Asana manda: si el proyecto vive en un Portfolio, ese es su programa. El
    `programa_manual` es el respaldo SOLO cuando Asana no agrupa el proyecto
    (sin Portfolios en el tier, o el proyecto no está en ninguno). El sync nunca
    pisa `programa_manual`, pero un Portfolio existente tiene prioridad sobre él.
    \"\"\"
    name = program_map.get(gid)
    if name:
        return f"[[{name} ({ws_name})|{name}]]" if ws_name else _wikilink(name)
    
    manual = (existing_fm or {}).get("programa_manual")
    if manual:
        clean = manual[2:-2] if manual.startswith("[[") and manual.endswith("]]") else manual
        if "|" in clean:
            clean = clean.split("|")[1].strip()
        if ws_name and not clean.endswith(f"({ws_name})"):
            return f"[[{clean} ({ws_name})|{clean}]]"
        return _wikilink(manual)
        
    if ws_name:
        # Si no hay nombre de portfolio, el programa genérico del workspace puede ser solo el workspace name
        return f"[[{ws_name} ({ws_name})|{ws_name}]]"
        
    return "[[%s]]" % GENERIC_PROGRAM"""

new_resolve = """def resolve_programa(existing_fm, program_map, gid, ws_name=None):
    \"\"\"Precedencia: Portfolio de Asana > override humano (programa_manual) > workspace > genérico.\"\"\"
    name = program_map.get(gid)
    if name:
        return _wikilink(name)
    manual = (existing_fm or {}).get("programa_manual")
    if manual:
        return _wikilink(manual)
    if ws_name:
        return _wikilink(ws_name)
    return "[[%s]]" % GENERIC_PROGRAM"""

text = text.replace(old_resolve, new_resolve)

# In plan_sync, programs_seen.add((ws_name, programa))
# Search for `programs_seen.add(programa)`
text = text.replace("programs_seen.add(programa)", "programs_seen.add((ws_name, programa))")

old_apply_prog = """    for prog in meta.get("programs", []):
        path_name = prog
        display_name = prog
        if prog.startswith("[[") and prog.endswith("]]"):
            inner = prog[2:-2]
            if "|" in inner:
                path_name, display_name = inner.split("|", 1)
            else:
                path_name = inner
                display_name = inner
        
        md_path = os.path.join(prog_dir, f"{path_name}.md")
        if not os.path.exists(md_path):
            atomic_write(md_path, f"---\\ntype: programa\\n---\\n# {display_name}\\n\\n![[{path_name}.base]]\\n")
            
        base_path = os.path.join(prog_dir, f"{path_name}.base")
        if not os.path.exists(base_path):
            base_content = 'filters:\\n  and:\\n    - \\'type == "proyecto"\\'\\n    - \\'programa == this.file.asLink()\\'\\n\\nformulas:\\n  pct: \\'if(tasks_total, (tasks_done / tasks_total * 100).round(0), 0)\\'\\n\\nviews:\\n  - type: table\\n    name: "Proyectos del programa"\\n    order:\\n      - file.name\\n      - status\\n      - formula.pct\\n      - tasks_blocked\\n      - due_date\\n      - owner\\n    summaries:\\n      formula.pct: Average\\n'
            atomic_write(base_path, base_content)"""

new_apply_prog = """    for ws_name, prog in meta.get("programs", []):
        if prog.startswith("[[") and prog.endswith("]]"):
            name = prog[2:-2]
        else:
            name = prog
            
        file_name = f"{name} ({ws_name})" if ws_name else name
        
        md_path = os.path.join(prog_dir, f"{file_name}.md")
        if not os.path.exists(md_path):
            atomic_write(md_path, f"---\\ntype: programa\\n---\\n# {name}\\n\\n![[{file_name}.base]]\\n")
            
        base_path = os.path.join(prog_dir, f"{file_name}.base")
        if not os.path.exists(base_path):
            base_content = f\"\"\"filters:
  and:
    - 'type == "proyecto"'
    - 'workspace == "{ws_name}"'
    - 'programa == "{prog}"'

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
\"\"\"
            atomic_write(base_path, base_content)"""

text = text.replace(old_apply_prog, new_apply_prog)

with open("skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py", "w") as f:
    f.write(text)
