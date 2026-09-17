import os
import re

path = "skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Rate Limiting in asana_get
asana_get_old = """    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:"""
asana_get_new = """    import time
    while True:
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
"""
text = text.replace(asana_get_old, asana_get_new)

# 2. Pagination in fetch_projects
fetch_projects_old = """def fetch_projects(token, workspace_gid, limit=5):
    return asana_get(
        token,
        "/workspaces/%s/projects" % workspace_gid,
        {
            "opt_fields": "name,notes,color,archived,due_on,start_on,"
                          "created_at,modified_at,owner.name,current_status,"
                          "current_status.title,public,permalink_url",
            "limit": limit,
        },
    ).get("data", [])"""
fetch_projects_new = """def fetch_projects(token, workspace_gid, limit=5):
    out = []
    params = {
        "opt_fields": "name,notes,color,archived,due_on,start_on,"
                      "created_at,modified_at,owner.name,current_status,"
                      "current_status.title,public,permalink_url",
        "limit": 100,
    }
    path = "/workspaces/%s/projects" % workspace_gid
    while True:
        page = asana_get(token, path, params)
        out.extend(page.get("data", []))
        if limit and len(out) >= limit:
            out = out[:limit]
            break
        nxt = (page.get("next_page") or {}).get("offset")
        if not nxt:
            break
        params["offset"] = nxt
    return out"""
text = text.replace(fetch_projects_old, fetch_projects_new)

# 3. Dependencies in fetch_project_tasks
fpt_old = """        "opt_fields": "name,completed,completed_at,due_on,start_on,"
                      "assignee.name,memberships.section.name,notes,permalink_url","""
fpt_new = """        "opt_fields": "name,completed,completed_at,due_on,start_on,"
                      "assignee.name,memberships.section.name,notes,permalink_url,dependencies,dependents","""
text = text.replace(fpt_old, fpt_new)

# 4. Better parse_frontmatter
parse_fm_old = """def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\\n")
    body = text[end + 4:]
    fm = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body"""
parse_fm_new = """def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\\n")
    body = text[end + 4:]
    fm = {}
    lines = raw.splitlines()
    current_key = None
    current_val = []
    
    def save_current():
        if current_key:
            val = "\\n".join(current_val).strip()
            if val.startswith('"') and val.endswith('"'): val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"): val = val[1:-1]
            fm[current_key] = val

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            save_current()
            k, sep, v = line.partition(":")
            current_key = k.strip()
            current_val = [v.strip()] if v.strip() else []
        else:
            if current_key:
                current_val.append(line)
    save_current()
    return fm, body"""
text = text.replace(parse_fm_old, parse_fm_new)

# 5. Local time for `today`
utc_time = "datetime.now(timezone.utc).date().isoformat()"
local_time = "datetime.now().astimezone().date().isoformat()"
text = text.replace(utc_time, local_time)
text = text.replace("datetime.now(timezone.utc).replace(microsecond=0)", "datetime.now().astimezone().replace(microsecond=0)")

# 6. Preserve all existing frontmatter
plan_sync_old = """        if cur_fm.get("programa_manual"):
            fm["programa_manual"] = cur_fm["programa_manual"]"""
plan_sync_new = """        for k, v in cur_fm.items():
            if k not in fm and not k.startswith("_"):
                fm[k] = v"""
text = text.replace(plan_sync_old, plan_sync_new)

# 7. write_index uses task_is_done and is marker-safe
write_index_old = """def write_index(vault, plan, meta):
    \"\"\"Fase 6: LLM Wiki Index.\"\"\"
    now = meta["synced_at"]"""
write_index_new = """def write_index(vault, plan, meta):
    \"\"\"Fase 6: LLM Wiki Index.\"\"\"
    path = os.path.join(vault, "LLM Wiki Index.md")
    
    # Preserve human notes outside HERMES block
    human_notes = "## Notas humanas\\n\\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            m = re.search(r"^##\s+Notas humanas\s*$", content, flags=re.MULTILINE)
            if m:
                human_notes = content[m.start():].rstrip() + "\\n"
    
    now = meta["synced_at"]"""
text = text.replace(write_index_old, write_index_new)

index_start_old = """        "---",
        "",
        "# LLM Wiki Index",
        "",
        "Punto de entrada para Hermes. No es una copia completa de las notas:",
        "es el mapa. Última sincronización: **%s**." % now,
        "","""
index_start_new = """        "---",
        "",
        "# LLM Wiki Index",
        "",
        "Punto de entrada para Hermes. No es una copia completa de las notas:",
        "es el mapa. Última sincronización: **%s**." % now,
        "",
        START,
        "","""
text = text.replace(index_start_old, index_start_new)

index_bug_old = """        od = [t for t in tasks
              if not t.get("completed") and t.get("due_on") and t["due_on"] < today]"""
index_bug_new = """        od = [t for t in tasks
              if not task_is_done(t) and t.get("due_on") and t["due_on"] < today]"""
text = text.replace(index_bug_old, index_bug_new)

index_end_old = """        "## Agentes registrados",
        "",
        "- [[Maha PM]]",
        "",
        "## Sistema",
        "",
        "- [[Hermes Knowledge Protocol]]",
        "",
    ]
    path = os.path.join(vault, "LLM Wiki Index.md")
    atomic_write(path, "\\n".join(lines))"""
index_end_new = """    ]
    lines.extend([
        "",
        END,
        "",
        human_notes
    ])
    atomic_write(path, "\\n".join(lines))"""
text = text.replace(index_end_old, index_end_new)


# 8. record_deletion appends OUTSIDE HERMES block (Notas humanas)
record_del_old = """    head, _, tail = text.partition(END)
    # insert right after the "## Cambios recientes" heading if present,
    # otherwise immediately before the END marker
    m = re.search(r"(^##\s+Cambios recientes\s*$)", head, flags=re.MULTILINE)
    if m:
        idx = m.end()
        new_head = head[:idx] + "\\n\\n" + line + head[idx:]
    else:
        new_head = head.rstrip() + "\\n\\n" + line + "\\n\\n"

    new_text = new_head + tail"""

record_del_new = """    # Escribir en Notas Humanas para no invalidar el source_hash ni ser sobreescrito
    m = re.search(r"(^##\s+Notas humanas\s*$)", text, flags=re.MULTILINE)
    if m:
        idx = m.end()
        new_text = text[:idx] + "\\n\\n" + line + text[idx:]
    else:
        new_text = text.rstrip() + "\\n\\n## Notas humanas\\n\\n" + line + "\\n"
"""
text = text.replace(record_del_old, record_del_new)
text = text.replace("Append a deletion notice to '## Cambios recientes'", "Append a deletion notice to '## Notas humanas'")
text = text.replace("Registrado en '## Cambios recientes'.", "Registrado en '## Notas humanas'.")


with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Patch applied to asana_obsidian_sync.py successfully.")
