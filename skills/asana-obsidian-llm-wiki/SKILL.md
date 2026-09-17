---
name: asana-obsidian-llm-wiki
description: "Sync Asana projects into an Obsidian LLM Wiki, and read/write Asana project state via REST — MCP setup, marker-safe note generation, incremental sync, bulk task status updates, notes-driven progress reconciliation, and PM status reporting. Use when wiring Asana to Obsidian, debugging the sync script, adding wiki sections, marking/moving tasks in bulk, reporting portfolio progress, or when a board appears stalled and needs verification against task notes."
version: 1.5.0
platforms: [macos, linux]
---

# Asana → Obsidian LLM Wiki

Connect Asana (operational truth) to an Obsidian vault (documental truth) via
Hermes. Asana holds tasks/projects/owners/dates/status. Obsidian holds context,
decisions, risks, learnings, meeting notes. Hermes orchestrates one-way
(Asana → Obsidian). No embeddings, no vector DB — plain Markdown,
YAML frontmatter, WikiLinks, full-text search.

## When to use

- Setting up Asana↔Obsidian integration from scratch.
- The hourly sync is failing or not firing.
- Adding a section to generated project notes.
- A note lost its human content, or markers got corrupted.
- **Auditing or shipping this skill set as a package for someone else** (the
  owner says *"estoy probando esto para dejarlo como un skill estándar para
  cualquiera"* or links his own repo). Switch from build mode to QA mode and
  read `references/skill-packaging-qa.md` first — the review standard changes
  from "works for me" to "works for a stranger".

## Key facts (established 2026-09-17)

### Asana is NOT in the Hermes MCP catalog

`hermes mcp catalog` ships only `linear` and `n8n` on Hermes v0.15.1.
`hermes mcp install asana` fails: `'asana' is not in the catalog`.

**Workaround:** configure `mcp_servers.asana` manually using
`@roychri/mcp-server-asana@1.8.0` (stdio via `npx`).

That server authenticates with a **Personal Access Token**
(`ASANA_ACCESS_TOKEN`) — **not** OAuth. It exposes a `READ_ONLY_MODE=true`
env flag that disables all write/create/delete tools **at the server level**,
which is stronger than filtering tools by name. Always ship with read-only on
first.

## Setup

### 1. Token — get the right screen

The PAT does **not** come from the developer *app* screen. Asana has two
panels that look alike and users reliably pick the wrong one:

| Panel | Gives | Use for |
|---|---|---|
| **MCP de Asana / app config** | Client ID + Client Secret | OAuth only |
| **Tokens de acceso personal** | Personal Access Token | `ASANA_ACCESS_TOKEN` ✅ |

Direct URL: **`https://app.asana.com/0/developer-console`** → section
"Tokens de acceso personal" → Create new token.

Add to the profile `.env`, line for the key already present:

```bash
ASANA_ACCESS_TOKEN=<paste here>
```

Never print the token. Never put it in the vault. See
`references/credential-handling.md` for the paste-back protocol.

### 1b. Validate the token by CALLING, not by inspecting

**Do not judge a token by its shape.** Asana's own docs (Authentication →
Personal access token) state:

> "Asana API tokens should be treated as opaque. Token formats may change
> without notice. Validating a token's format on the client side could result
> in unexpected breakages."

Modern PATs look like `2/<digits>/<digits>:<hex>` — with slashes and a colon,
i.e. exactly what an older-era OAuth token looked like. Concluding "that's not
a PAT, wrong screen" from the prefix is WRONG and burns the user's patience.
Verify with a live call instead:

```bash
python3 scripts/asana_test_connection.py   # GET /users/me + /workspaces
```

That script reports validity, identity, and the workspace gid in one shot.
Run it *before* diagnosing anything.

### 2. MCP server config

**Do NOT** `patch`/`write_file` `config.yaml` — it's guarded and will refuse.
**Do NOT** rely on `hermes mcp add --args` — argparse swallows `-y` as a
Hermes flag and fails with `unrecognized arguments`. (Verified: `--args`,
`--args=`, and `--args --` all fail.)

Use the same code path the CLI uses:

```bash
cd /path/to/hermes-agent && venv/bin/python -c "
import sys; sys.path.insert(0, '/path/to/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg.setdefault('mcp_servers', {})['asana'] = {
    'command': 'npx',
    'args': ['-y', '@roychri/mcp-server-asana@1.8.0'],
    'env': {'ASANA_ACCESS_TOKEN': '\${ASANA_ACCESS_TOKEN}',
            'READ_ONLY_MODE': 'true'},
    'timeout': 120, 'connect_timeout': 90,
}
save_config(cfg)"
```

Verify: `hermes mcp list` → `asana ... ✓ enabled`.

### 3. Vault structure

```bash
V="/path/to/vault"
mkdir -p "$V/02 Projects" "$V/04 Decisions" "$V/05 Knowledge" \
         "$V/07 Agents" "$V/99 System"
```

Then write `99 System/Hermes Knowledge Protocol.md` (rules) plus
`07 Agents/<Agent>.md` and seed `04 Decisions/`. Register the vault:

```bash
OBSIDIAN_VAULT_PATH="/path/to/vault"
```

Find vaults via `~/Library/Application Support/obsidian/obsidian.json`
(macOS) — the `vaults` map lists every registered vault path. Don't guess;
a user with several vaults needs to pick one.

### 4. Gateway (the silent killer)

Cron jobs only fire if that **profile's** gateway runs. Check:

```bash
launchctl list | grep hermes         # macOS: the REAL truth (PID + status)
hermes cron status                   # "Gateway is running — cron jobs will fire"
hermes gateway status                # LEAST reliable — see warning below
```

If the profile is `not running`: `hermes gateway install`.

**⚠️ `hermes gateway status` can report "✓ loaded" while the process is dead.**
The reliable signals are `launchctl list` (macOS) / `systemctl --user status`
(Linux) — a real PID with status `0` — and `hermes cron status`. Always confirm
with one of those, never with `gateway status` alone.

**Symptom of a dead-but-loaded gateway:** `Next run` stays frozen in the past
on `hermes cron list`, and nothing fires. No error surfaces anywhere the user
would look.

### Telegram token conflicts (the #1 cause of dead gateways)

**Each Hermes profile needs its OWN `TELEGRAM_BOT_TOKEN`.** Two profiles
sharing a token produce an infinite restart loop:

```
ERROR gateway.run: Gateway hit a non-retryable startup conflict:
telegram: Telegram bot token already in use (PID 1438).
```

The gateway starts, collides, exits, and launchd/systemd revives it — forever.
Cron never fires. Detect duplicate tokens across profiles with a fingerprint
check (never print the tokens themselves):

```python
import hashlib
# hash each profile's token, compare the digests
h = hashlib.sha256(token.encode()).hexdigest()[:10]
```

A reusable checker ships with this skill:

```bash
python3 scripts/check_telegram_conflicts.py          # fingerprints every profile
python3 scripts/check_telegram_conflicts.py --hermes-home ~/.hermes
```

It prints a short SHA-256 fingerprint per token (never the token) and names
any profile set sharing one. **Run it during onboarding for every new profile,
before starting that profile's gateway.**

**Also check the stale error log, not just the live one.** After fixing the
token, `gateway.error.log` still shows old collision lines. Compare timestamps
against the restart time before concluding it's still broken.

### What must be unique vs. shared per profile

| Variable | Per-profile unique? | Why |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ **Unique** | Two profiles, one token = restart loop |
| `TELEGRAM_HOME_CHANNEL` | ❌ Shared OK | It's the *destination* chat (the owner's user ID) — same everywhere |
| `TELEGRAM_ALLOWED_USERS` | ❌ Shared OK | The owner's user ID |
| `OBSIDIAN_VAULT_PATH` | ⚠️ Decide | Share one vault or isolate per agent — isolation avoids write races |
| `ASANA_ACCESS_TOKEN` | ❌ Shared OK | Same PAT reads the same workspace |

Don't change `TELEGRAM_HOME_CHANNEL` when creating a new bot — that's a
different thing (where messages land, not who sends them). Changing it breaks
notifications for no benefit.

### ⚠️ A cron job can be "enabled" and NEVER have run

The worst staleness failure is silent: the job is registered, enabled, has a
valid schedule and a future `next_run_at` — and has **never fired once**. The
wiki just quietly stops updating. Nothing errors anywhere the user would look.

The signal is `last_run_at: null` / `last_status: null`. That is NOT
"the job is fine, waiting for its first run" if the job is old — it means it
never executed.

```bash
python3 -c "
import json; d=json.load(open('$HOME/cron/jobs.json'))
for j in d['jobs']:
    print(j['name'], '|', j['schedule_display'], '| enabled', j['enabled'],
          '| last_run', j['last_run_at'], '| status', j['last_status'])
"
```

Or `cronjob(action='list')`. **`last_run` is the only field that proves the job
works.** `enabled: true` proves nothing.

Before trusting any schedule, force one run and confirm it:

```
cronjob(action='run', job_id='<id>')      # trigger immediately
# wait ~30-45s, then re-read last_run_at / last_status
```

`last_status: ok` after a forced run is the proof that the wiring works. Do
this at least once whenever you set up or inherit a sync job, and re-check
after any gateway move/restart.

This is distinct from the dead-gateway case above: there the job never even
gets a chance to fire. Here the gateway may be perfectly healthy and the job
still never runs — so **check `last_run_at` specifically**, don't conclude
"the schedule is fine" from a live gateway.

### Prefer one daily slot over hourly for this sync

A portfolio of ~5 projects changes on human timescales. Hourly is noise and
waste; a single daily slot at end-of-day is what the owner actually wants:

```
cronjob(action='update', job_id='<id>', schedule='0 18 * * *',
        name='Asana to Obsidian sync (diario 6pm)')
```

Also keep the on-demand path explicit in the agreement: *"automático a las
6pm, y cuando te diga lo corro al instante."* Owners ask for both — the
schedule for reliability, the manual trigger for confidence. Honor the manual
run immediately when asked; don't just point at the schedule.

### Verify wiki freshness by READING the note, not by trusting the sync

After any Asana write (especially a bulk status update), the wiki is **stale
until the sync runs**. Confirm by reading the actual generated note and
comparing the numbers against Asana:

```bash
python3 asana_obsidian_sync.py --query <PROJECT_GID>   # Asana vs Obsidian, side by side
```

Or read the note and check `## Estado actual` — `Tareas completadas` and
`Tareas abiertas` must match what Asana returned. If the note still says
`completadas | 0` right after you marked 14 done, the sync has not run and the
note is lying.

When you write to Asana and the sync is manual/on-demand, **run the sync in
the same turn** and say plainly that the wiki was stale and is now updated.
Don't leave the owner believing the docs reflect a change they don't yet.

The sync rewrites only the `<!-- HERMES:START -->…<!-- HERMES:END -->` block;
`## Notas humanas` survives untouched. Good output looks like
`A ACTUALIZAR: 1 / SIN CAMBIOS: 4` — the untouched projects being "sin cambios"
is correct and expected, not a failure.

## ⚠️ Scripts live in TWO places and drift

The operational scripts exist in **both** locations, and they are **not**
symlinked or synced:

| Location | Purpose |
|---|---|
| `~/.hermes/profiles/<profile>/scripts/` | What actually runs (cron, manual invocations) |
| `skills/productivity/asana-obsidian-llm-wiki/scripts/` | What ships with the skill |

Verified state (2026-09-17): the skill carried 4 of the 8 scripts
(`asana_test_connection`, `check_telegram_conflicts`,
`mark_completed_from_notes`, `asana_bulk_status`). The profile carried all 8
plus `asana_obsidian_sync.py`, `close_task.py`, `project_detail.py`,
`weekly_onepager.py` — **the engine itself was not in the skill.**

Consequences to state plainly rather than paper over:

- Another agent loading the skill gets references to scripts it does not have.
- Editing one copy leaves the other stale with no signal.
- The two copies of the *same* script can diverge in behaviour.

**The owner notices this and asks about it.** He cross-references the file list
in `SKILL.md` against the actual folder and reports what is missing. Treat
"referenced but absent" as a real defect, not as documentation polish — and
when he hands you a list of missing files, verify it against the filesystem
before answering. Do not assume the files are lost; they are usually just in
the other of the two locations.

**When adding a script: put it in the profile `scripts/` for it to run, and
copy it into the skill `scripts/` so the package is complete. Note it in both
`SKILL.md`'s support-file list and here.**

### Locating anything in this stack (recurring request)

The owner asks *"¿dónde está X?"* and *"quiero ver el contenido"* often, about
skills, scripts, and config. Answer with the absolute path **and** the shortest
way to open it, then optionally show content.

```bash
# A script
ls -la /Users/user/.hermes/profiles/<profile>/scripts/<name>.py

# A skill (find by name — NOT search_files; see pm-workflow gotchas)
find /Users/user/.hermes/profiles/<profile> -iname "*<name>*"
hermes skills list | grep <name>
```

Note the scripts carry a stale-looking `mtime` after atomic writes
(`os.replace` preserves nothing useful here) while the content is current —
**check content, not timestamp**, before concluding a file is old. Confirmed
by grepping for a marker unique to the new revision.

## Sync script

`scripts/asana_obsidian_sync.py`:

```bash
python3 asana_obsidian_sync.py --dry-run     # report only (safe default)
python3 asana_obsidian_sync.py --apply       # perform writes
python3 asana_obsidian_sync.py --query GID   # Asana + Obsidian for one project
```

### Invariants it enforces

- **Read-only against Asana** (GET only).
- **Marker-safe**: writes only between `<!-- HERMES:START -->` and
  `<!-- HERMES:END -->`. Everything else is preserved.
- **`## Notas humanas` is never touched** — preserved byte-for-byte.
- **Never deletes** a note.
- **Fails closed**: if Asana is unreachable, it aborts and writes nothing.
- **Dedup** by `asana_gid` (+ `source_hash` for change detection). Renaming a
  project in Asana does not create a duplicate note.
- Name collisions get ` (last6ofgid)` appended rather than overwriting.

### Frontmatter contract

```yaml
---
type: project
source: asana
asana_gid:            # permanent identity — never key on name
asana_url:
workspace:
owner:
status:
start_date:
due_date:
last_synced_at:
source_hash:          # sha256[:16] of the rendered Asana payload
---
```

`source_hash` covers gid/name/dates/archived/owner/status/modified_at plus a
sorted task set. Routine syncs with no real change produce **no write**.

### ⚠️ `completed: false` does NOT mean the work is undone

**This is the single most expensive misread in this workflow.** Portfolios
here were seeded by an **MS Project import**, and that import writes progress
into the task **notes** as plain text while leaving Asana's native
`completed` flag at `false`:
```
Description: Aprobación ejecutiva del alcance, presupuesto y criterios de éxito.
Start Date: 05/04/2026
Completed: TRUE
Dependents: Definir landing zone objetivo
Status: Completado
Percent Complete: 100
Priority: Alta
```

Treat a board reporting 0/N as **unverified, not as fact.** Before you ever say
"this project is at 0%", "nobody is signing", "stuck since May", or "the
bottleneck is approvals" — cross-check the notes. Getting this wrong once
produced a full portfolio report to the owner that was **completely wrong**
(claimed 3 projects stalled at 0%; reality was 61%, 52%, 38% — all in flight),
and it had to be retracted a turn later.

**The claim you must never make without checking notes:** any statement about
*why* a project is stuck, or that it is stalled at all.

```bash
# Detect the desync — read-only by default, exits silently if nothing to do
python3 scripts/mark_completed_from_notes.py <PROJECT_GID>

# Then apply, one project at a time
python3 scripts/mark_completed_from_notes.py <PROJECT_GID> --apply
```

The script only acts when a note matches `Completed:\s*TRUE` (case-insensitive)
**and** Asana has `completed: false`. Notes explicitly saying `Completed: FALSE`
are left alone, so genuinely open work is never closed by accident. It
re-verifies by re-reading the project after writing.

Also mine these note fields, they carry real state the API does not expose:

- `Status:` — `Bloqueado` / `En curso` / `No iniciado` / `Completado`
- `Percent Complete:` — partial progress on open tasks (e.g. 60)
- `Dependents:` — the dependency edge, so you can spot the critical path
- `Start Date:` — scheduled start, useful vs. the Asana `due_on`

An open task whose note says `Status: Bloqueado` is the **real** blocker in a
portfolio — surface it first. That is the finding worth reporting, not the
raw overdue count.

### Bulk status updates (marking tasks done)

Two different scripts, for two different situations — pick by *why* you are
writing:

| Situation | Script | Selector |
|---|---|---|
| "Board is stale, the work is actually finished" (MS Project import, notes say `Completed: TRUE`) | `mark_completed_from_notes.py` | note content |
| "These are past due and the owner confirmed they're done" | `asana_bulk_status.py` | `due_on < today` |
| "Close *this one* — the owner just said it's done" | `close_task.py` | name substring |

Default to the **notes-driven** script when the project came from an import.
Date-driven selection is the fallback, not the primary path.

#### Closing individual tasks by name

Once the notes-driven pass is exhausted, follow-up closures arrive one or two at
a time by name (*"actualiza Construir agente de análisis documental, ya está
cumplido"*). Use the name-matching script rather than hand-pasting a gid:

```bash
python3 scripts/close_task.py <PROJECT_GID> "análisis documental"          # dry-run
python3 scripts/close_task.py <PROJECT_GID> "análisis documental" --apply
```

It matches case- and accent-insensitively (normalizes `á é í ó ú`), and
**aborts unless exactly one task matches** — that guard is the whole point, since
a loose substring like "documental" can hit several tasks. It says plainly when
the task was already completed, and re-reads the project after writing to report
the new percentage. Prefer 2–4 distinctive words from the task name over the
full string.

### Report what a closure *unblocks*, and flag impossible dependency orders

When the owner closes tasks by name, they are usually working down a chain. Two
things belong in your reply beyond the new percentage:

**1. What it unblocks.** Query the `Dependents:` note field and name the
downstream task now freed. That is the consequential fact — the percentage is
bookkeeping.

**2. An impossible dependency order, if you find one.** Compare note-declared
dependencies against due dates. A real example from this portfolio:

```
Integrar repositorio documental      due 2026-10-09   Status: Bloqueado
  ↳ Dependents: Construir agente de análisis documental   due 2026-09-25
```

The dependent is due **two weeks before its own blocker**. Either the schedule
is wrong or the dependency edge is. Surface it as a finding and ask which —
do not silently "fix" the dates.

When the owner then confirms the blocked item is also done, close it and note
that the dependency edge is now consistent. Being closed out of order is
**normal owner behavior, not an error** — say so in one line and move on rather
than treating it as a defect to correct.

A ready-made script ships with this skill — prefer it over hand-rolling:

```bash
# read-only: what is overdue in a project
python3 scripts/asana_bulk_status.py --project GID --list-overdue

# dry run, then apply
python3 scripts/asana_bulk_status.py --project GID --complete-overdue
python3 scripts/asana_bulk_status.py --project GID --complete-overdue --apply

# every open task, not just overdue
python3 scripts/asana_bulk_status.py --project GID --complete-all-open --apply
```

It does enumerate → print targets → write → **re-verify**, and exits non-zero
if anything is still overdue.

The common real-world order is *"these are actually finished, the board is just
stale — mark them done."* Do it via REST, not the MCP write tools (fewer moving
parts, and the MCP write path is all-or-nothing incl. delete).

```python
# 1. ENUMERATE — read the project, filter, and PRINT the target list first
open_t   = [t for t in tasks if not t["completed"]]
targets  = [t for t in open_t if t.get("due_on") and t["due_on"] < TODAY]
# 2. CONFIRM   — show count + names to the owner before any write
# 3. WRITE     — PUT completed:true, one call per task, collect failures
# 4. VERIFY    — re-read the project; assert overdue == 0
```

Step 4 is not optional. A `PUT` returning `completed: True` is the API echoing
your input back, not proof of persistence. Re-read and count.

Always disambiguate scope before a bulk write: *"todas las vencidas"* vs *"todas
las 24"* are different sets. `Solo las N vencidas` is the safer default — do
that, then offer the remainder rather than assuming the broader set.

**But don't let disambiguation become friction.** State the scope you are
executing in one line, then DO IT — don't stop and wait for a reply:

> *"Voy con las 14 vencidas. Si quieres las 24, me dices y sigo con las otras 10."*

Julio reads a confirm-only question as being slowed down. The rule is
**default + proceed + offer the remainder**, not **ask and halt**. Only halt if
the action is destructive (delete, archive, overwrite) — marking work that the
owner has confirmed as finished is not destructive.

When the owner says *"it's done, they just didn't update it"*, that is
authorization. Execute, then verify, then report the numbers. Do not re-ask.

### Don't argue semantics when the owner gives an instruction

If the owner says *"actualiza todas a done"*, the intent is unambiguous — mark
them completed. A lecture about "Asana has no 'actualizar' status, only
`completed: true/false`" is noise that reads as obstruction.

One short clarifying line is fine *only* when it changes what you execute
(scope: which set). Otherwise translate the instruction into the API call and
run it. Julio's standing rule: **problem + concrete alternative, immediately.**

### Disclose the irreversibility once, briefly, then proceed

A bulk `completed: true` is reversible, but it does change what the portfolio
reports. One line of framing is honest and sufficient:

> *"Marcar done va a reportar Zero Trust como avanzado. Si el programa ya no
> va, lo correcto es archivar, no marcar hecho — dime si es el caso."*

Say it once, then do what was asked. Repeating the caveat across turns is what
earns the *"no te compliques"* correction.

Scale note: ~14 tasks took ~11s (sequential). Beyond ~50, keep it in one script
run but expect ~1s/task.

### If the Asana MCP tools return `{"error":"Not Found"}`

Every `mcp_asana_*` read can fail this way while the token is perfectly good.
It is a server-side resolution problem, not a credential problem — do **not**
re-verify the PAT or ask the owner for a new one.

Fall back to REST immediately. Same token, same workspace, and the whole
enumerate → confirm → write → verify loop works:

```python
import json, urllib.request
# Parse the .env FILE directly (never os.environ — see Pitfalls)
H = {"Authorization": f"Bearer {env['ASANA_ACCESS_TOKEN']}",
     "Content-Type": "application/json"}
req = urllib.request.Request(f"https://app.asana.com/api/1.0/projects/{gid}/tasks"
                             "?limit=100&opt_fields=name,completed,due_on",
                             headers=H)
```

REST is the reliable path for reads and writes; treat the MCP server as a
convenience layer. Paginate with `next_page.offset`.

### The workspace gid is in the project permalink

Project URLs are `https://app.asana.com/1/<WORKSPACE_GID>/project/<PROJECT_GID>`.
If `search_projects` fails or you need the workspace id, it is already sitting
in any task permalink you have — no extra API call needed.

## ⚠️ Read the references BEFORE reporting, not after

**This skill's own reference files have already contained the fix for mistakes
that were then made anyway** — because only `SKILL.md` was read.

The concrete case: `references/pm-reporting.md` carried, in bold, a warning
that a board showing `0/N` must not be narrated as stalled until the task
**notes** are checked (MS Project import pattern). A session read the summary
`SKILL.md`, skipped the reference, saw `23 tareas / 23 abiertas` in a dry-run,
and delivered a confident "111 tareas abiertas, 0 completadas, deuda acumulada
de meses, Asana abandonado" report. The real figures were ~58% complete and in
flight. The owner had to be corrected twice in one session.

**Rule: before any status/health/progress report, load the references that
govern it.** Minimally:

| About to... | Read first |
|---|---|
| Report progress, %, overdue, "how is X going" | `references/pm-reporting.md` |
| Handle a token, a secret, or a credential screen | `references/credential-handling.md` |
| Enable write/delete permissions | `references/permission-escalation.md` |
| Stand this up on a new profile | `references/runbook-asana-obsidian.md` |

Two mechanical habits that prevent the repeat:

1. **Run the reconciliation probe before forming any sentence about state.**
   `mark_completed_from_notes.py <GID>` is read-only and exits in a second. Its
   output — "ya completed en Asana: 14 / Candidatas: 0" — is what tells you
   whether a board is stale or genuinely behind. Do this *before* the report
   exists, not after being challenged.
2. **Never let a dry-run summary line be the source of a number you report.**
   The sync's `N tareas / M abiertas` line is a planning hint, not a
   measurement. Measure with the REST read or the note's `## Estado actual`,
   which are the values that get persisted.

Corollary for any summary counter: if a count and the underlying data disagree,
the count is wrong until proven otherwise — check the code that builds it
rather than trusting the label.

## Pitfalls

- **Token key name is `ASANA_ACCESS_TOKEN`, not `ASANA_PAT`.** Guessing
  `ASANA_PAT` raises `KeyError` mid-script. Dump the actual Asana-related keys
  first (`[k for k in env if 'ASANA' in k.upper()]`) instead of guessing —
  cheaper than a failed run.
- **Read `.env` directly, never via `os.environ`.** `security.redact_secrets`
  is on by default in Hermes. It masks secret values in tool output, so an
  exported `ASANA_ACCESS_TOKEN` can read back as `***` or empty *while the
  file itself holds a perfectly good 68-char token*. A `load_env()` that does
  `os.environ.get(...)` — or that only writes to `os.environ` when the key is
  absent — will report a valid token as MISSING and send you chasing a
  phantom. Parse the `.env` file into a local dict and read from that.
  Symptom: `len(token) == 0` but `awk 'NR==N'` on the same line shows 60+
  chars. That discrepancy IS the redactor, not corruption.
- **The redactor also rewrites your shell commands.** Interpolating the
  variable name inside a one-liner can produce
  `SyntaxError: expression cannot contain assignment`. Write a small script
  file and run that instead of fighting inline quoting.
- **`load_env()` must read the `.env` file directly**, not via `os.environ`.
  Prefer an explicit file read over `os.environ.get()` so masking can't
  produce a false "token missing".
- **`${VAR}` in `mcp_servers.<name>.env` resolves from `os.environ`.** Hermes
  loads the profile `.env` into the environment before spawning MCP servers,
  so this works — verify with `hermes mcp test <name>` rather than assuming.
- **`READ_ONLY_MODE` silently drops write tools.** Confirmed: `true` → 18 tools,
  all read-only; `asana_create_task` / `asana_update_task` / `asana_delete_task`
  are absent from the list entirely. That's the flag working, not a broken
  install. Flip to `false` to get all 41 tools (verified: 4 write functions
  appear). The mode change requires a **restart** of Hermes to take effect.
- **The Asana MCP server has NO granular permissions.** It's all-or-nothing:
  18 read-only tools or 41 with full write+delete. There is no "write but no
  delete" setting. Any restriction on deletion must be enforced **by process
  and convention**, not by server config — which is why the protocol document
  carries the deletion policy rather than the MCP env.
- **The sync script must stay GET-only even after writes are enabled.** Keep
  writes in the MCP tools; keep the sync read-only. Mixing them means a sync
  bug can mutate Asana.
- **When a task is deleted, log it before the next sync.** The next sync will
  simply not return it, and the note silently loses the line. Use
  `--record-deletion <project_gid> --task-name "X" --task-gid NNN --apply`
  to append `- Tarea «X» eliminada el YYYY-MM-DD (gid NNN)` to
  `## Cambios recientes` inside the Hermes block.
- **When editing notes with ad-hoc scripts, NEVER strip the HERMES markers.**
  A careless `re.sub(r"(## Cambios recientes\n)\n+", ...)` across the whole
  file can eat `<!-- HERMES:END -->`. Always assert
  `count(START) == count(END) == 1` after any manual edit, and re-run the
  sync to regenerate a canonical block if it breaks.
- **`write_index` must tolerate `skip` items** — early versions crashed with
  `KeyError: 'tasks'` because only create/update carried task lists.
- **Don't persist internal fields.** `_title` is used for rendering; the
  frontmatter renderer must skip keys starting with `_`.
- **Asana names use underscores** (`Programa_Zero_Trust`). Normalize to
  spaces for the H1 and filename, but keep `asana_gid` as the true identity.
- **Shell `HOME` is the profile dir.** In a Hermes session, `$HOME` is
  `~/.hermes/profiles/<name>/home`, so `~/...` paths and `hermes` on `PATH`
  resolve wrong. Use absolute `/Users/<user>/...` paths. The binary is at
  `<hermes-root>/venv/bin/hermes` — `export PATH` to it first.
- **macOS has no `timeout`.** Use `npm install` directly instead.
- **Google Drive + Obsidian is fragile.** Drive's sync client and concurrent
  writes can conflict. The script uses `os.replace()` (atomic) to minimize the
  window, but if conflicts appear, move the vault local and sync differently.
- **Never write secrets into the vault.** The token lives only in `.env`.
- **Recording an action ≠ authorization to perform it.** Writing "we could
  update Asana" is not permission to write to Asana.
- **A GID handed to you is probably the wrong object.** Users say "ID del
  cliente" / "ID del proyecto" for what the API needs as a *workspace* gid.
  Don't ask for gids at all — `/workspaces` resolves it from the token. If a
  stray gid arrives, resolve it (`/projects/<gid>`) rather than guessing.
- **Don't conflate adjacent systems the owner mentioned historically.** This
  profile carries a stale `LINEAR_API_KEY` from an earlier era with no Linear
  MCP configured. Recalling "their PM tool is Linear" and proposing to "cross-
  reference Asana with Linear" invents a fourth system inside a two-source
  architecture (Asana + Obsidian) and confuses the user about which data means
  what. Check what is *actually configured today* (`hermes mcp list`, grep the
  profile `.env`) before referencing any tool by memory.

## Verification

```bash
# 0. Token + workspace (run this FIRST, always)
python3 scripts/asana_test_connection.py

# MCP registered + reachable (NOT just "enabled" — this actually connects)
hermes mcp test asana

# Gateway live — use the reliable signals, not `gateway status` alone
launchctl list | grep hermes        # macOS: real PID, status 0
hermes cron status

# Sync dry-run
python3 scripts/asana_obsidian_sync.py --dry-run

# Vault intact + note structure
ls "$OBSIDIAN_VAULT_PATH"
```

Marker integrity check (catches a truncated block):

```bash
grep -rc "HERMES:START" "$V/02 Projects" | grep -v ":1"
```

Every note should have exactly 1 START and 1 END.

## Bundled support files

- `scripts/asana_test_connection.py` — credential + connectivity probe.
  Validates the PAT by calling `/users/me`, lists workspaces with gids.
  Never prints the token. **Run this before any other diagnosis.**
- `scripts/asana_bulk_status.py` — enumerate/confirm/write/verify bulk status
  updates over plain REST. Works even when the Asana MCP tools return
  `Not Found`. Dry-run by default; re-reads after writing and fails loudly if
  anything is still overdue.
- `scripts/mark_completed_from_notes.py` — reconciles a board that reports
  0/N while the tasks' **notes** say `Completed: TRUE` (MS Project import
  pattern). Notes-driven selection, so genuinely open work is never closed.
  **Run this before making any "the project is stalled" claim.**
- `scripts/close_task.py` — closes a single task matched by name substring
  (accent-insensitive), refusing unless exactly one task matches. Dry-run by
  default; re-reads the project after writing to report the new percentage.
- `scripts/project_detail.py` — full single-project dump: sections, every open
  task with its note fields, and overdue age in days. This is the read that
  exposes dependency edges and impossible schedules — run it when the owner
  says *"revisemos <proyecto>"*, before answering anything about focus.
- `scripts/weekly_onepager.py` — portfolio rollup: per-project %, overdue count,
  and tasks due inside the current week.
- `scripts/check_telegram_conflicts.py` — fingerprints `TELEGRAM_BOT_TOKEN`
  across the root profile and every named profile; names any set sharing one
  token (the cause of silent gateway restart loops). Run during onboarding.
- `scripts/asana_obsidian_sync.py` — **the engine.** Marker-safe note
  generation, incremental dedup by `asana_gid` + `source_hash`, index
  generation, `--record-deletion`. ⚠️ Currently lives only in the profile's
  `scripts/`; copy it into the skill when packaging for another agent.

⚠️ **Four more scripts exist only in the profile** and are referenced
throughout this file — `close_task.py`, `project_detail.py`,
`weekly_onepager.py`, `asana_obsidian_sync.py`. They run fine; they are just
not in the shipped package yet. See "Scripts live in TWO places and drift".

⚠️ **A NEWER engine exists in the owner's `pm-obsidian-agent` repo** (34 KB vs
the 27 KB local one). It adds `task_is_done` + `reconcile_tasks`, which resolve
`Completed: TRUE` from task **notes** during the sync itself — making the
`0/N stale board` bug structurally impossible instead of relying on someone
remembering to run `mark_completed_from_notes.py` first. It also writes
`tasks_total/done/blocked`, `next_due`, `critical_blocker`, and the `programa`
up-link into the frontmatter, and feeds the reconciled state into `source_hash`
(so editing a note to `Completed: TRUE` triggers a re-render). **Diff function
names before migrating, and test on a throwaway vault** — it changes the
frontmatter schema, so existing notes render empty in any Base that filters on
the new fields. Full migration guidance: `references/skill-packaging-qa.md`.

⚠️ **`project_detail.py` and `weekly_onepager.py` hardcode `today`** as a
literal date (`today = datetime.date(2026, 9, 17)`). Past that date their
overdue and "this week" calculations are wrong. Use them for structure
(sections, note fields, dependency edges), not for date arithmetic — or fix
them to `date.today()` before relying on the date-derived output.
- `references/credential-handling.md` — paste-back protocol, what to do when
  the user pastes a secret into chat anyway, the escalation ladder for
  "user can't find the right screen", and the agent's own
  verify-before-asserting rule.
- `references/pm-reporting.md` — the recurring PM questions (progress %,
  what's left, what to focus on this month) and how to answer each from one
  REST read; critical-path ranking; posting focus comments via
  `/tasks/<gid>/stories`; and the reporting shape the owner actually wants.
  **Read this before answering any "how is X going" question** — it carries the
  board-staleness trap that has already caused one fully retracted report.
- `references/runbook-asana-obsidian.md` — the end-to-end build sequence for
  standing this integration up on a *new* profile, in Spanish, with the
  verification for each step and the real failures marked inline. Use it when
  replicating; use SKILL.md for operating an existing install.
- `references/permission-escalation.md` — how to handle an owner asking to
  enable destructive capabilities (delete/archive) on the Asana side: the
  pushback, the legitimate counter-argument, and the governance pattern that
  resolves it without either stonewalling or granting a blank cheque.
- `references/obsidian-bases.md` — building `.base` files: native Obsidian
  tables/cards computed from the wiki frontmatter (no scripts, no embeddings).
  Includes the four-point pre-flight validation, the Duration and
  undefined-formula traps, and the version check. Use this when the owner
  wants to *see the portfolio himself* rather than ask the agent.
- `references/skill-packaging-qa.md` — auditing and shipping this skill set as
  a **package for other people**: the completeness check (folder vs. what
  SKILL.md promises), which of the owner's several local copies was published,
  hardcoded paths and dates that break on another machine, the Asana-tier
  assumption behind `programa`, the clean-install dry-run, and the
  migration-vs-rebuild answer. **Read this when he frames the work as testing
  a standard, distributable skill** rather than building his own vault.

## Replicating this for a new agent

Order matters; steps 4 and 6 are the ones people skip and then lose days to:

1. `hermes profile create <name>`
2. **New bot** in @BotFather → token unique to that profile
3. Token into that profile's `.env`
4. `python3 scripts/check_telegram_conflicts.py` — verify BEFORE starting
5. `hermes gateway install`
6. `launchctl list | grep hermes` — confirm a real PID (not just "loaded")
7. Only now: MCP servers, cron jobs, skills

`TELEGRAM_BOT_TOKEN` must be unique per profile. `TELEGRAM_HOME_CHANNEL` and
`TELEGRAM_ALLOWED_USERS` are the owner's ids and are intentionally identical
everywhere — do not "fix" them when creating a new bot.
