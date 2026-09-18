import os
import tempfile
import unittest
import sys

sys.path.append(os.path.join(os.path.dirname(__file__)))
from unittest.mock import patch
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

if __name__ == '__main__':
    unittest.main()
