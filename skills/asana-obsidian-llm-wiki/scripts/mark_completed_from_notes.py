#!/usr/bin/env python3
"""Mark Asana tasks completed based on the progress recorded in their NOTES.

Why this exists: portfolios seeded by an MS Project import carry their real
progress as text in the task notes ("Completed: TRUE", "Status: Completado",
"Percent Complete: 100") while Asana's native `completed` flag stays false.
A board like that reports 0/N even when most of the work is finished. This
script reconciles the two.

Usage:
  python3 mark_completed_from_notes.py <PROJECT_GID>            # dry-run (default)
  python3 mark_completed_from_notes.py <PROJECT_GID> --apply    # perform writes

Safety rules:
  * Acts ONLY when a note matches `Completed: TRUE` (case-insensitive)
    AND the task is NOT already completed in Asana.
  * Notes saying `Completed: FALSE` are ignored -> genuinely open work is
    never closed by accident.
  * Dry-run is the default. Writes require an explicit --apply.
  * Re-reads the project after writing and prints the verified counts.

Exit codes: 0 = ok / nothing to do, 1 = at least one write failed.
"""
import json
import os
import re
import sys
import urllib.request

# ---------------------------------------------------------------- credentials
# Read the .env FILE directly — never os.environ. Hermes' secret redactor can
# mask an exported token back to "***" and produce a false "token missing".
def load_env():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
    ]
    if "HERMES_PROFILE_DIR" in os.environ:
        candidates.append(os.path.join(os.environ["HERMES_PROFILE_DIR"], ".env"))
    elif "HERMES_PROFILE" in os.environ:
        candidates.append(os.path.expanduser(f"~/.hermes/profiles/{os.environ['HERMES_PROFILE']}/.env"))
    else:
        candidates.append(os.path.expanduser("~/.hermes/profiles/default/.env"))

    for path in candidates:
        if os.path.exists(path):
            env = {}
            for line in open(path):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k] = v.strip().strip('"').strip("'")
            return env
    raise SystemExit(f"ERROR: no .env found in {candidates}")


env = load_env()
TOKEN = env.get("ASANA_ACCESS_TOKEN")
if not TOKEN:
    keys = [k for k in env if "ASANA" in k.upper()]
    raise SystemExit(f"ERROR: no Asana token. Keys present: {keys}")

HJ = {"Authorization": f"Bearer {TOKEN}"}
HW = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HJ)))


def put(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=HW, method="PUT"
    )
    return json.load(urllib.request.urlopen(req))


def fetch_tasks(gid, opt_fields):
    """Paginate every task in a project."""
    tasks, offset = [], None
    while True:
        url = (
            f"https://app.asana.com/api/1.0/projects/{gid}/tasks"
            f"?limit=100&opt_fields={opt_fields}"
        )
        if offset:
            url += "&offset=" + offset
        data = get(url)
        tasks += data["data"]
        offset = data.get("next_page", {}).get("offset") if data.get("next_page") else None
        if not offset:
            return tasks


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    gid = sys.argv[1]
    apply_flag = "--apply" in sys.argv

    tasks = fetch_tasks(gid, "name,completed,due_on,notes")
    already = sum(1 for t in tasks if t["completed"])

    candidates = []
    for t in tasks:
        if t["completed"]:
            continue
        notes = t.get("notes") or ""
        m = re.search(r"Completed:\s*(TRUE|FALSE)", notes, re.IGNORECASE)
        if m and m.group(1).upper() == "TRUE":
            candidates.append(t)

    print(f"Proyecto: {gid}")
    print(f"Tareas totales: {len(tasks)} | ya completed en Asana: {already}")
    print(f"Candidatas (nota dice Completed: TRUE, Asana en false): {len(candidates)}\n")
    for t in candidates:
        print(f"  [{t.get('due_on')}] {t['name']}")

    if not candidates:
        print("\nNada que hacer.")
        return 0

    if not apply_flag:
        print("\n[DRY-RUN] Nada modificado. Usa --apply para ejecutar.")
        return 0

    print("\n--- APLICANDO ---")
    ok, fail = [], []
    for t in candidates:
        try:
            r = put(
                f"https://app.asana.com/api/1.0/tasks/{t['gid']}",
                {"data": {"completed": True}},
            )
            ok.append((t["name"], r["data"]["completed"]))
        except Exception as e:  # noqa: BLE001 - report, don't abort the batch
            fail.append((t["name"], str(e)[:150]))

    print(f"OK: {len(ok)} | FALLOS: {len(fail)}")
    for name, val in ok:
        print(f"  done: {name} -> completed={val}")
    for name, err in fail:
        print(f"  FAIL: {name} -> {err}")

    # VERIFY — a PUT echoing completed:True is not proof; re-read and count.
    after = fetch_tasks(gid, "name,completed")
    total = len(after)
    done = sum(1 for t in after if t["completed"])
    print(f"\n=== VERIFICADO === {done}/{total} completadas = {round(100 * done / total)}%")

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
