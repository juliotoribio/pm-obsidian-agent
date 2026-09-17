# Packaging & shipping a skill bundle (QA pass)

When the owner treats a skill set as a **product for other people** rather than
a personal tool, the review standard changes. He stops asking "does it work for
me" and starts asking "does it work for a stranger." Recorded from the
`juliotoribio/pm-obsidian-agent` review (17 sep 2026).

## Trigger

The owner says any of:

- *"estoy probando esto para dejarlo como un skill estándar para cualquiera"*
- *"estoy testeando"*
- links a a public repo (often his own) and says *"toma esto"* / *"olvidemos lo
  anterior y tomes esto"*
- asks how to replicate the setup for future agents

That reframes the job. You are no longer building his vault — you are
**auditing a distributable package**. Say so plainly and switch mode; don't
keep optimizing his local install.

## What to check, in order

### 1. Completeness — does the folder match what SKILL.md promises?

The single highest-value check. The owner does this himself and reports the
gap; do it before he does.

```bash
S="/path/to/skills/<skill-name>"
# every script/filename the SKILL.md mentions
grep -oE "[a-z_]+\.(py|md|sh)" "$S/SKILL.md" | sort -u
# what actually exists
find "$S" -type f | sort
```

Real finding: the repo shipped `asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py`
and **nothing else** — no `SKILL.md`, no references, 9 of 11 files missing. A
script without its SKILL.md is an orphan: an agent finds it and has no idea
when to use it.

### 2. Which copy was published?

The owner keeps **several local copies** of a project. Confirmed state:

```
~/.hermes/profiles/<p>/skills/productivity/<skill>/   11 files  ← complete
~/Documents/DEV/projects/Skills/<proj>/skills/<skill>/   1 file  ← partial
~/Downloads/<proj>/<skill>/                              1 file  ← partial
```

He published the **Downloads** copy — which was both incomplete *and* missing
the `skills/` top-level directory that the `DEV` copy had.

```bash
# find every copy and count files — do this before advising anything
find /Users/user -name "<skill-name>" -type d \
     -not -path "*/venv/*" -not -path "*/.git/*" \
  | while read d; do echo "$(find "$d" -type f | wc -l) $d"; done
```

**Rule: never assume files are lost.** They are almost always in the other
copy. Verify, then say which copy is the good one.

### 3. Hardcoded paths to his machine

These break for every other user. Grep for them:

```bash
grep -rn "/Users/user\|maha_pm_agent\|Julio" "$S" --include="*.py" --include="*.md"
```

Real examples found:

```python
DEFAULT_ENV = os.path.expanduser("~/.hermes/profiles/maha_pm_agent/.env")
```

```bash
cp -R obsidian-pm-context /Users/user/.hermes/skills/
```

The first should resolve the profile from `$HERMES_HOME` or a CLI flag. The
second should document `$HERMES_HOME/skills/` rather than one absolute path.

### 4. Hardcoded dates

```python
today = datetime.date(2026, 9, 17)   # ← freezes the tool
wk_end = datetime.date(2026, 9, 21)
```

Two scripts carried these. Past that date every "overdue" and "this week"
calculation is silently wrong. Must be `date.today()`.

### 5. Committed junk

`.DS_Store` at three levels, including inside the skill directory itself.
Should be gitignored, not committed. Cosmetic but it signals the package was
zipped from a working desktop, not curated.

### 6. Missing README

The repo had no README at the root (the good local copy had one). Without it a
stranger cannot know: requirements, what it does, install steps, what Asana
tier is needed. **Also check the README claims match reality** — a README that
promises scripts the package lacks is worse than no README.

### 7. Third-party dependency assumptions

`obsidian-pm-context` resolves the Programa link from **Asana Portfolios**,
which are tier **Advanced**. Without it, every project lands in a single
`[[Programa General]]` bucket and the grouping feature looks broken:

```
Migracion_Cloud_Hibrida    → [[Programa General]]
Implementacion_ERP_S4HANA  → [[Programa General]]
                          ... all of them
```

A stranger on the free tier sees this and thinks the tool is broken. The
fallback must be **documented and explained in the output**, and the skill
should point at the `programa_manual` escape hatch.

## The clean-install test (the only real proof)

Everything above is static analysis. The actual answer to "does this work for
anyone" is a **dry run on a throwaway vault with a fresh profile**:

```bash
mkdir -p /tmp/vault-test/{02\ Projects,02\ Programas,09\ Vistas,04\ Decisions,99\ System}
cd <skill>/scripts
HOME=/Users/user OBSIDIAN_VAULT_PATH=/tmp/vault-test python3 asana_obsidian_sync.py --dry-run
```

Verify the resulting frontmatter carries the **full schema**, not just the
subset you happened to need:

```
asana_gid  asana_url  workspace  owner  status  start_date  due_date
tasks_total  tasks_done  tasks_blocked  next_due  critical_blocker
programa  last_synced_at  source_hash
```

The `tasks_*` counters are the ones worth checking — see below.

## What the newer package version adds (and why it matters)

If the repo's script is bigger than the installed one, diff the function names
before deciding to migrate:

```bash
grep -oE "^def [a-z_]+" <new>.py | sort > /tmp/new
grep -oE "^def [a-z_]+" <old>.py | sort > /tmp/old
diff /tmp/old /tmp/new
```

The `pm-obsidian-agent` version added 8 functions the local one lacked, and two
of them change behaviour:

| Function | Effect |
|---|---|
| `task_is_done` | Counts a task done if its **note** says `Completed: TRUE`, even when the Asana flag is `false` |
| `reconcile_tasks` | Runs that reconciliation during sync, so `tasks_done` is right in the frontmatter |

**Consequence: it makes the "0/N stale board" bug structurally impossible.**
The frontmatter is correct at write time; nobody has to remember to run
`mark_completed_from_notes.py` first. Verified on the real portfolio:

```
PROYECTO                       TOT  DONE  BLCK AVANCE
Migracion_Cloud_Hibrida         23    14     1    61%
Programa_Zero_Trust             24    14     0    58%
Implementacion_ERP_S4HANA       25    13     0    52%
Plataforma_Agentes_IA           24    12     0    50%
Lanzamiento Pack Manifestación  15     0     0     0%
```

Note it also surfaced a **`tasks_blocked: 1`** with a named
`critical_blocker` — a finding that had never appeared in any prior report.

The others: `parse_task_note`, `resolve_programa`, `build_program_map`,
`fetch_portfolios`, `fetch_me`, `_wikilink`.

## Migration vs. rebuild — how to answer it

He asks *"¿crees que es mejor ponerlo desde cero?"* Answer with the layer
split, not a yes/no:

| Layer | Decision |
|---|---|
| Infrastructure (MCP, gateway, cron, token) | **Keep.** Rebuilding repeats the 6 documented setup failures for zero gain. |
| Skills | **Add** the new ones alongside; don't rewrite the working ones. |
| Sync script | **Replace** with the package version (it fixes the counting bug). |
| Vault notes | **Regenerate** — the frontmatter schema changed. |
| Vault folders | **Add** `02 Programas/`, `09 Vistas/`; don't move existing ones. |

Cost framing that lands: rebuild ≈ hours repeating solved problems; migrate ≈
minutes. Infrastructure and vault schema are **independent layers** — the
schema changed, the plumbing did not.

## Schema migration is a real change — confirm before writing

The new frontmatter adds `tasks_total`, `tasks_done`, `tasks_blocked`,
`next_due`, `critical_blocker`, `programa`. Existing notes lack these, so
Bases that filter on them render empty. **Regenerating the notes is a write to
the owner's vault — get explicit approval first**, and always test against
`/tmp/vault-test` before touching the real one.

Also: the `.base` files change too. `Proyectos.base` (grouped by `status`)
gives way to `00 Portafolio.base` (grouped by `programa`, with a health
formula) plus `09 Vistas/Bloqueados.base`. Don't leave both — they will
contradict each other.

## Reporting shape

Lead with the finding count, then a table, then the fix offer. He wants
*"faltan 9 de 11"* first, not a walkthrough of how you discovered it.

State corrected diagnoses plainly when your own earlier claim was wrong (e.g.
"the files aren't lost, they're in the other copy") — that is the pattern he
responds well to, per `pm-reporting.md`.
