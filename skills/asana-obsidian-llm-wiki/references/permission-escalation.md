# Enabling destructive permissions on an integration

Distilled from a session where the owner asked to turn on full write access to
Asana — **including delete** — on an integration that had been built read-only
that same day.

This is a recurring shape: the read-only phase proves the wiring, then the owner
wants to actually *act* through the agent. How you handle that request decides
whether the system stays trustworthy.

## The shape of the request

It arrives in escalating forms. Expect all of them:

1. *"activa los límites"* — ambiguous; could mean "set sensible limits" or
   "turn on everything."
2. *"todo, incluso borrar"* — after being offered a menu of scopes.
3. *"si necesito que borres y si es así actualizas en obsidian que se ha
   borrado"* — **the good argument.** See below.

Form 3 is the one to pay attention to; it is not a demand, it is a design
objection.

## The three things NOT to do

**Do not silently comply.** The MCP server is all-or-nothing — there is no
"write but no delete" switch (18 read-only tools vs 41 including
`asana_delete_task`). Granting the request *is* granting irreversible deletion.

**Do not stonewall.** A flat "I won't do that" with no path forward reads as
obstruction and earns the *"no te compliques"* correction. The owner has a
legitimate need; refusing the need is not the job.

**Do not lecture.** One or two lines of framing is honest. A paragraph on the
asymmetry of irreversible operations is noise. Say it once.

## The legitimate counter-argument (form 3) — and why it wins

The owner's point: *if the protocol says nothing may ever be deleted, and
deletion is sometimes genuinely needed, then the protocol is wrong — and worse,
if something IS deleted and the wiki still lists it, the wiki is lying.*

That is correct. **A protocol that describes an aspiration instead of the
operational reality will be violated and then quietly ignored.** The fix is not
to forbid the operation; it is to **govern** it and **record** it.

So: agree with the substance, then change *how* it is registered rather than
whether it is permitted.

## The pattern that resolves it

**Grant the capability, govern it by process, and make every use leave a trace.**

1. **Write the policy into the protocol document BEFORE flipping the switch.**
   The order matters — protocol first, then permissions. Flipping first and
   documenting later means the system briefly contradicts its own spec.

2. **The policy itself** (adapt wording, but keep the structure):

   - No deletion on the agent's own initiative, ever — not in bulk, not because
     a sync detected something.
   - The owner requests it, naming the specific item.
   - The agent **proposes archiving first** — archiving is reversible, deleting
     is not. Asana has no trash: `asana_delete_task` is described by Asana
     itself as *"permanently removes the task."*
   - If the owner confirms, execute **that one item only**.
   - **In the same step**, update the wiki (see below).
   - Never a silent deletion.

3. **How the wiki reflects a deletion** — the owner's own choice, offered as
   options:

   | Option | Behaviour |
   |---|---|
   | **A (chosen)** | Remove the line from the active list; record `- Tarea «X» eliminada el YYYY-MM-DD (gid NNN)` in `## Cambios recientes` |
   | B | Strike it in place: `~Tarea X~ — eliminada YYYY-MM-DD` |
   | C | Remove with no trace |

   Option A wins because the active list must mirror Asana *today* (otherwise
   the wiki lies), while the second-brain purpose requires keeping the trace.
   The `gid` in the record is what makes it auditable later.

   **A deleted project never deletes its note.** Keep the note with
   `status: deleted` + `deleted_at` in the frontmatter and the Hermes block
   updated. The vault is a record; notes are never removed from it.

4. **Document the mode change with its date** inside the protocol, so a future
   reader can tell when the surface changed and why.

## Enforcement lives in the tools, not in resolve

A promise to "be careful" is not a control. Give the owner something runnable:

```bash
python3 asana_obsidian_sync.py --record-deletion <project_gid> \
    --task-name "Nombre" --task-gid NNN            # dry-run: prints the line
python3 asana_obsidian_sync.py --record-deletion <project_gid> \
    --task-name "Nombre" --task-gid NNN --apply
```

Dry-run by default so the exact line is shown before anything is written.
Refuses if the note has no `HERMES:START/END` pair — never writes into a
malformed block.

**Keep the sync script GET-only regardless.** Writes go through the MCP tools
or dedicated REST scripts. If the sync can mutate Asana, a sync bug becomes a
data-loss bug.

## Say the boundary out loud, once

The line that carries the whole policy:

> **Registrar una acción ≠ autorización para ejecutarla.**
> Reporting "there are 14 overdue tasks" is not permission to close them.

Owners reasonably assume a finding implies a mandate. State the opposite
explicitly, then honour it — act only when asked.

## Verify the flag actually changed

A config write is not proof. Confirm the tool surface, then restart:

```bash
hermes mcp test asana      # 18 tools = still read-only; 41 = write enabled
```

The mode change needs a Hermes restart to take effect. Re-count the tools after
the restart rather than assuming the edit landed.

## Checklist

- [ ] Protocol updated with the deletion policy **before** enabling writes
- [ ] Archiving offered as the reversible alternative
- [ ] Deletion requires a per-item, owner-initiated request
- [ ] Wiki-record step defined (option A: remove + trace in `Cambios recientes`)
- [ ] Deleted *projects* keep their note, marked `status: deleted`
- [ ] `--record-deletion` dry-run verified, then applied
- [ ] Sync script still GET-only
- [ ] "Recording an action ≠ authorization" stated explicitly
- [ ] `hermes mcp test` re-counted after the change + restart
- [ ] Mode change date recorded in the protocol
