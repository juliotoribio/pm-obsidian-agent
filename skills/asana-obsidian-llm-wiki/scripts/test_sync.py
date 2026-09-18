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

if __name__ == '__main__':
    unittest.main()
