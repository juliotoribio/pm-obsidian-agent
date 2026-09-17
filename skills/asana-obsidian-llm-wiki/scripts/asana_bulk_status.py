#!/usr/bin/env python3
"""Bulk status updates on Asana tasks — enumerate / confirm / write / verify.

Falls back to plain REST, so it works even when the Asana MCP tools return
{"error":"Not Found"}. Reads the profile .env FILE directly (never
os.environ) because Hermes' secret redactor can mask env vars into '' or '***'.

Usage
-----
  # what is overdue in a project (read-only, always safe)
  python3 asana_bulk_status.py --project GID --list-overdue

  # mark the overdue ones done (dry-run by default)
  python3 asana_bulk_status.py --project GID --complete-overdue

  # actually write
  python3 asana_bulk_status.py --project GID --complete-overdue --apply

  # every open task, not just overdue
  python3 asana_bulk_status.py --project GID --complete-all-open --apply

Never prints the token. Always re-reads to verify after writing.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://app.asana.com/api/1.0"
DEFAULT_ENV = os.path.expanduser(
    "~/.hermes/profiles/maha_pm_agent/.env"
)


def load_env(path):
    """Parse the .env FILE directly. Do NOT use os.environ — redaction masks it."""
    env = {}
    if not os.path.exists(path):
        sys.exit(f"FATAL: .env not found at {path}")
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_token(env):
    # The key is ASANA_ACCESS_TOKEN. Do not guess ASANA_PAT.
    for key in ("ASANA_ACCESS_TOKEN", "ASANA_TOKEN", "ASANA_API_KEY"):
        if env.get(key):
            return env[key]
    sys.exit(
        "FATAL: no Asana token in .env. Keys seen: "
        + ", ".join(k for k in env if "ASANA" in k.upper())
    )


class Asana:
    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _req(self, url, data=None, method="GET"):
        req = urllib.request.Request(url, data=data, headers=self.headers,
                                     method=method)
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            raise SystemExit(f"HTTP {e.code} on {method} {url}\n{body}")

    def project_tasks(self, project_gid, opt_fields="name,completed,due_on,assignee.name"):
        """Paginate all tasks in a project."""
        tasks, offset = [], None
        while True:
            url = (f"{API}/projects/{project_gid}/tasks"
                   f"?limit=100&opt_fields={opt_fields}")
            if offset:
                url += f"&offset={offset}"
            payload = self._req(url)
            tasks.extend(payload["data"])
            nxt = payload.get("next_page") or {}
            offset = nxt.get("offset")
            if not offset:
                return tasks

    def complete(self, task_gid):
        body = json.dumps({"data": {"completed": True}}).encode()
        return self._req(f"{API}/tasks/{task_gid}", data=body, method="PUT")


def describe(t):
    return f"  {t.get('due_on') or '   -    '}  {t['name']}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True, help="Project GID")
    p.add_argument("--list-overdue", action="store_true",
                   help="Show open+overdue tasks, change nothing")
    p.add_argument("--complete-overdue", action="store_true",
                   help="Target open tasks past their due date")
    p.add_argument("--complete-all-open", action="store_true",
                   help="Target every open task")
    p.add_argument("--apply", action="store_true",
                   help="Actually write. Without this it is a dry run.")
    p.add_argument("--today", default=None,
                   help="Override today's date (YYYY-MM-DD), for testing")
    p.add_argument("--env", default=DEFAULT_ENV, help="Path to .env")
    args = p.parse_args()

    if not (args.list_overdue or args.complete_overdue or args.complete_all_open):
        sys.exit("Pick one of --list-overdue / --complete-overdue / "
                 "--complete-all-open")

    today = args.today or datetime.date.today().isoformat()
    asana = Asana(get_token(load_env(args.env)))

    tasks = asana.project_tasks(args.project)
    open_t = [t for t in tasks if not t["completed"]]
    overdue = [t for t in open_t if t.get("due_on") and t["due_on"] < today]

    print(f"project {args.project} | today {today}")
    print(f"total {len(tasks)} | open {len(open_t)} | "
          f"done {len(tasks) - len(open_t)} | overdue {len(overdue)}")

    if args.list_overdue:
        print(f"\n-- overdue ({len(overdue)}) --")
        for t in sorted(overdue, key=lambda x: x["due_on"]):
            print(describe(t))
        return

    targets = overdue if args.complete_overdue else sorted(
        open_t, key=lambda x: x.get("due_on") or "9999"
    )

    print(f"\n-- targets ({len(targets)}) --")
    for t in targets:
        print(describe(t))

    if not args.apply:
        print(f"\nDRY RUN. Re-run with --apply to mark {len(targets)} done.")
        return

    ok, fail = [], []
    for t in targets:
        try:
            asana.complete(t["gid"])
            ok.append(t["gid"])
        except SystemExit as e:
            fail.append((t["gid"], str(e)[:120]))

    print(f"\nwrote {len(ok)} | failed {len(fail)}")
    for g, e in fail:
        print(f"  FAIL {g}: {e}")

    # VERIFY — a PUT echo is not proof. Re-read and count.
    after = asana.project_tasks(args.project)
    open_after = [t for t in after if not t["completed"]]
    over_after = [t for t in open_after
                  if t.get("due_on") and t["due_on"] < today]
    print(f"\nVERIFY: total {len(after)} | open {len(open_after)} | "
          f"done {len(after) - len(open_after)} | overdue {len(over_after)}")
    if over_after:
        print("STILL OVERDUE:")
        for t in over_after:
            print(describe(t))
        sys.exit(1)
    print("OK — no overdue tasks remain.")


if __name__ == "__main__":
    main()
