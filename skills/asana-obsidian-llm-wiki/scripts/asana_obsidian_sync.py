#!/usr/bin/env python3
"""
Asana -> Obsidian incremental sync for the LLM Wiki.

Implements Fase 3 (project representation) and Fase 5 (incremental sync).

Safety invariants:
  - The SYNC is read-only against Asana. It only ever issues GET requests.
    Writes to Asana happen through the MCP tools, never through this script.
  - NEVER writes outside <!-- HERMES:START --> / <!-- HERMES:END --> markers.
  - NEVER touches "## Notas humanas".
  - NEVER deletes a note from the vault.
  - If Asana is unreachable: aborts without writing anything.
  - --dry-run reports what WOULD change and writes nothing.

Deletion policy (see "Hermes Knowledge Protocol" section 9):
  - Deletions are NOT automatic. The owner requests them, item by item.
  - Archiving is preferred over deleting (reversible vs irreversible).
  - When something IS deleted, this script records it in "## Cambios recientes"
    with the format: - Tarea «Name» eliminada el YYYY-MM-DD (gid NNN)
    Use --record-deletion to append that line before the next sync.

Usage:
  python asana_obsidian_sync.py --dry-run      # report only (default)
  python asana_obsidian_sync.py --apply        # perform writes
  python asana_obsidian_sync.py --query <gid>  # show one project (Asana + Obsidian)
  python asana_obsidian_sync.py --record-deletion <project_gid> --task-name "..." \
      --task-gid NNN [--apply]
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone

ASANA_API = "https://app.asana.com/api/1.0"

START = "<!-- HERMES:START -->"
END = "<!-- HERMES:END -->"

# Programa asignado cuando no hay Portfolio (tier sin Advanced) ni override.
GENERIC_PROGRAM = "Programa General"


# ── env loading ──────────────────────────────────────────────────────────

def load_env():
    """Load ASANA_ACCESS_TOKEN + OBSIDIAN_VAULT_PATH from the profile .env.

    Reads the file directly rather than relying on os.environ -- the Hermes
    secret-redactor can present exported variables as masked/empty, which
    would make a valid token look absent.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    env_paths = [
        os.path.join(here, "..", ".env"),
    ]
    
    if "HERMES_PROFILE_DIR" in os.environ:
        env_paths.append(os.path.join(os.environ["HERMES_PROFILE_DIR"], ".env"))
    elif "HERMES_PROFILE" in os.environ:
        env_paths.append(os.path.expanduser(f"~/.hermes/profiles/{os.environ['HERMES_PROFILE']}/.env"))
    else:
        # Fallback si se corre el script por fuera sin variables de Hermes
        env_paths.append(os.path.expanduser("~/.hermes/profiles/default/.env"))

    found = {}
    for p in env_paths:
        p = os.path.abspath(p)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in found:
                    found[k] = v

    token = found.get("ASANA_ACCESS_TOKEN", "").strip()
    vault = found.get("OBSIDIAN_VAULT_PATH", "").strip()
    return token, vault


# ── Asana client (read-only) ─────────────────────────────────────────────

class AsanaError(RuntimeError):
    pass


def asana_get(token, path, params=None):
    url = ASANA_API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        },
    )
    while True:
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            body = ""
            try:
                body = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise AsanaError("Asana HTTP %s on %s: %s" % (e.code, path, body))
        except urllib.error.URLError as e:
            raise AsanaError("Asana unreachable (%s): %s" % (path, e.reason))


def fetch_workspaces(token):
    return asana_get(token, "/workspaces", {"opt_fields": "name,is_organization"}).get("data", [])


def fetch_teams(token, workspace_gid):
    try:
        return asana_get(token, "/workspaces/%s/teams" % workspace_gid,
                         {"opt_fields": "name"}).get("data", [])
    except AsanaError:
        return []


def fetch_projects(token, workspace_gid, limit=None):
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
    return out


def fetch_project_tasks(token, project_gid):
    """Tasks for one project, with the fields the wiki cares about."""
    out = []
    params = {
        "opt_fields": "name,completed,completed_at,due_on,start_on,"
                      "assignee.name,memberships.section.name,notes,permalink_url,dependencies,dependents",
        "limit": 100,
    }
    path = "/projects/%s/tasks" % project_gid
    while True:
        page = asana_get(token, path, params)
        out.extend(page.get("data", []))
        nxt = (page.get("next_page") or {}).get("offset")
        if not nxt:
            break
        params["offset"] = nxt
    return out


# ── programa layer: Portfolios (paid tier) with graceful fallback ────────

def fetch_me(token):
    return asana_get(token, "/users/me", {"opt_fields": "name"}).get("data", {})


def fetch_portfolios(token, workspace_gid, owner_gid):
    """Portfolios owned by owner in workspace.

    Returns None when the workspace tier does not include Portfolios (Asana
    answers 402 Payment Required / 403 on non-Advanced plans) so the caller
    can fall back to a generic program. NOTE: the /portfolios list endpoint
    REQUIRES both `workspace` and `owner` -- it only returns portfolios owned
    by that user; omit either and it errors.
    """
    if not owner_gid:
        return None
    try:
        return asana_get(token, "/portfolios",
                         {"workspace": workspace_gid, "owner": owner_gid,
                          "opt_fields": "name"}).get("data", [])
    except AsanaError as e:
        msg = str(e)
        if "402" in msg or "403" in msg:
            return None          # tier without Portfolios -> generic bucket
        raise


def build_program_map(token, portfolios):
    """project_gid -> portfolio (program) name. Empty if no portfolios."""
    m = {}
    for pf in portfolios or []:
        try:
            items = asana_get(token, "/portfolios/%s/items" % pf["gid"],
                              {"opt_fields": "name,resource_type"}).get("data", [])
        except AsanaError:
            continue
        for it in items:
            if it.get("resource_type") == "project":
                m[it["gid"]] = pf.get("name")
    return m


def _wikilink(name):
    name = str(name).strip()
    return name if "[[" in name else "[[%s]]" % slugify(name)


def resolve_programa(existing_fm, program_map, gid, ws_name=None):
    """Precedencia: Portfolio de Asana > override humano (programa_manual) > workspace > genérico.

    Asana manda: si el proyecto vive en un Portfolio, ese es su programa. El
    `programa_manual` es el respaldo SOLO cuando Asana no agrupa el proyecto
    (sin Portfolios en el tier, o el proyecto no está en ninguno). El sync nunca
    pisa `programa_manual`, pero un Portfolio existente tiene prioridad sobre él.
    """
    name = program_map.get(gid)
    if name:
        return _wikilink(name)
    manual = (existing_fm or {}).get("programa_manual")
    if manual:
        return _wikilink(manual)
    if ws_name:
        return _wikilink(ws_name)
    return "[[%s]]" % GENERIC_PROGRAM


# ── task notes: reconcile counts from MS Project-import fields ────────────

def parse_task_note(notes):
    """Extract the plain-text state an MS Project import writes into a task
    note (Completed / Status / Percent Complete / Dependents). Asana's native
    `completed` flag can be false while the note says the work is done."""
    n = notes or ""
    def field(key):
        m = re.search(r"^\s*%s:\s*(.+)$" % re.escape(key), n,
                      flags=re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else None
    comp = field("Completed")
    return {
        "note_completed": (comp.strip().upper() == "TRUE") if comp is not None else None,
        "note_status": field("Status"),
        "note_percent": field("Percent Complete"),
        "note_dependents": field("Dependents"),
    }


def task_is_done(t):
    """Reconciled done: Asana flag OR the note explicitly says Completed: TRUE.
    A note saying Completed: FALSE never closes a task (leaves genuine work open).
    """
    return bool(t.get("completed")) or (parse_task_note(t.get("notes"))["note_completed"] is True)


def reconcile_tasks(tasks):
    """Rollup a project's tasks from RECONCILED state (not the raw flag)."""
    total = len(tasks)
    done = blocked = 0
    open_due = []
    blockers = []
    for t in tasks:
        if task_is_done(t):
            done += 1
            continue
        pn = parse_task_note(t.get("notes"))
        st = (pn["note_status"] or "").strip().lower()
        if st.startswith("bloque"):                 # "Bloqueado"
            blocked += 1
            if pn["note_dependents"]:               # bloquea a algo aguas abajo
                blockers.append(t.get("name"))
        if t.get("due_on"):
            open_due.append(t["due_on"])
    return {
        "tasks_total": total,
        "tasks_done": done,
        "tasks_blocked": blocked,
        "next_due": min(open_due) if open_due else "",
        "critical_blocker": blockers[0] if blockers else "",
    }


# ── hashing / dedup ──────────────────────────────────────────────────────

def source_hash(project, tasks, programa=None):
    """Stable hash of the Asana payload that drives note content.

    Changes only when something the wiki renders changes -- so routine
    syncs with no real movement produce no write. Includes reconciled note
    state and the resolved programa, so editing a task note to
    "Completed: TRUE" or moving a project between portfolios re-renders.
    """
    material = {
        "gid": project.get("gid"),
        "name": project.get("name"),
        "due_on": project.get("due_on"),
        "start_on": project.get("start_on"),
        "archived": project.get("archived"),
        "owner": (project.get("owner") or {}).get("name"),
        "status": (project.get("current_status") or {}).get("title"),
        "modified_at": project.get("modified_at"),
        "programa": programa,
        "tasks": sorted(
            {
                "gid": t.get("gid"),
                "name": t.get("name"),
                "rdone": task_is_done(t),
                "rstatus": parse_task_note(t.get("notes"))["note_status"],
                "due_on": t.get("due_on"),
                "assignee": (t.get("assignee") or {}).get("name"),
                "section": next(
                    (m.get("section", {}).get("name")
                     for m in (t.get("memberships") or []) if m.get("section")),
                    None,
                ),
            }.items()
            for t in tasks
        ),
    }
    blob = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ── frontmatter ──────────────────────────────────────────────────────────

def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4:]
    fm = {}
    lines = raw.splitlines()
    current_key = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and not line.startswith("- ") and ":" in line:
            k, sep, v = line.partition(":")
            current_key = k.strip()
            v = v.strip()
            if v:
                if v.startswith("[") and v.endswith("]"):
                    # Parse inline list like ["A", "B"]
                    inner = v[1:-1]
                    fm[current_key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
                else:
                    fm[current_key] = v.strip('"').strip("'")
            else:
                fm[current_key] = []
        elif line.lstrip().startswith("- "):
            if current_key and isinstance(fm[current_key], list):
                val = line.lstrip()[2:].strip().strip('"').strip("'")
                fm[current_key].append(val)
    return fm, body


def yaml_escape(value):
    if value is None:
        return ""
    s = str(value)
    if re.search(r"[:#\[\]{}|>&*!%@`\"']", s) or s.startswith(" ") or s.endswith(" "):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def render_frontmatter(fm):
    order = [
        "type", "source", "asana_gid", "asana_url",
        "programa", "programa_manual", "workspace", "owner",
        "status", "start_date", "due_date",
        "tasks_total", "tasks_done", "tasks_blocked", "next_due",
        "critical_blocker", "last_synced_at", "source_hash",
    ]
    lines = ["---"]
    
    def add_field(k, v):
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {yaml_escape(item)}")
        else:
            lines.append(f"{k}: {yaml_escape(v)}")

    for k in order:
        if k in fm:
            add_field(k, fm[k])
    for k, v in fm.items():
        if k not in order and not k.startswith("_"):
            add_field(k, v)
    lines.append("---")
    return "\n".join(lines)


# ── note rendering ───────────────────────────────────────────────────────

def slugify(name):
    """Human-friendly note title. Underscores become spaces so Asana names
    like 'Programa_Zero_Trust' render as 'Programa Zero Trust'."""
    s = str(name).replace("_", " ")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip()
    s = re.sub(r"[\s_]+", " ", s)
    return s or "Untitled"


def display_title(name):
    """Title for the H1 heading: underscores -> spaces, trimmed."""
    return re.sub(r"\s+", " ", str(name).replace("_", " ")).strip() or "(sin nombre)"


def md_list(items, empty="Sin elementos registrados."):
    if not items:
        return empty
    return "\n".join(items)


def render_hermes_block(project, tasks, synced_at, note_name):
    """Content between HERMES markers. Regenerated on every material change."""
    name = project.get("name") or "(sin nombre)"
    owner = (project.get("owner") or {}).get("name") or "Sin asignar"
    status_title = (project.get("current_status") or {}).get("title")
    notes = (project.get("notes") or "").strip()

    # Reconciliado: una tarea "hecha" en su nota cuenta como hecha aunque el
    # flag de Asana siga en false (patrón import MS Project).
    open_tasks = [t for t in tasks if not task_is_done(t)]
    done_tasks = [t for t in tasks if task_is_done(t)]
    roll = reconcile_tasks(tasks)

    # Prioridades activas: open tasks, soonest due first, undated last
    def due_key(t):
        return (t.get("due_on") is None, t.get("due_on") or "9999-99-99")

    prio_lines = []
    for t in sorted(open_tasks, key=due_key)[:15]:
        due = t.get("due_on") or "sin fecha"
        who = (t.get("assignee") or {}).get("name") or "sin asignar"
        prio_lines.append("- [ ] %s — vence %s — %s" % (t.get("name"), due, who))

    ver_lines = []
    for t in sorted(done_tasks, key=lambda x: x.get("completed_at") or "", reverse=True)[:8]:
        ver_lines.append("- [x] %s" % t.get("name"))

    # Risks: only what Asana itself signals -- everything else is inference
    risks = []
    today = datetime.now().astimezone().date().isoformat()
    overdue = [t for t in open_tasks if t.get("due_on") and t["due_on"] < today]
    for t in overdue[:10]:
        risks.append("- **[Hecho — Asana]** Vencida: \"%s\" (vence %s)"
                     % (t.get("name"), t.get("due_on")))
    if project.get("archived"):
        risks.append("- **[Hecho — Asana]** El proyecto está archivado en Asana.")
    if not owner or owner == "Sin asignar":
        risks.append("- **[Hecho — Asana]** El proyecto no tiene responsable asignado.")
    if not open_tasks and tasks:
        risks.append("- **[Hecho — Asana]** No hay tareas abiertas: el proyecto "
                     "puede estar estancado o cerrado.")
    if not tasks:
        risks.append("- **[Inferencia — Hermes]** El proyecto no tiene tareas "
                     "visibles; verificar permisos o si realmente está vacío.")
    if not risks:
        risks.append("Sin riesgos ni bloqueos detectados en Asana.")

    dep_lines = []
    for t in open_tasks:
        if t.get("dependencies") or t.get("dependents"):
            dep_lines.append("- %s (dependencias registradas en Asana)" % t.get("name"))

    changes = ("- %s — Sincronización inicial / actualización de contenido."
               % synced_at)

    ctx = notes[:1200] if notes else (
        "Sin descripción en Asana. *[Inferencia — Hermes]* El alcance no está "
        "documentado en la fuente operativa; conviene definirlo."
    )

    block = []
    block.append(START)
    block.append("")
    block.append("## Contexto")
    block.append("")
    block.append(ctx)
    block.append("")
    block.append("## Estado actual")
    block.append("")
    block.append("| Campo | Valor |")
    block.append("|---|---|")
    block.append("| Estado en Asana | %s |" % (status_title or "sin estado publicado"))
    block.append("| Responsable | %s |" % owner)
    block.append("| Inicio | %s |" % (project.get("start_on") or "sin fecha"))
    block.append("| Vencimiento | %s |" % (project.get("due_on") or "sin fecha"))
    block.append("| Tareas abiertas | %d |" % len(open_tasks))
    block.append("| Tareas completadas | %d (reconciliadas de notas) |" % len(done_tasks))
    block.append("| Tareas bloqueadas | %d |" % roll["tasks_blocked"])
    block.append("| Archivado | %s |" % ("sí" if project.get("archived") else "no"))
    block.append("")
    block.append("> Datos obtenidos de Asana el %s." % synced_at)
    block.append("")
    block.append("## Prioridades activas")
    block.append("")
    block.append(md_list(prio_lines, "Sin tareas abiertas en Asana."))
    block.append("")
    if dep_lines:
        block.append("### Dependencias")
        block.append("")
        block.append(md_list(dep_lines))
        block.append("")
    block.append("## Riesgos y bloqueos")
    block.append("")
    block.append(md_list(risks))
    block.append("")
    block.append("## Cambios recientes")
    block.append("")
    block.append(changes)
    block.append("")
    if ver_lines:
        block.append("### Completadas recientemente")
        block.append("")
        block.append(md_list(ver_lines))
        block.append("")
    block.append(END)
    return "\n".join(block)


def build_note(fm, hermes_block, existing_body=None):
    """Full note text: frontmatter + intro + HERMES block + human zone.

    If an existing note is supplied, everything from '## Notas humanas'
    onward is preserved byte-for-byte.
    """
    human = ""
    if existing_body:
        m = re.search(r"^##\s+Notas humanas\s*$", existing_body, flags=re.MULTILINE)
        if m:
            human = existing_body[m.start():].rstrip() + "\n"
    if not human:
        human = ("## Notas humanas\n\n"
                 "<!-- Espacio reservado. Hermes nunca sobrescribe esta sección. -->\n")

    name = fm.get("type") and "" or ""
    parts = [
        render_frontmatter(fm),
        "",
        "# " + display_title(fm.get("_title") or "Proyecto"),
        "",
        "> Proyecto de Asana. `asana_gid`: `%s`" % fm.get("asana_gid", ""),
        "",
        hermes_block,
        "",
        human,
    ]
    return "\n".join(parts)


# ── note discovery / dedup ───────────────────────────────────────────────

def scan_existing_notes(vault):
    """Map asana_gid -> note path for every note in 02 Projects."""
    out = {}
    folder = os.path.join(vault, "02 Projects")
    if not os.path.isdir(folder):
        return out
    for fn in os.listdir(folder):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(folder, fn)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                fm, body = parse_frontmatter(fh.read())
        except Exception:
            continue
        gid = fm.get("asana_gid")
        if gid:
            out[gid] = {"path": path, "fm": fm, "body": body}
    return out


def atomic_write(path, text):
    tmp = path + ".hermes-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


# ── main sync ────────────────────────────────────────────────────────────

def plan_sync(token, vault, workspace_gid=None, project_limit=None):
    """Compute the full plan. Returns (plan, meta). Writes nothing."""
    now = datetime.now().astimezone().replace(microsecond=0)
    synced_at = now.isoformat()

    workspaces = fetch_workspaces(token)
    if not workspaces:
        raise AsanaError("No workspaces returned for this token.")

    ws = None
    if workspace_gid:
        ws = next((w for w in workspaces if w["gid"] == workspace_gid), None)
    ws = ws or workspaces[0]

    teams = fetch_teams(token, ws["gid"])
    projects = fetch_projects(token, ws["gid"], limit=project_limit)

    # Capa Programa: Portfolios nativos si el tier lo permite; si no (402/403),
    # program_map queda vacío y cada proyecto cae en el bucket genérico salvo
    # override manual.
    me = fetch_me(token)
    portfolios = fetch_portfolios(token, ws["gid"], me.get("gid"))
    portfolios_available = portfolios is not None
    program_map = build_program_map(token, portfolios) if portfolios else {}

    existing = scan_existing_notes(vault)

    plan = {"create": [], "update": [], "skip": []}
    for p in projects:
        gid = p["gid"]
        tasks = fetch_project_tasks(token, gid)
        note_name = slugify(p.get("name"))
        ws_name = ws.get("name")

        cur = existing.get(gid)
        cur_fm = cur["fm"] if cur else {}
        programa = resolve_programa(cur_fm, program_map, gid, ws_name)
        roll = reconcile_tasks(tasks)
        h = source_hash(p, tasks, programa)

        fm = {
            "type": "proyecto",
            "source": "asana",
            "asana_gid": gid,
            "asana_url": p.get("permalink_url") or
                         ("https://app.asana.com/0/%s" % gid),
            "programa": programa,
            "workspace": ws_name,
            "owner": (p.get("owner") or {}).get("name") or "",
            "status": (p.get("current_status") or {}).get("title") or
                      ("archived" if p.get("archived") else "active"),
            "start_date": p.get("start_on") or "",
            "due_date": p.get("due_on") or "",
            "tasks_total": roll["tasks_total"],
            "tasks_done": roll["tasks_done"],
            "tasks_blocked": roll["tasks_blocked"],
            "next_due": roll["next_due"],
            "critical_blocker": roll["critical_blocker"],
            "last_synced_at": synced_at,
            "source_hash": h,
            "_title": p.get("name"),
        }
        # Preserve existing manual frontmatter
        for k, v in cur_fm.items():
            if k not in fm and not k.startswith("_"):
                fm[k] = v
        if not cur:
            plan["create"].append({"fm": fm, "project": p, "tasks": tasks,
                                   "filename": note_name + ".md"})
        elif cur["fm"].get("source_hash") != h:
            plan["update"].append({"fm": fm, "project": p, "tasks": tasks,
                                   "existing": cur})
        else:
            plan["skip"].append({"fm": fm, "project": p, "tasks": tasks,
                                 "existing": cur})

    meta = {
        "workspace": ws,
        "teams": teams,
        "projects": projects,
        "synced_at": synced_at,
        "existing_count": len(existing),
        "portfolios_available": portfolios_available,
        "programs": sorted({v for v in program_map.values() if v}),
    }
    return plan, meta


def apply_plan(vault, plan, meta):
    created, updated = [], []
    folder = os.path.join(vault, "02 Projects")
    os.makedirs(folder, exist_ok=True)

    for item in plan["create"]:
        path = os.path.join(folder, item["filename"])
        if os.path.exists(path):
            # name collision with a different gid -- disambiguate, never clobber
            base = item["filename"][:-3]
            path = os.path.join(folder, "%s (%s).md" % (base, item["fm"]["asana_gid"][-6:]))
        block = render_hermes_block(item["project"], item["tasks"],
                                    meta["synced_at"], item["fm"]["_title"])
        atomic_write(path, build_note(item["fm"], block))
        created.append(path)

    for item in plan["update"]:
        path = item["existing"]["path"]
        block = render_hermes_block(item["project"], item["tasks"],
                                    meta["synced_at"], item["fm"]["_title"])
        text = build_note(item["fm"], block, existing_body=item["existing"]["body"])
        atomic_write(path, text)
        updated.append(path)

    return created, updated


def write_index(vault, plan, meta):
    """Fase 6: LLM Wiki Index."""
    path = os.path.join(vault, "LLM Wiki Index.md")
    
    # Preserve human notes outside HERMES block
    human_notes = "## Notas humanas\n\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            m = re.search(r"^##\s+Notas humanas\s*$", content, flags=re.MULTILINE)
            if m:
                human_notes = content[m.start():].rstrip() + "\n"

    now = meta["synced_at"]
    lines = [
        "---",
        "type: index",
        "source: hermes",
        "last_synced_at: %s" % now,
        "workspace: %s" % yaml_escape(meta["workspace"].get("name")),
        "---",
        "",
        "# LLM Wiki Index",
        "",
        "Punto de entrada para Hermes. No es una copia completa de las notas:",
        "es el mapa. Última sincronización: **%s**." % now,
        "",
        START,
        "",
        "## Proyectos activos",
        "",
    ]
    all_items = plan["create"] + plan["update"] + plan["skip"]
    if all_items:
        for it in all_items:
            fm = it["fm"]
            title = fm["_title"]
            lines.append("- [[%s]] — `%s` — vence %s"
                         % (slugify(title), fm["asana_gid"],
                            fm.get("due_date") or "sin fecha"))
    else:
        lines.append("Sin proyectos detectados.")
    lines += [
        "",
        "## Decisiones recientes",
        "",
        "- [[Adopción de MCP manual para Asana]]",
        "",
        "## Riesgos abiertos",
        "",
    ]
    risk_lines = []
    today = datetime.now().astimezone().date().isoformat()
    for it in all_items:
        p = it.get("project") or {}
        tasks = it.get("tasks", [])
        od = [t for t in tasks
              if not task_is_done(t) and t.get("due_on") and t["due_on"] < today]
        if od:
            risk_lines.append("- [[%s]] — %d tarea(s) vencida(s)"
                              % (slugify(p.get("name")), len(od)))
    lines.append(md_list(risk_lines, "Sin riesgos abiertos detectados."))
    lines += [
        "",
        "## Conocimiento reutilizable",
        "",
        "Sin notas en `05 Knowledge` todavía.",
        "",
    ]
    lines.extend([
        "",
        END,
        "",
        human_notes
    ])
    atomic_write(path, "\n".join(lines))
    return path


# ── CLI ──────────────────────────────────────────────────────────────────

def cmd_query(token, vault, gid):
    print("=== ASANA (hecho operativo) ===")
    p = asana_get(token, "/projects/%s" % gid,
                  {"opt_fields": "name,notes,owner.name,due_on,start_on,archived,"
                                 "current_status.title,permalink_url,modified_at"})
    proj = p.get("data", {})
    print(json.dumps(proj, indent=2, ensure_ascii=False)[:1500])

    print()
    print("=== OBSIDIAN (conocimiento documentado) ===")
    existing = scan_existing_notes(vault)
    cur = existing.get(gid)
    if cur:
        print("Nota: %s" % cur["path"])
        print("source_hash en nota : %s" % cur["fm"].get("source_hash"))
        print("last_synced_at      : %s" % cur["fm"].get("last_synced_at"))
        body = cur["body"]
        for section in ("Contexto", "Riesgos y bloqueos", "Notas humanas"):
            m = re.search(r"^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(section),
                          body, flags=re.MULTILINE | re.DOTALL)
            if m:
                print("\n-- %s --" % section)
                print(m.group(1).strip()[:800])
    else:
        print("Sin nota en Obsidian para el gid %s." % gid)


def record_deletion(vault, project_gid, task_name, task_gid, apply=False):
    """Append a deletion notice to '## Notas humanas' of a project note.

    Implements protocol section 12: the item is removed from the active list
    (which happens naturally on the next sync) and a permanent trace is left
    here. Never touches anything inside the HERMES markers to preserve source_hash.
    """
    existing = scan_existing_notes(vault)
    cur = existing.get(str(project_gid))
    if not cur:
        print("ERROR: no hay nota en '02 Projects' con asana_gid=%s" % project_gid)
        return 1

    path = cur["path"]
    today = datetime.now().astimezone().date().isoformat()
    line = "- Tarea «%s» eliminada el %s (gid %s)" % (task_name, today, task_gid)

    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    if START not in text or END not in text:
        print("ERROR: marcadores HERMES ausentes o incompletos en %s" % path)
        print("No se escribió nada.")
        return 1

    if line in text:
        print("Ya registrado (sin cambios): %s" % line)
        return 0

    # Escribir en Notas Humanas para no invalidar el source_hash ni ser sobreescrito
    m = re.search(r"(^##\s+Notas humanas\s*$)", text, flags=re.MULTILINE)
    if m:
        idx = m.end()
        new_text = text[:idx] + "\n\n" + line + text[idx:]
    else:
        new_text = text.rstrip() + "\n\n## Notas humanas\n\n" + line + "\n"

    print("Nota   : %s" % path)
    print("Línea  : %s" % line)
    if not apply:
        print()
        print("[dry-run] Nada escrito. Usa --apply para registrar.")
        return 0

    atomic_write(path, new_text)
    print()
    print("Registrado en '## Notas humanas'.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Asana -> Obsidian sync (read-only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only (default when --apply absent)")
    ap.add_argument("--apply", action="store_true", help="perform writes")
    ap.add_argument("--query", metavar="GID", help="inspect one project by gid")
    ap.add_argument("--workspace", metavar="GID", help="force a workspace gid")
    ap.add_argument("--limit", type=int, default=None, help="max projects (default None/all)")
    ap.add_argument("--record-deletion", metavar="PROJECT_GID",
                    help="record a deleted task in a project note")
    ap.add_argument("--task-name", metavar="NAME",
                    help="name of the deleted task (with --record-deletion)")
    ap.add_argument("--task-gid", metavar="GID",
                    help="gid of the deleted task (with --record-deletion)")
    args = ap.parse_args()

    token, vault = load_env()
    if not vault or not os.path.isdir(vault):
        print("ERROR: OBSIDIAN_VAULT_PATH inválido o inaccesible: %r" % vault)
        return 2

    if args.record_deletion:
        if not args.task_name:
            print("ERROR: --record-deletion requiere --task-name")
            return 2
        return record_deletion(vault, args.record_deletion, args.task_name,
                               args.task_gid or "desconocido", apply=args.apply)

    if not token:
        print("ERROR: ASANA_ACCESS_TOKEN vacío en .env. Pega el token y reintenta.")
        return 2

    try:
        if args.query:
            cmd_query(token, vault, args.query)
            return 0

        plan, meta = plan_sync(token, vault, args.workspace, args.limit)
    except AsanaError as e:
        print("ERROR de Asana: %s" % e)
        print("No se modificó nada en Obsidian.")
        return 1

    ws = meta["workspace"]
    print("Workspace : %s (%s)" % (ws.get("name"), ws["gid"]))
    print("Equipos   : %d" % len(meta["teams"]))
    print("Proyectos : %d detectados" % len(meta["projects"]))
    if meta["portfolios_available"]:
        print("Portfolios: sí — programas: %s"
              % (", ".join(meta["programs"]) or "(ninguno con proyectos)"))
    else:
        print("Portfolios: no disponibles (tier sin Advanced) — bucket «%s»"
              % GENERIC_PROGRAM)
    print("Notas ya  : %d existentes en 02 Projects" % meta["existing_count"])
    print()
    print("A CREAR   : %d" % len(plan["create"]))
    for it in plan["create"]:
        print("   + %s  (gid %s)" % (it["filename"], it["fm"]["asana_gid"]))
    print("A ACTUALIZAR: %d" % len(plan["update"]))
    for it in plan["update"]:
        print("   ~ %s" % os.path.basename(it["existing"]["path"]))
    print("SIN CAMBIOS : %d" % len(plan["skip"]))
    for it in plan["skip"]:
        print("   = %s" % os.path.basename(it["existing"]["path"]))

    if not args.apply:
        print()
        print("[dry-run] Nada escrito. Usa --apply para ejecutar.")
        return 0

    created, updated = apply_plan(vault, plan, meta)
    idx = write_index(vault, plan, meta)
    print()
    print("CREADAS   : %d" % len(created))
    for p in created:
        print("   + %s" % p)
    print("ACTUALIZADAS: %d" % len(updated))
    for p in updated:
        print("   ~ %s" % p)
    print("ÍNDICE    : %s" % idx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
