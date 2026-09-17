# Credential handling for Asana integrations

Distilled from a session where the user pasted credentials into chat **four
times** across several rounds, and the agent had to steer each one without
using any of them.

## The core rule

**Never accept a secret through the chat channel.** The user pastes it, the
agent configures the rest. The value should travel user → file, never
user → chat → agent → file.

Steps to give the user (copy verbatim):

1. Generate the token in the provider's UI.
2. Open the config file yourself:
   `/Users/<user>/.hermes/profiles/<profile>/.env`
3. Paste the value after the `=` on the existing key line.
4. Save the file.
5. Reply **"listo"** — with no value in the message.

Then verify by *reading the file and calling the API*, not by asking them to
repeat the token.

## When they paste it anyway

Do **not** use it. Do **not** echo it back. Say three things, in this order:

1. **It's compromised** — anything through chat is burned and must be rotated,
   even if it still works.
2. **Rotate it** — concrete instruction to revoke in the provider UI.
3. **The next one goes in the file** — restate the paste-back steps.

Then continue with the task using the file-based flow. If they push back
("estamos en prueba, pon ese que te di"), hold the line: a leaked token is
dead regardless of environment, and pasting it into `.env` just moves the
problem. Offer a *different* path forward (guided navigation, screenshot
review, simulated data) rather than repeating the refusal.

## Escalation ladder

When the user cannot find the right credential screen, escalate in this order:

| Rung | Offer | Cost to user |
|---|---|---|
| 1 | Exact URL + section name | lowest |
| 2 | "Send me a screenshot — the file path, not the content" | low |
| 3 | Open the provider in the agent's browser and point at the button | medium (login) |
| 4 | Proceed with simulated data; wire the real token later | none now |

Stop escalating if the agent's browser lands on a login wall — the agent has
no session and must not ask for the user's provider password. Drop to rung 2.

## Distinguishing credential types (Asana specifically)

The user repeatedly named things wrongly. Don't echo their terminology —
identify by *where it came from*:

- **Client ID + Client Secret** → from the developer *app* screen → OAuth only.
- **Personal Access Token** → from `developer-console` → what
  `ASANA_ACCESS_TOKEN` needs.

But per Asana's docs, **do not infer the type from the string's shape**.
Tokens are opaque and formats change. Test by calling `/users/me`.

## Rotation checklist to hand the user

- [ ] Revoke every credential that appeared in chat.
- [ ] Generate a fresh PAT.
- [ ] Paste it into `.env` only.
- [ ] Confirm the old ones no longer work.

The agent cannot do any of this — it's provider-side. Say so plainly instead
of implying the agent will "clean it up".

## The agent's own failure mode during this session

Two separate rounds were burned because the agent **deduced a state instead of
testing it**, then reported the deduction as fact:

| Claimed | Reality | Cost |
|---|---|---|
| "That's not a PAT, the `2/` prefix is wrong" | It WAS the PAT | ~3 rounds of the user re-pasting |
| "The MCP is broken / won't connect" | It connected fine (`hermes mcp test asana`) | Told the user a working system was down |

Both times the correct action was one command away. The rule:

**Run the probe before forming the sentence.** For this integration the probes
are: `scripts/asana_test_connection.py` (credentials), `hermes mcp test asana`
(MCP transport + tool list), `launchctl list | grep hermes` (gateway alive).
Assert nothing until one of those has produced output.

This matters more than usual with this user: they get impatient when the agent
stops them with a guess. A wrong "it's broken" is doubly expensive — it costs
rounds *and* it makes the agent look unreliable about the system it just built.

## Don't let the user's vocabulary redraw the architecture

The user says "ID del cliente" for a project gid, "credenciales" for a mixed
bag of app secrets, and mentions Linear because it's in their history. Mirror
their words back for rapport, but **never let them become a new component in
the design**.

Concretely, this session produced a bad proposal — "let me cross-reference the
Asana numbers with Linear" — because memory said their PM tool was Linear. The
stated architecture is two sources (Asana operational, Obsidian documental).
Linear had no MCP configured, only a stale `LINEAR_API_KEY` in `.env`.

When tempted to bring in an adjacent system: check `hermes mcp list` and the
profile `.env` first. If it isn't wired up today, it isn't part of the design.
Ask "is X still live for you, or is it legacy?" rather than assuming either way.
