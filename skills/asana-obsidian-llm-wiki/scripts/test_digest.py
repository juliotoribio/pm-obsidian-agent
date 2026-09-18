import unittest
import os
import tempfile
import json
from unittest.mock import patch
import io
import sys

from generate_proactive_digest import generate_digest, evaluate_project

class TestProactiveDigest(unittest.TestCase):
    
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        self.log_dir = os.path.join(self.vault, "03 Log")
        os.makedirs(self.log_dir)
        
        self.state_dir = os.path.join(self.vault, "99 System")
        os.makedirs(self.state_dir)
        self.state_file = os.path.join(self.state_dir, "digest-state.json")
        
    def tearDown(self):
        self.tmp.cleanup()
        
    def generate_mock_snapshot(self, gid, name, status="proyecto", total=10, done=5, blocked=1, due_date="2026-10-10", pct=50, replans=0, slip=0, blocker="-", filename="file", ms=0, ms_done=0, next_ms="", ws="W1"):
        return f"""| asana_gid | name | status | total | done | blocked | due_date | pct | replans | slip | blocker | filename | milestones | milestones_done | next_milestone_date | workspace |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| {gid} | {name} | {status} | {total} | {done} | {blocked} | {due_date} | {pct} | {replans} | {slip} | {blocker} | {filename} | {ms} | {ms_done} | {next_ms} | {ws} |
"""
        
    def create_snapshot(self, date_str, content):
        with open(os.path.join(self.log_dir, f"{date_str}.md"), "w") as f:
            f.write(content)
            
    def read_state(self):
        if not os.path.exists(self.state_file):
            return {}
        with open(self.state_file, "r") as f:
            return json.load(f)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_three_runs_stalled_or_unchanged_red(self, mock_stdout):
        # Day 1: New project with blocked task
        snap_content = self.generate_mock_snapshot("111", "Proy A", blocked=1)
        self.create_snapshot("2026-09-01", snap_content)
        
        count1 = generate_digest(self.vault, umbral_dias=7, dry_run=False)
        self.assertEqual(count1, 1)
        self.assertIn("NUEVO: Proy A - Bloqueado (1 tareas)", mock_stdout.getvalue())
        
        state1 = self.read_state()
        self.assertEqual(state1["111"]["last_notified_state"], "rojo")
        self.assertEqual(state1["111"]["last_notified_date"], "2026-09-01")
        
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        
        # Day 2: Still blocked (1), nothing else changed.
        self.create_snapshot("2026-09-02", snap_content)
        
        count2 = generate_digest(self.vault, umbral_dias=7, dry_run=False)
        self.assertEqual(count2, 0)
        
        state2 = self.read_state()
        self.assertEqual(state2["111"]["last_notified_date"], "2026-09-01")
        
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        
        # Day 8: Still blocked, 7 days passed.
        self.create_snapshot("2026-09-08", snap_content)
        
        count3 = generate_digest(self.vault, umbral_dias=7, dry_run=False)
        self.assertEqual(count3, 1)
        self.assertIn("RECORDATORIO: Proy A - Bloqueado (1 tareas)", mock_stdout.getvalue())
        
        state3 = self.read_state()
        self.assertEqual(state3["111"]["last_notified_date"], "2026-09-08")
        
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_recovery_announced_only_once(self, mock_stdout):
        state = {
            "222": {
                "last_notified_date": "2026-09-01",
                "last_notified_state": "rojo",
                "last_notified_reason": "Bloqueado (1 tareas)",
                "snapshot_metrics": {
                    "name": "Proy B",
                    "blocked": 1,
                    "pct": 10,
                    "due_date": "2026-10-10",
                    "next_milestone_date": None,
                    "milestones_done": 0,
                    "total": 5
                }
            }
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f)
            
        # Day 2: Recovery (0 blocked tasks)
        snap_content = self.generate_mock_snapshot("222", "Proy B", blocked=0, pct=10, total=5)
        self.create_snapshot("2026-09-02", snap_content)
        
        count1 = generate_digest(self.vault, umbral_dias=7, dry_run=False)
        self.assertEqual(count1, 1)
        self.assertIn("RECUPERADO: Proy B", mock_stdout.getvalue())
        
        state_after = self.read_state()
        self.assertEqual(state_after["222"]["last_notified_state"], "verde")
        
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        
        # Day 3: Still recovered (0 blocked)
        self.create_snapshot("2026-09-03", snap_content)
        
        count2 = generate_digest(self.vault, umbral_dias=7, dry_run=False)
        self.assertEqual(count2, 0)
        self.assertNotIn("RECUPERADO", mock_stdout.getvalue())
        
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_dry_run_does_not_modify_state(self, mock_stdout):
        snap_content = self.generate_mock_snapshot("333", "Proy C", blocked=1)
        self.create_snapshot("2026-09-01", snap_content)
        
        count = generate_digest(self.vault, umbral_dias=7, dry_run=True)
        self.assertEqual(count, 1)
        self.assertIn("NUEVO: Proy C", mock_stdout.getvalue())
        
        self.assertFalse(os.path.exists(self.state_file))

if __name__ == '__main__':
    unittest.main()
