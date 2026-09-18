import unittest
import tempfile
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))
from generate_status_report import generate_report

class TestReportStates(unittest.TestCase):
    def test_semantic_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            os.makedirs(os.path.join(tmp, "03 Log"))
            
            # Crear nota ficticia para extraer frontmatter
            with open(os.path.join(tmp, "02 Projects", "P1.md"), "w", encoding="utf-8") as f:
                f.write("---\ntype: proyecto\nasana_gid: 123\ncritical_blocker: 'A'\nreplan_count: 1\nslip_days: 5\n---\n")
                
            with open(os.path.join(tmp, "02 Projects", "P2.md"), "w", encoding="utf-8") as f:
                f.write("---\ntype: proyecto\nasana_gid: 222\n---\n")

            # Snapshot 1 (Día 1)
            # 123: Avanza después
            # 222: Se estancará en 50%
            # 333: Desaparecerá
            snap1 = """# Snapshot: 2026-09-17
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % |
|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 2 | 0 | 2026-10-01 | 20 |
| 222 | P2 | active | 10 | 5 | 0 | 2026-10-01 | 50 |
| 333 | P3 | active | 10 | 5 | 0 | 2026-10-01 | 50 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-17.md"), "w") as f: f.write(snap1)
            
            # Snapshot 2 (Día 2)
            # 123: Avanza a 30%
            # 222: Sigue 50%
            # 444: Aparece nuevo
            snap2 = """# Snapshot: 2026-09-18
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % |
|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 3 | 0 | 2026-10-01 | 30 |
| 222 | P2 | active | 10 | 5 | 0 | 2026-10-01 | 50 |
| 444 | P4 | active | 10 | 0 | 0 | 2026-10-01 | 0 |
| 555 | P5 | active | 0 | 0 | 0 | 2026-10-01 | 0 |
| 666 | P6 | active | 10 | 5 | 0 | 2020-01-01 | 50 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-18.md"), "w") as f: f.write(snap2)
            
            # Snapshot 3 (Día 3)
            # 123: Avanza a 40% -> VERDE
            # 222: Sigue 50% por tercer día -> ROJO (estancado 3 cortes)
            # 444: Sigue 0% (segundo día) -> GRIS (estancado 2 cortes)
            # 555: 0 total tareas -> GRIS (sin tareas)
            # 666: Fecha vencida 2020-01-01 -> ROJO
            # 333: (Ausente) -> GRIS
            snap3 = """# Snapshot: 2026-09-19
| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % |
|---|---|---|---|---|---|---|---|
| 123 | P1 | active | 10 | 4 | 0 | 2026-10-01 | 40 |
| 222 | P2 | active | 10 | 5 | 0 | 2026-10-01 | 50 |
| 444 | P4 | active | 10 | 0 | 0 | 2026-10-01 | 0 |
| 555 | P5 | active | 0 | 0 | 0 | 2026-10-01 | 0 |
| 666 | P6 | active | 10 | 5 | 0 | 2020-01-01 | 50 |
"""
            with open(os.path.join(tmp, "03 Log", "2026-09-19.md"), "w") as f: f.write(snap3)
            
            # Generar de 18 a 19 (con N=3)
            report_path = generate_report(tmp, "2026-09-18", "2026-09-19", 3)
            
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Validar VERDE
            self.assertIn("## 🟢 Avance", content)
            self.assertIn("P1", content)
            self.assertIn("30% ➡️ 40%", content)
            
            # Validar ROJO (Estancado N=3)
            self.assertIn("## 🔴 Alertas Rojas", content)
            self.assertIn("P2", content)
            self.assertIn("Estancado en 50% por 3 cortes", content)
            
            # Validar ROJO (Vencido)
            self.assertIn("P6", content)
            self.assertIn("Vencido (2020-01-01)", content)
            
            # Validar GRIS (Estancado N=2)
            self.assertIn("## ⚪️ Proyectos en Gris", content)
            self.assertIn("P4", content)
            self.assertIn("Sin movimiento reciente", content)
            
            # Validar GRIS (Sin tareas)
            self.assertIn("P5", content)
            self.assertIn("Sin tareas", content)
            
            # Validar GRIS (Nuevo)
            # P4 fue "Nuevo" en el corte de 17 a 18, pero de 18 a 19 ya no es nuevo.
            # Veamos si generamos el de 17 a 18, P4 sería nuevo
            report2_path = generate_report(tmp, "2026-09-17", "2026-09-18", 3)
            with open(report2_path, "r", encoding="utf-8") as f:
                content2 = f.read()
            self.assertIn("P4", content2)
            self.assertIn("Nuevo desde el último corte", content2)
            
            # P3 desaparece en el corte 17 a 18
            self.assertIn("P3", content2)
            self.assertIn("Ya no aparece en Asana", content2)

if __name__ == '__main__':
    unittest.main()
