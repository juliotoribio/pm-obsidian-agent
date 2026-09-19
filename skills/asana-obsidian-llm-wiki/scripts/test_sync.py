import os
import tempfile
import unittest
import sys

sys.path.append(os.path.join(os.path.dirname(__file__)))
from unittest.mock import patch, mock_open
from asana_obsidian_sync import parse_frontmatter, build_note, reconcile_tasks, source_hash, render_frontmatter, scan_existing_notes, plan_sync, write_index

class TestSync(unittest.TestCase):
    def test_parse_frontmatter(self):
        text = """---
type: proyecto
aliases: ["P1", "P2"]
tags:
  - tag1
  - tag2
status: active
---
## Contexto
Hello world!"""
        fm, body = parse_frontmatter(text)
        self.assertEqual(fm.get("type"), "proyecto")
        self.assertEqual(fm.get("status"), "active")
        self.assertIn("aliases", fm)
        self.assertIn("tags", fm)
        self.assertEqual(fm["tags"], ["tag1", "tag2"])
        self.assertEqual(fm["aliases"], ["P1", "P2"])
        self.assertIn("Hello world!", body)

    def test_roundtrip_frontmatter(self):
        import yaml
        fm = {
            "type": "proyecto",
            "tags": ["estrategico", "capex"],
            "aliases": ["P1"],
            "status": "active",
            "meta": {"clave": "valor"}
        }
        rendered = render_frontmatter(fm)
        # Parse natively using the script
        fm2, _ = parse_frontmatter(rendered + "\nbody")
        self.assertEqual(fm["tags"], fm2["tags"])
        self.assertEqual(fm["aliases"], fm2["aliases"])
        self.assertEqual(fm["status"], fm2["status"])
        self.assertEqual(fm["meta"], fm2["meta"])
        
        # Ensure that it emits valid YAML
        raw = rendered.strip("-").strip("\n").strip()
        fm3 = yaml.safe_load(raw)
        self.assertEqual(fm["meta"], fm3["meta"])

    def test_scan_existing_notes_int_gid(self):
        # Create a temp directory simulating a vault
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            path = os.path.join(tmp, "02 Projects", "Test.md")
            with open(path, "w") as f:
                f.write("---\nasana_gid: 1234567890\n---\nBody")
            
            existing = scan_existing_notes(tmp)
            self.assertIn("1234567890", existing)
            self.assertEqual(existing["1234567890"]["fm"]["asana_gid"], 1234567890)

    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_corrupt_yaml_skipped_in_plan(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces):
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = [{"gid": "t1", "name": "Team 1"}]
        mock_projects.return_value = [{"gid": "9999", "name": "Broken Project"}]
        mock_tasks.return_value = []
        mock_me.return_value = {"gid": "me1", "name": "User 1"}
        mock_portfolios.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            path = os.path.join(tmp, "02 Projects", "Test.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("---\nasana_gid: \"9999\"\n[ esto rompe el YAML!\n---\nBody")
            
            plan, meta = plan_sync("fake_token", tmp)
            
            self.assertEqual(len(plan["create"]), 0)
            self.assertEqual(len(plan["corrupt"]), 1)
            self.assertEqual(plan["corrupt"][0]["project"]["gid"], "9999")
            
            # Now verify index doesn't include it
            write_index(tmp, plan, meta)
            idx_path = os.path.join(tmp, "LLM Wiki Index.md")
            with open(idx_path, "r", encoding="utf-8") as f:
                idx_content = f.read()
            self.assertNotIn("9999", idx_content)
            self.assertNotIn("broken-project", idx_content)

    def test_build_note_preserves_human_notes(self):
        fm = {"type": "proyecto"}
        hermes = "<!-- HERMES:START -->\nHello\n<!-- HERMES:END -->"
        existing_body = """# Titulo
<!-- HERMES:START -->
Old
<!-- HERMES:END -->

## Notas humanas
Esto es un comentario humano.
"""
        note = build_note(fm, hermes, existing_body)
        self.assertIn("Esto es un comentario humano.", note)
        self.assertIn("Hello", note)
        self.assertNotIn("Old", note)

    def test_apply_people_plan_preserves_human_notes(self):
        """Verifica que las notas manuales de una persona sobrevivan sin marcadores HERMES."""
        from asana_obsidian_sync import apply_people_plan, parse_frontmatter
        with tempfile.TemporaryDirectory() as tmp:
            people_dir = os.path.join(tmp, "08 People")
            os.makedirs(people_dir)
            md_path = os.path.join(people_dir, "Ana Perez.md")
            
            # Nota creada manualmente por el usuario antes de cualquier sync
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("---\nrol: Scrum Master\n---\n## Notas humanas\n\nRegistro del 1:1 con Ana.")
                
            people_stats = {
                "Ana Perez": {
                    "open_tasks": 5,
                    "overdue_tasks": 0,
                    "blocked_tasks": 0,
                    "active_projects": set()
                }
            }
            
            apply_people_plan(tmp, people_stats, "2026-09-18")
            
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            fm, body = parse_frontmatter(content)
            self.assertEqual(fm.get("rol"), "Scrum Master")
            self.assertEqual(fm.get("open_tasks"), 5)
            self.assertIn("Registro del 1:1 con Ana.", body)
            self.assertIn("<!-- HERMES:START -->", body)

    def test_reconcile_tasks(self):
        tasks = [
            {"name": "Done in Asana", "completed": True, "notes": ""},
            {"name": "Done in Notes", "completed": False, "notes": "Completed: TRUE"},
            {"name": "Blocked", "completed": False, "notes": "Status: Bloqueado", "due_on": "2026-09-17"}
        ]
        roll = reconcile_tasks(tasks)
        self.assertEqual(roll["tasks_total"], 3)
        self.assertEqual(roll["tasks_done"], 2)
        self.assertEqual(roll["tasks_blocked"], 1)

    def test_source_hash_stability(self):
        p = {"gid": "123", "name": "P1"}
        tasks = [{"gid": "t1", "completed": False}]
        
        h1 = source_hash(p, tasks, "Programa A")
        h2 = source_hash(p, tasks, "Programa A")
        self.assertEqual(h1, h2)
        
        h3 = source_hash(p, tasks, "Programa B")
        self.assertNotEqual(h1, h3)

    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_financial_fields_preserved(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from asana_obsidian_sync import plan_sync, apply_plan, parse_frontmatter
        from datetime import datetime, timezone
        import yaml
        
        mock_datetime.now.return_value = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []
        mock_projects.return_value = [{"gid": "p1", "name": "P1"}]
        mock_tasks.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            p1_path = os.path.join(tmp, "02 Projects", "P1.md")
            with open(p1_path, "w", encoding="utf-8") as f:
                f.write("---\nasana_gid: \"p1\"\ncapex_budget: 150000\nopex_budget: 50000\nspend_ytd: 20000\ncapitalization_status: In Progress\n---\n# P1\n<!-- HERMES:START -->\n<!-- HERMES:END -->\n")
                
            # RUN SYNC 1
            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            # RUN SYNC 2
            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            with open(p1_path, "r", encoding="utf-8") as f:
                fm, _ = parse_frontmatter(f.read())
                
            self.assertEqual(fm.get("capex_budget"), 150000)
            self.assertEqual(fm.get("opex_budget"), 50000)
            self.assertEqual(fm.get("spend_ytd"), 20000)
            self.assertEqual(fm.get("capitalization_status"), "In Progress")

    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_finanzas_logic(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from asana_obsidian_sync import plan_sync, apply_plan, parse_frontmatter
        from datetime import datetime, timezone
        
        mock_datetime.now.return_value = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []
        mock_projects.return_value = [
            {"gid": "p1", "name": "Presupuesto Cero"},
            {"gid": "p2", "name": "Campos Ausentes"},
            {"gid": "p3", "name": "Watermelon"},
            {"gid": "p4", "name": "Sin Clasificar"}
        ]
        # P3 and P4 will have tasks to calculate pct_avance
        mock_tasks.side_effect = lambda token, gid: [{"gid": "t1", "completed": True}] if gid in ["p3", "p4"] else []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            p1_path = os.path.join(tmp, "02 Projects", "Presupuesto Cero.md")
            with open(p1_path, "w", encoding="utf-8") as f:
                f.write("---\nasana_gid: \"p1\"\ncapex_budget: 0\nopex_budget: 0\nspend_ytd: 500\n---\n")
                
            p2_path = os.path.join(tmp, "02 Projects", "Campos Ausentes.md")
            with open(p2_path, "w", encoding="utf-8") as f:
                f.write("---\nasana_gid: \"p2\"\n---\n")

            p3_path = os.path.join(tmp, "02 Projects", "Watermelon.md")
            with open(p3_path, "w", encoding="utf-8") as f:
                # pct_avance will be 100%. pct_presupuesto will be 150%. Watermelon!
                f.write("---\nasana_gid: \"p3\"\ncapex_budget: 100\nopex_budget: 0\nspend_ytd: 150\ncapitalization_status: OPEX\n---\n")

            p4_path = os.path.join(tmp, "02 Projects", "Sin Clasificar.md")
            with open(p4_path, "w", encoding="utf-8") as f:
                f.write("---\nasana_gid: \"p4\"\ncapex_budget: 100\nspend_ytd: 50\n---\n")

            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            with open(p1_path, "r", encoding="utf-8") as f: fm1, _ = parse_frontmatter(f.read())
            self.assertNotIn("capitalization_status", fm1) # 0 budgets don't get "Sin clasificar"
            
            with open(p2_path, "r", encoding="utf-8") as f: fm2, _ = parse_frontmatter(f.read())
            self.assertNotIn("capitalization_status", fm2)
            
            with open(p3_path, "r", encoding="utf-8") as f: fm3, _ = parse_frontmatter(f.read())
            self.assertEqual(fm3.get("capitalization_status"), "OPEX") # intact
            
            with open(p4_path, "r", encoding="utf-8") as f: fm4, _ = parse_frontmatter(f.read())
            self.assertEqual(fm4.get("capitalization_status"), "Sin clasificar")
    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_sync_ignores_risks_folder(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from asana_obsidian_sync import plan_sync, apply_plan
        from datetime import datetime, timezone
        
        mock_datetime.now.return_value = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []
        mock_projects.return_value = [{"gid": "p1", "name": "P1"}]
        mock_tasks.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            # Crear riesgo artificialmente
            os.makedirs(os.path.join(tmp, "06 Risks"))
            riesgo_path = os.path.join(tmp, "06 Risks", "Riesgo-P1.md")
            with open(riesgo_path, "w", encoding="utf-8") as f:
                f.write("---\ntype: riesgo\n---\nDetalles del riesgo")
                
            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            # Verificar que existe intacto
            self.assertTrue(os.path.exists(riesgo_path))
            with open(riesgo_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "---\ntype: riesgo\n---\nDetalles del riesgo")

    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_historical_snapshots_and_baseline(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from datetime import datetime, timezone
        import asana_obsidian_sync

        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = [{"gid": "t1", "name": "Team 1"}]
        mock_tasks.return_value = []
        mock_me.return_value = {"gid": "me1", "name": "User 1"}
        mock_portfolios.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            os.makedirs(os.path.join(tmp, "03 Log"))

            # --- PRIMER SYNC ---
            mock_projects.return_value = [{"gid": "123", "name": "P1", "due_on": "2026-09-20"}]
            # Mock datetime para el 2026-09-17
            dt1 = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = dt1
            mock_datetime.strptime = datetime.strptime # pass through strptime
            
            plan1, meta1 = plan_sync("fake_token", tmp)
            asana_obsidian_sync.apply_plan(tmp, plan1, meta1)
            asana_obsidian_sync.write_snapshot(tmp, plan1, meta1)

            # Verificar note de proyecto
            path_p1 = os.path.join(tmp, "02 Projects", "P1.md")
            with open(path_p1, "r", encoding="utf-8") as f:
                fm1, _ = parse_frontmatter(f.read())
            self.assertEqual(fm1.get("baseline_due_date"), "2026-09-20")
            self.assertEqual(fm1.get("replan_count"), 0)
            self.assertEqual(fm1.get("slip_days"), 0)

            # Verificar Snapshot 1
            snap1_path = os.path.join(tmp, "03 Log", "2026-09-17.md")
            self.assertTrue(os.path.exists(snap1_path))

            # --- SEGUNDO SYNC ---
            # Simulamos que en Asana cambió la fecha de entrega
            mock_projects.return_value = [{"gid": "123", "name": "P1", "due_on": "2026-09-25"}]
            # Mock datetime para el 2026-09-18
            dt2 = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = dt2

            plan2, meta2 = plan_sync("fake_token", tmp)
            asana_obsidian_sync.apply_plan(tmp, plan2, meta2)
            asana_obsidian_sync.write_snapshot(tmp, plan2, meta2)

            # Verificar note de proyecto tras mutación
            with open(path_p1, "r", encoding="utf-8") as f:
                fm2, _ = parse_frontmatter(f.read())
            self.assertEqual(fm2.get("baseline_due_date"), "2026-09-20") # inmutable
            self.assertEqual(fm2.get("replan_count"), 1)
            self.assertEqual(fm2.get("slip_days"), 5)

            # Verificar Snapshot 2
            snap2_path = os.path.join(tmp, "03 Log", "2026-09-18.md")
            self.assertTrue(os.path.exists(snap2_path))
            
            with open(snap2_path, "r", encoding="utf-8") as f:
                snap_content = f.read()
            self.assertIn("| asana_gid | Proyecto | Status | Total | Done | Blocked | Due Date | % | Replans | Slip Days | Blocker | Filename | Milestones | Milestones Done | Next Milestone Date |", snap_content)
            self.assertIn("| 123 | P1 | active | 0 | 0 | 0 | 2026-09-25 | 0 | 1 | 5 |  | P1.md | 0 | 0 |  |", snap_content)


    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_edge_cases_and_slug_collisions(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from datetime import datetime, timezone
        dt = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = dt
        mock_datetime.strptime = datetime.strptime # pass through strptime
        
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = [{"gid": "t1", "name": "Team 1"}]
        mock_me.return_value = {"gid": "me1", "name": "User 1"}
        mock_portfolios.return_value = []

        # Tareas mockeadas por gid de proyecto
        def mock_fetch_tasks(token, gid):
            if gid == "p_all_completed":
                return [{"gid": "t1", "completed": True}, {"gid": "t2", "completed": True}]
            return []
        
        mock_tasks.side_effect = mock_fetch_tasks

        long_name = "A" * 250
        long_name_2 = "A" * 250 + "B" # Deberían truncarse igual y colisionar
        
        mock_projects.return_value = [
            {"gid": "p_weird", "name": "Project / with | and : and 🚀", "due_on": "2026-09-20"},
            {"gid": "p_long", "name": long_name, "due_on": "2026-09-20"},
            {"gid": "p_long_2", "name": long_name_2, "due_on": "2026-09-20"},
            {"gid": "p_no_due", "name": "No Due Date"},
            {"gid": "p_no_tasks", "name": "No Tasks", "due_on": "2026-09-20"},
            {"gid": "p_all_completed", "name": "All Completed", "due_on": "2026-09-20"},
            # Colisión de nombres
            {"gid": "p_col1", "name": "Mi Proyecto", "due_on": "2026-09-20"},
            {"gid": "p_col2", "name": "Mi_Proyecto", "due_on": "2026-09-20"},
            # Slug vacío
            {"gid": "p_empty", "name": "🚀///🚀", "due_on": "2026-09-20"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            os.makedirs(os.path.join(tmp, "03 Log"))

            plan1, meta1 = plan_sync("fake_token", tmp)
            import asana_obsidian_sync
            asana_obsidian_sync.apply_plan(tmp, plan1, meta1)
            asana_obsidian_sync.write_snapshot(tmp, plan1, meta1)
            
            # Verificar existencia de archivos en el disco y evitar sobreescritura
            files = set(os.listdir(os.path.join(tmp, "02 Projects")))
            # Deberíamos tener 9 archivos distintos
            self.assertEqual(len(files), 9)
            
            # Verificar nombres de archivo (slugify & colisiones)
            self.assertIn("Project with and and.md", files) # Caracteres raros limpiados
            self.assertIn("No Due Date.md", files)
            self.assertIn("No Tasks.md", files)
            self.assertIn("All Completed.md", files)
            self.assertIn("Mi Proyecto.md", files)
            self.assertIn("Mi Proyecto (p_col2).md", files) # Desempate aplicado
            self.assertIn("p_empty.md", files) # Slug vacío usa gid
            
            # Verificar longitud máxima y colisión
            self.assertIn(long_name[:200] + ".md", files)
            self.assertIn(long_name[:200] + " (long_2).md", files)
            
            # Verificar snapshot columns
            snap_path = os.path.join(tmp, "03 Log", "2026-09-17.md")
            self.assertTrue(os.path.exists(snap_path))
            with open(snap_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("| Filename |", content)
                self.assertIn("| p_empty.md |", content)
                self.assertIn("| Mi Proyecto (p_col2).md |", content)
                
            # SIMULAR SEGUNDO SYNC (Incremental)
            plan2, meta2 = plan_sync("fake_token", tmp)
            
            self.assertEqual(len(plan2["create"]), 0)
            self.assertEqual(len(plan2["skip"]), 9)


    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_rag_formulas(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from datetime import datetime, timezone
        from asana_obsidian_sync import plan_sync, apply_plan

        dt = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = dt
        mock_datetime.strptime = datetime.strptime
        
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []

        mock_projects.return_value = [
            # Coincidencia: Asana Verde, Calculado Verde (0 bloqueos, 0 slip, avance normal)
            {"gid": "p_match", "name": "Match", "due_on": "2026-09-25", "current_status": {"color": "green"}},
            # Watermelon: Asana Verde, Calculado Rojo (bloqueado)
            {"gid": "p_watermelon", "name": "Watermelon", "due_on": "2026-09-25", "current_status": {"color": "green"}},
            # Falso alarmista: Asana Rojo, Calculado Verde
            {"gid": "p_alarm", "name": "Alarm", "due_on": "2026-09-25", "current_status": {"color": "red"}},
            # Falta RAG: Asana null, Calculado Rojo (slip grave)
            {"gid": "p_no_gov", "name": "No Gov", "due_on": "2026-10-10"},
            # Grises: Asana null, Calculado null (sin fecha, sin tareas)
            {"gid": "p_grey", "name": "Grey", "current_status": {}}
        ]

        def mock_fetch_tasks(token, gid):
            if gid == "p_match":
                return [{"gid": "t1", "completed": False, "notes": "Status: Doing\nDependents: None"}]
            if gid == "p_watermelon":
                return [{"gid": "t2", "name": "Tarea 2", "completed": False, "notes": "Status: Bloqueado\nDependents: t3"}]
            if gid == "p_alarm":
                return [{"gid": "t3", "completed": False, "notes": "Status: Doing\nDependents: None"}]
            return []
        
        mock_tasks.side_effect = mock_fetch_tasks

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            # Simularemos que "p_no_gov" tiene slip_days inyectando en las notas base
            path_no_gov = os.path.join(tmp, "02 Projects", "No Gov.md")
            with open(path_no_gov, "w") as f:
                f.write("---\nasana_gid: p_no_gov\nbaseline_due_date: 2026-09-01\n---\n")

            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            def get_rag(gid, title):
                path = os.path.join(tmp, "02 Projects", f"{title}.md")
                with open(path, "r", encoding="utf-8") as f:
                    fm, _ = parse_frontmatter(f.read())
                return fm.get("rag_declarado"), fm.get("rag_calculado")

            dec, calc = get_rag("p_match", "Match")
            self.assertEqual(dec, "Verde")
            self.assertEqual(calc, "Verde")

            dec, calc = get_rag("p_watermelon", "Watermelon")
            self.assertEqual(dec, "Verde")
            self.assertEqual(calc, "Rojo")

            dec, calc = get_rag("p_alarm", "Alarm")
            self.assertEqual(dec, "Rojo")
            self.assertEqual(calc, "Verde")

            dec, calc = get_rag("p_no_gov", "No Gov")
            self.assertEqual(dec, "Sin declarar")
            self.assertEqual(calc, "Rojo")

            dec, calc = get_rag("p_grey", "Grey")
            self.assertEqual(dec, "Sin declarar")
            self.assertEqual(calc, "Sin calcular")


    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_milestones(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from datetime import datetime, timezone
        from asana_obsidian_sync import plan_sync, apply_plan

        dt = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = dt
        mock_datetime.strptime = datetime.strptime
        
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []

        mock_projects.return_value = [
            {"gid": "p_milestones", "name": "Project Milestones", "due_on": "2026-12-31"},
        ]

        def mock_fetch_tasks(token, gid):
            return [
                {"gid": "t1", "name": "Hito Pasado", "completed": True, "completed_at": "2026-09-01T10:00:00Z", "resource_subtype": "milestone"},
                {"gid": "t2", "name": "Hito Futuro Cercano", "completed": False, "due_on": "2026-10-01", "resource_subtype": "milestone"},
                {"gid": "t3", "name": "Hito Futuro Lejano", "completed": False, "due_on": "2026-11-01", "resource_subtype": "milestone"},
                {"gid": "t4", "name": "Hito Sin Fecha", "completed": False, "resource_subtype": "milestone"},
                {"gid": "t5", "name": "Tarea Normal 1", "completed": False},
                {"gid": "t6", "name": "Tarea Normal 2", "completed": True},
            ]
        
        mock_tasks.side_effect = mock_fetch_tasks

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            
            path = os.path.join(tmp, "02 Projects", "Project Milestones.md")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            fm, body = parse_frontmatter(content)
            
            self.assertEqual(fm.get("tasks_total"), 6)
            self.assertEqual(fm.get("tasks_done"), 2)
            self.assertEqual(fm.get("milestones_total"), 4)
            self.assertEqual(fm.get("milestones_done"), 1)
            self.assertEqual(fm.get("next_milestone"), "Hito Futuro Cercano")
            self.assertEqual(fm.get("next_milestone_date"), "2026-10-01")
            
            # Verificar renderizado en Markdown
            self.assertIn("## Hitos", body)
            self.assertIn("- [ ] Hito Futuro Cercano — vence 2026-10-01", body)
            self.assertIn("- [ ] Hito Futuro Lejano — vence 2026-11-01", body)
            self.assertIn("- [ ] Hito Sin Fecha — vence sin fecha", body)
            self.assertIn("- [x] Hito Pasado", body)
            
            # Verificar que no aparecen duplicados en Prioridades activas
            act_section = body.split("## Prioridades activas")[1]
            self.assertIn("Tarea Normal 1", act_section)
            self.assertNotIn("Hito Futuro Cercano", act_section)


    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_people_layer_and_bus_factor(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from datetime import datetime, timezone
        from asana_obsidian_sync import plan_sync, apply_plan, apply_people_plan

        dt = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = dt
        mock_datetime.strptime = datetime.strptime
        
        mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []

        mock_projects.return_value = [
            {"gid": "p_bus", "name": "Project Bus Factor", "due_on": "2026-12-31"},
            {"gid": "p_shared", "name": "Project Shared", "due_on": "2026-12-31"},
        ]

        def mock_fetch_tasks(token, gid):
            if gid == "p_bus":
                return [
                    {"gid": "t1", "name": "T1", "completed": False, "assignee": {"name": "Maria"}, "due_on": "2026-09-01"}, # overdue
                    {"gid": "t2", "name": "T2", "completed": False, "assignee": {"name": "Maria"}, "notes": "Status: bloqueado no db"}, # blocked
                ]
            else:
                return [
                    {"gid": "t3", "name": "T3", "completed": False, "assignee": {"name": "Maria"}},
                    {"gid": "t4", "name": "T4", "completed": False, "assignee": {"name": "Juan"}},
                    {"gid": "t5", "name": "T5", "completed": True, "assignee": {"name": "Juan"}}, # completed ignores
                ]
        
        mock_tasks.side_effect = mock_fetch_tasks

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            # create manual note for Juan without HERMES markers
            os.makedirs(os.path.join(tmp, "08 People"))
            juan_path = os.path.join(tmp, "08 People", "Juan.md")
            with open(juan_path, "w") as f:
                f.write("---\nmanual_field: test\n---\n## Notas humanas\n\nMy manual notes")
            
            plan, meta = plan_sync("fake_token", tmp)
            apply_plan(tmp, plan, meta)
            apply_people_plan(tmp, plan["people_stats"], meta["synced_at"])
            
            # 1. Bus Factor Check
            path_bus = os.path.join(tmp, "02 Projects", "Project Bus Factor.md")
            with open(path_bus, "r", encoding="utf-8") as f:
                content_bus = f.read()
            fm_bus, _ = parse_frontmatter(content_bus)
            self.assertTrue(fm_bus.get("bus_factor_alert"))
            
            path_shared = os.path.join(tmp, "02 Projects", "Project Shared.md")
            with open(path_shared, "r", encoding="utf-8") as f:
                content_shared = f.read()
            fm_shared, _ = parse_frontmatter(content_shared)
            self.assertFalse(fm_shared.get("bus_factor_alert"))
            
            # 2. People Check - Maria
            maria_path = os.path.join(tmp, "08 People", "Maria.md")
            with open(maria_path, "r", encoding="utf-8") as f:
                content_m = f.read()
            fm_m, body_m = parse_frontmatter(content_m)
            self.assertEqual(fm_m.get("open_tasks"), 3) # 2 bus + 1 shared
            self.assertEqual(fm_m.get("overdue_tasks"), 1)
            self.assertEqual(fm_m.get("blocked_tasks"), 1)
            self.assertIn("[[Project Bus Factor]]", fm_m.get("active_projects"))
            self.assertIn("[[Project Shared]]", fm_m.get("active_projects"))
            self.assertIn("## Carga Consolidada de Maria", body_m)
            
            # 3. People Check - Juan (preserve manual)
            with open(juan_path, "r", encoding="utf-8") as f:
                content_j = f.read()
            fm_j, body_j = parse_frontmatter(content_j)
            self.assertEqual(fm_j.get("open_tasks"), 1) # only t4 is open
            self.assertEqual(fm_j.get("manual_field"), "test")
            self.assertIn("My manual notes", body_j)
            self.assertIn("## Notas humanas", body_j)


    @patch("asana_obsidian_sync.datetime")
    @patch("asana_obsidian_sync.fetch_workspaces")
    @patch("asana_obsidian_sync.fetch_teams")
    @patch("asana_obsidian_sync.fetch_projects")
    @patch("asana_obsidian_sync.fetch_project_tasks")
    @patch("asana_obsidian_sync.fetch_me")
    @patch("asana_obsidian_sync.fetch_portfolios")
    def test_multi_workspace_no_collision(self, mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
        from asana_obsidian_sync import plan_sync, apply_plan, parse_frontmatter
        from datetime import datetime, timezone
        
        mock_datetime.now.return_value = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        mock_workspaces.return_value = [
            {"gid": "ws1", "name": "Workspace 1"},
            {"gid": "ws2", "name": "Workspace 2"}
        ]
        mock_teams.return_value = []
        mock_me.return_value = {}
        mock_portfolios.return_value = []
        
        # Simulate different projects coming from different workspaces based on the ws param
        def fake_projects(token, ws_gid, limit=None):
            if ws_gid == "ws1":
                return [{"gid": "p1", "name": "Proyecto A"}]
            else:
                return [{"gid": "p2", "name": "Proyecto A"}] # Same name!
        mock_projects.side_effect = fake_projects
        mock_tasks.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "02 Projects"))
            
            plan, meta = plan_sync("fake_token", tmp, all_workspaces=True)
            apply_plan(tmp, plan, meta)
            
            # The files shouldn't collide because they have different gids and slugify prevents it
            p1_path = os.path.join(tmp, "02 Projects", "Proyecto A.md")
            p2_path = os.path.join(tmp, "02 Projects", "Proyecto A (p2).md") # Fallback avoids collision
            
            self.assertTrue(os.path.exists(p1_path))
            self.assertTrue(os.path.exists(p2_path))
            
            with open(p1_path, "r", encoding="utf-8") as f:
                fm1, _ = parse_frontmatter(f.read())
                self.assertEqual(fm1.get("workspace"), "Workspace 1")
                
            with open(p2_path, "r", encoding="utf-8") as f:
                fm2, _ = parse_frontmatter(f.read())
                self.assertEqual(fm2.get("workspace"), "Workspace 2")

    def test_write_index_no_nameerror(self):
        from asana_obsidian_sync import write_index
        with tempfile.TemporaryDirectory() as tmp:
            plan = {
                "create": [{"fm": {"asana_gid": "gid1", "due_date": "2026-09-19"}, "filename": "P1.md"}],
                "update": [],
                "skip": [{"existing": {"path": "P2.md"}, "fm": {"asana_gid": "gid2"}}]
            }
            meta = {
                "synced_at": "2026-09-19T10:00:00Z",
                "workspaces": [{"name": "WS1"}]
            }
            # Should not raise NameError
            write_index(tmp, plan, meta)
            
            index_path = os.path.join(tmp, "LLM Wiki Index.md")
            self.assertTrue(os.path.exists(index_path))
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("- [[P1]] — `gid1` — vence 2026-09-19", content)
                self.assertIn("- [[P2]] — `gid2` — vence sin fecha", content)

    @patch("asana_obsidian_sync.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="ASANA_ACCESS_TOKEN=from_env_file\nOBSIDIAN_VAULT_PATH=from_env_file")
    def test_load_env_priorities(self, mock_file, mock_exists):
        from asana_obsidian_sync import load_env
        import os
        mock_exists.return_value = True
        
        # Scenario 1: Both in os.environ, os.environ has truncated token
        with patch.dict(os.environ, {"ASANA_ACCESS_TOKEN": "truncated", "OBSIDIAN_VAULT_PATH": "from_environ"}):
            token, vault = load_env()
            self.assertEqual(token, "from_env_file")
            self.assertEqual(vault, "from_environ")
            
        # Scenario 2: Token not in os.environ, Vault not in os.environ
        with patch.dict(os.environ, {}, clear=True):
            token, vault = load_env()
            self.assertEqual(token, "from_env_file")
            self.assertEqual(vault, "from_env_file")
            
        # Scenario 3: Token in os.environ but NOT in env file (simulate missing in .env)
        mock_file.side_effect = [mock_open(read_data="OBSIDIAN_VAULT_PATH=from_env_file").return_value] * 10
        with patch.dict(os.environ, {"ASANA_ACCESS_TOKEN": "fallback_environ", "OBSIDIAN_VAULT_PATH": "from_environ"}):
            token, vault = load_env()
            self.assertEqual(token, "fallback_environ")
            self.assertEqual(vault, "from_environ")

if __name__ == '__main__':
    unittest.main()
