# PM reporting over Asana — recurring request shapes

Julio asks these in near-identical form across sessions. Each has a fast,
deterministic answer computed from the same REST read. Don't hand-wave or
narrate — compute, then lead with the number.

## The one read that answers most of them

```python
tasks = project_tasks(gid)          # paginate, opt_fields=name,completed,due_on,assignee.name
open_t  = [t for t in tasks if not t["completed"]]
overdue = [t for t in open_t if t.get("due_on") and t["due_on"] < today]
```

Nothing else is needed for: progress %, overdue list, remaining list, critical
focus. Fetch once, compute all derived views locally — never re-hit the API per
question.

## "¿Cuál es el porcentaje de avance?"

```
progress = done / total * 100
```

Report the raw counts alongside it (`14 de 24 tareas`), because the percentage
alone hides how small the denominator is. A 58% on 24 tasks is not the same
signal as 58% on 240.

Use `--query <GID>` on the sync script if you also want the Asana-side vs
Obsidian-side numbers in one shot.

## "¿Qué tareas faltan?"

List the open tasks **ordered by due date**, grouped by date bucket, with the
nearest deadline flagged. Include the overdue ones if any remain — a "what's
left" answer that silently drops overdue work is misleading.

## "Revisemos <proyecto>" — the deep dive

This is the highest-value request shape because it is where the real findings
live. It is **not** just "list the tasks". Run the detail script and read the
note fields on every task:

```bash
python3 scripts/project_detail.py <PROJECT_GID>
```

It prints sections, then every open task ordered by date with its note fields
and overdue age. From that output you can derive four things the API never
exposes directly — lead your report with these, not with the task list:

1. **The real blocker.** An open task whose note says `Status: Bloqueado` is the
   actual constraint in the project. One such task outranks a long overdue list.
2. **The critical path.** Follow `Dependents:` forward from the blocker. State
   the chain and what falls if the head isn't resolved: *"latency blocks ola 3 →
   pruebas integrales → go-live → cutover → hypercare → cierre"*.
3. **Flagged risk.** `Status: En riesgo` on a near-term task is an early warning
   the owner has already recorded — repeat it back.
4. **The true end date.** The latest `due_on`, not today's overdue count. A
   project whose last task is 13 Nov is *in flight and on schedule*, not
   failing. This single fact overturned a wrong "it's stalled" read.

Also report the **section breakdown** (e.g. `Gobierno y planificación: 4`,
`Migración por olas: 5`). It shows the project's shape — where the work sits —
which is what the owner means by "revisemos".

### The "it's stalled" trap, restated

The detail dump is also the safety net. If every task's note says
`Completed: TRUE` while Asana reports `0/23`, you are looking at a stale board,
not a dead project — reconcile with `mark_completed_from_notes.py --apply`
before reporting anything. See the warning in the previous section. The
`project_detail.py` output makes this obvious because it prints the note text
right next to the task name; a summary that only counts `completed` hides it.

## "¿En qué nos enfocamos el siguiente mes?"

Month-scoped focus is a different computation from "this week". Look at the
**next** month's due dates across all projects and group by week, because the
useful finding is usually **collision**:

> 2 Oct — 6 tasks due the same day across 3 projects.

A pile-up like that is the real risk-of-the-month. Name it, name the projects,
and say it needs sequencing and owners *before* the date arrives rather than on
the day. Bundle it with:

- The **blocker** that gates the whole month (if unresolved by week 1, the
  cascade behind it dies).
- The **Go/No-Go decisions** falling in the window — these are the only tasks
  that genuinely need the owner personally.
- The **closing dates** per project, so the month reads as a runway to
  something rather than a list.

If the month runs clean, say what closes and when — *"if October lands, three
programs close in November"*. That is the sentence the owner is looking for.


The useful answer is critical-path, not just "soonest due". Rank by:

1. **Chain length** — how many later tasks depend on this one. A task blocking
   five downstream items outranks one due sooner that blocks nothing.
2. **Dates inside the current window** — this month only; park the rest.
3. **Approval/decision tasks** — *only if verified.* See the warning immediately
   below: an unverified approval-bottleneck narrative produced a fully wrong
   report to the owner. Check the notes first, then claim it.

Say explicitly which ones you would **discard** for the month and why. An
honest "these three matter, these two can wait" is worth more than a list of
ten ranked items.

### ⛔ Do NOT lead with "it's an unsigned-decision problem" — verify first

An earlier version of this file asserted, as a standing portfolio finding, that
*"every project stalls at the same point: the first approval task stays open
for months... it is an unsigned-decision problem."* **That was wrong and it
produced a fully incorrect report to the owner.**

What actually happened: the board was an **MS Project import**. The tasks were
finished, with `Completed: TRUE` / `Status: Completado` written in their
**notes**, while Asana's native `completed` flag stayed `false`. So the board
reported 0/N on projects that were really at 61%, 52% and 38% — all in flight
and on schedule. The "nobody is signing" narrative was an artifact of trusting
one boolean.

Before any claim that work is stalled, blocked, or that decisions are the
bottleneck:

```bash
python3 scripts/mark_completed_from_notes.py <PROJECT_GID>   # dry-run
```

If it reports candidates, the board is stale — reconcile it, then re-derive
every number. **Never narrate a cause ("nobody signs", "capacity problem")
from an overdue count alone.** Overdue + `completed: false` is consistent with
both "genuinely stuck" and "finished but never ticked". Only the notes tell
you which.

What survives as a real observation: **0 of ~96 tasks have an assignee.** No
owner means no closed loop — that one is verifiable from the API and worth
stating. The stalled-decisions claim is not.

### Report corrections the moment you find them

If a number you already sent turns out to be wrong, open the next message with
the correction and the new number — don't bury it after the fresh findings.
Julio got a whole portfolio report retracted this way, and the honest reversal is
what preserved trust. Say plainly what you got wrong and why ("trusted the
`completed` flag without reading the notes"), then give the corrected table.

## Posting a focus plan as task comments

Owners often want the focus written back into Asana so it's visible to whoever
opens the task. Use the stories endpoint — one call per task, plain text:

```python
body = json.dumps({"data": {"text": txt}}).encode()
req = urllib.request.Request(f"{API}/tasks/{gid}/stories",
                             data=body, headers=H, method="POST")
```

Write the comment as: `FOCO <MES> — <prioridad>. Vence <fecha>. <why it
matters / what it unblocks>.` Name the downstream tasks it unlocks — that is
what makes it actionable rather than a restatement of the due date.

Verify each returned `data.gid` (that's the story id) and report the count
written. Do not comment on tasks you just marked complete — they are already
closed; put focus on the **open** work.

## "Haz un one pager: solo lo crítico de la semana + next steps"

A fixed shape that works. Build it from one portfolio read, then write it to
`workspace/onepager-YYYY-MM-DD.md` so it can be re-sent or attached.

1. **Header line** — projects, total tasks, global %, open count, overdue count.
2. **🔴 CRÍTICO DE LA SEMANA** — only tasks due inside the current week
   (today → next Monday). Name the exact date. State if none have an owner.
3. **📊 ESTADO POR PROYECTO** — one block each: `name — pct (done/total)`, then
   overdue count, then the single blocking task with its age in days.
   Mark the healthy one explicitly (✅ the only one advancing) so the contrast
   is legible at a glance.
4. **⚠️ EL PATRÓN** — the cross-project observation. After verification this is
   usually *"N of M have no assignee"* or a shared dependency. Do not invent a
   narrative cause here (see the warning above).
5. **✅ NEXT STEPS** — numbered, each with a date and an owner-or-"assign one".
   Separate *this week* from *this month* from *process fix*.
6. **🎯 LA DECISIÓN QUE PIDE ESTA SEMANA** — end on the one question only the
   owner can answer (e.g. "are these real or inventory?"). One pager, one
   decision.

Keep it to a screen and a half. Telegram renders tables badly — use bullets
and `key: value` lines, never pipe tables.

## "Actualiza la wiki" / "¿está actualizada mi base de conocimiento?"

Answer by **reading a generated note and comparing numbers to Asana**, never by
trusting that the sync ran. Then check the cron's `last_run_at` — an enabled
job that has never fired is the usual root cause, and the wiki looks fine while
being frozen.

After any Asana write, run the sync in the same turn and say the wiki was stale
and is now current. See the "Verify wiki freshness" section in SKILL.md.

## Reporting shape that works

Lead with the headline number. Then a short grouped list. Then **one**
recommendation with a concrete next action. Julio does not want a tour of the
data — he wants the decision. Keep it under a screen; use bullets over tables
(Telegram renders tables poorly, and bullet lists read faster on mobile).

Avoid: restating what the data obviously says, hedging, multiple competing
recommendations, or technical caveats about the API.
