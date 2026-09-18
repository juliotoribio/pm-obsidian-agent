import os
import tempfile
from scripts.generate_status_report import parse_snapshot
with tempfile.NamedTemporaryFile("w", delete=False) as f:
    f.write("""| asana_gid | name | type | status | pct | tasks_total | tasks_done | tasks_blocked | due_date | next_milestone_date | milestones_total | milestones_done | replans | slip | blocker | owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 111 | Proy A | proyecto | rojo | 50 | 10 | 5 | 1 | 2026-10-10 |  | 0 | 0 | 0 | 0 | - | - |
""")
print(parse_snapshot(f.name))
