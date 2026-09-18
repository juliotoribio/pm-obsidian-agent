import unittest
import tempfile
import os
import sys

# Agrega la ruta actual para importar los scripts
sys.path.append(os.path.dirname(__file__))

from generate_status_report import generate_report

class TestReport(unittest.TestCase):
    def test_generate_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            os.makedirs(os.path.join(tmp, "03 Log"))
            
            # Crear nota del proyecto para que scan_existing_notes la encuentre
            with open(os.path.join(tmp, "02 Projects", "P1.md"), "w", encoding="utf-8") as f:
                f.write("""---
type: proyecto
asana_gid: 123
replan_count: 1
slip_days: 5
critical_blocker: "Falta de servidor"
---
# P1
""")

            # Snapshot 1
            snap1 = """# Snapshot: 2026-09-17

| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % |
|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 5 | 0 | 2026-09-20 | 50 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-17.md"), "w") as f:
                f.write(snap1)
                
            # Snapshot 2
            snap2 = """# Snapshot: 2026-09-18

| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % |
|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 5 | 1 | 2026-09-25 | 50 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-18.md"), "w") as f:
                f.write(snap2)
                
            report_path = generate_report(tmp, "2026-09-17", "2026-09-18")
            
            self.assertTrue(os.path.exists(report_path))
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            self.assertIn("Aumentaron tareas bloqueadas", content)
            self.assertIn("Falta de servidor", content)
            self.assertIn("2026-09-20 ➡️ 2026-09-25", content)
            self.assertIn("**Replans**: 1", content)
            self.assertIn("**Slip Days**: 5", content)
            
if __name__ == '__main__':
    unittest.main()
