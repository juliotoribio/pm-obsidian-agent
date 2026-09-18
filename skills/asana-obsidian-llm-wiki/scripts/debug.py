from unittest.mock import patch
from datetime import datetime, timezone
import tempfile
import os

from asana_obsidian_sync import plan_sync

@patch("asana_obsidian_sync.datetime")
@patch("asana_obsidian_sync.fetch_workspaces")
@patch("asana_obsidian_sync.fetch_teams")
@patch("asana_obsidian_sync.fetch_projects")
@patch("asana_obsidian_sync.fetch_project_tasks")
@patch("asana_obsidian_sync.fetch_me")
@patch("asana_obsidian_sync.fetch_portfolios")
def run(mock_portfolios, mock_me, mock_tasks, mock_projects, mock_teams, mock_workspaces, mock_datetime):
    mock_datetime.now.return_value = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    mock_workspaces.return_value = [{"gid": "ws1", "name": "Workspace 1"}]
    mock_teams.return_value = []
    mock_me.return_value = {}
    mock_portfolios.return_value = []
    mock_projects.return_value = [{"gid": "p1", "name": "Match"}]
    mock_tasks.return_value = []

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "02 Projects"))
        plan, meta = plan_sync("fake", tmp)
        print("PLAN CREATE:", plan["create"])

run()
