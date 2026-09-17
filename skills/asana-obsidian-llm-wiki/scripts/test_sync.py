import os
import tempfile
import unittest
import sys

sys.path.append(os.path.join(os.path.dirname(__file__)))
from asana_obsidian_sync import parse_frontmatter, build_note, reconcile_tasks, source_hash

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
        self.assertIn("Hello world!", body)

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
