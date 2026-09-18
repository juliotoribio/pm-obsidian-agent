import unittest
import tempfile
import os
import sys

sys.path.append(os.path.dirname(__file__))
from generate_status_report import generate_report

class TestReportStates(unittest.TestCase):
    def test_semantic_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            os.makedirs(os.path.join(tmp, "03 Log"))

            snap1 = """# Snapshot: 2026-09-17
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % | Replans | Slip Days | Blocker | Filename | Milestones | Milestones Done | Next Milestone Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 2 | 0 | 2026-10-01 | 20 | 0 | 0 | Ninguno listado | P1 | 0 | 0 | |
| 222 | P2 | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P2 | 0 | 0 | |
| 333 | P3 | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P3 | 0 | 0 | |
| 888 | P8_Milestone_Moved | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P8 | 2 | 0 | 2026-09-25 |
| 999 | P9_Milestone_Reopened | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P9 | 2 | 1 | 2026-09-25 |
| 111 | P11_Milestone_Overdue | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P11 | 2 | 0 | 2026-09-20 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-17.md"), "w") as f: f.write(snap1)
            
            snap2 = """# Snapshot: 2026-09-18
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % | Replans | Slip Days | Blocker | Filename | Milestones | Milestones Done | Next Milestone Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 3 | 0 | 2026-10-01 | 30 | 0 | 0 | Ninguno listado | P1 | 0 | 0 | |
| 222 | P2_Stalled | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P2 Stalled | 0 | 0 | |
| 444 | P4 | active | 10 | 0 | 0 | 2026-10-01 | 0 | 0 | 0 | Ninguno listado | P4 | 0 | 0 | |
| 555 | P5 | active | 0 | 0 | 0 | 2026-10-01 | 0 | 0 | 0 | Ninguno listado | P5 | 0 | 0 | |
| 666 | P6 | active | 10 | 5 | 0 | 2020-01-01 | 50 | 0 | 0 | Ninguno listado | P6 | 0 | 0 | |
| 777 | P7_Blocked | active | 10 | 5 | 0 | 2026-10-01 | 50 | 1 | 5 | Servidor caído | P7 Blocked | 0 | 0 | |
| 888 | P8_Milestone_Moved | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P8 | 2 | 0 | 2026-09-25 |
| 999 | P9_Milestone_Reopened | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P9 | 2 | 1 | 2026-09-25 |
| 111 | P11_Milestone_Overdue | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P11 | 2 | 0 | 2026-09-17 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-18.md"), "w") as f: f.write(snap2)
            
            snap3 = """# Snapshot: 2026-09-19
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % | Replans | Slip Days | Blocker | Filename | Milestones | Milestones Done | Next Milestone Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 4 | 0 | 2026-10-01 | 40 | 0 | 0 | Ninguno listado | P1 | 0 | 0 | |
| 222 | P2_Stalled | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P2 Stalled | 0 | 0 | |
| 444 | P4 | active | 10 | 0 | 0 | 2026-10-01 | 0 | 0 | 0 | Ninguno listado | P4 | 0 | 0 | |
| 555 | P5 | active | 0 | 0 | 0 | 2026-10-01 | 0 | 0 | 0 | Ninguno listado | P5 | 0 | 0 | |
| 666 | P6 | active | 10 | 5 | 0 | 2020-01-01 | 50 | 0 | 0 | Ninguno listado | P6 | 0 | 0 | |
| 777 | P7_Blocked | active | 10 | 5 | 1 | 2026-10-01 | 50 | 1 | 5 | Servidor caído | P7 Blocked | 0 | 0 | |
| 888 | P8_Milestone_Moved | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P8 | 2 | 0 | 2026-10-25 |
| 999 | P9_Milestone_Reopened | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P9 | 2 | 0 | 2026-09-25 |
| 111 | P11_Milestone_Overdue | active | 10 | 5 | 0 | 2026-10-01 | 50 | 0 | 0 | Ninguno listado | P11 | 2 | 0 | 2026-09-17 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-19.md"), "w") as f: f.write(snap3)
            
            report_path = generate_report(tmp, "2026-09-18", "2026-09-19", 3)
            
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Validar VERDE
            self.assertIn("## 🟢 Avance", content)
            self.assertIn("[[P1]]", content) # wikilink correcto
            
            # Validar ROJO (Estancado)
            self.assertIn("## 🔴 Alertas Rojas", content)
            self.assertIn("[[P2 Stalled]]", content) # wikilink con slugify (quitó _)
            self.assertIn("Estancado en 50%", content)
            
            # Validar ROJO (Blocker en Comité)
            self.assertIn("[[P7 Blocked]]", content)
            self.assertIn("Servidor caído", content)
            self.assertIn("Proyectos con bloqueadores críticos", content)
            
            # Validar GRIS (Nuevo / Sin tareas)
            self.assertIn("## ⚪️ Proyectos en Gris", content)
            self.assertIn("[[P5]]", content)
            
            # Validar ROJO (Milestone Moved)
            self.assertIn("[[P8]]", content)
            self.assertIn("Hito demorado: 2026-09-25 ➡️ 2026-10-25", content)
            
            # Validar ROJO (Milestone Reopened)
            self.assertIn("[[P9]]", content)
            self.assertIn("Hito reabierto (1 -> 0)", content)
            
            # Validar ROJO (Milestone Overdue)
            self.assertIn("[[P11]]", content)
            self.assertIn("Próximo hito vencido (2026-09-17)", content)

if __name__ == '__main__':
    unittest.main()
