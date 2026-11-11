import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/obsidian-config-sync/scripts/sync.py"
REMOTE = "https://github.com/example/obsidian-settings.git"


class SyncTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bare = self.root / "settings.git"
        self.vault = self.root / "vault"
        self.config = self.vault / ".obsidian"
        self.config.mkdir(parents=True)
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": str(self.root / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{self.bare.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": REMOTE,
        }
        self.git(self.root, "config", "--global", "user.name", "Integration Test")
        self.git(self.root, "config", "--global", "user.email", "test@example.invalid")
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.bare))

    def git(self, directory, *args):
        return subprocess.run(
            ("git", *args), cwd=directory, env=self.env, check=True, text=True, capture_output=True
        ).stdout.strip()

    def run_sync(self, *args, expected=0):
        result = subprocess.run(
            (sys.executable, str(SCRIPT), "--vault", str(self.vault), "--remote", REMOTE, *args),
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def put(self, directory, name, value):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    def clone(self):
        other = self.root / "other"
        self.git(self.root, "clone", REMOTE, str(other))
        return other

    def publish(self, checkout):
        self.git(checkout, "add", "-A")
        self.git(checkout, "commit", "-m", "Change remote configuration")
        self.git(checkout, "push", "origin", "main")

    def test_scope_ignored_files_and_idempotence(self):
        self.put(self.vault, "notes/private.md", "outside the checkout")
        (self.config / ".gitignore").write_text("plugins/\n", encoding="utf-8")
        self.put(self.config, "plugins/demo/data.json", {"enabled": True})
        self.put(self.config, "workspace.json", {"layout": "saved"})
        self.assertIn("synchronized", self.run_sync("--init"))
        self.assertEqual(
            self.git(self.bare, "ls-tree", "-r", "--name-only", "main").splitlines(),
            [".gitignore", "plugins/demo/data.json", "workspace.json"],
        )
        self.assertIn("already up to date", self.run_sync())
        (self.config / "workspace.json").unlink()
        self.assertIn("synchronized", self.run_sync())
        self.assertNotIn("workspace.json", self.git(self.bare, "ls-tree", "main"))

    def test_remote_fast_forward(self):
        self.put(self.config, "app.json", {"version": 1})
        self.run_sync("--init")
        other = self.clone()
        self.put(other, "app.json", {"version": 2})
        self.publish(other)
        self.assertIn("Pulled remote", self.run_sync())
        self.assertEqual(json.loads((self.config / "app.json").read_text()), {"version": 2})

    def test_merge_disjoint_updates(self):
        self.put(self.config, "app.json", {"version": 1})
        self.run_sync("--init")
        other = self.clone()
        self.put(other, "theme.json", {"name": "remote"})
        self.publish(other)
        self.put(self.config, "hotkeys.json", {"name": "local"})
        self.assertIn("synchronized", self.run_sync())
        self.assertTrue((self.config / "theme.json").is_file())
        self.assertIn("hotkeys.json", self.git(self.bare, "ls-tree", "main"))

    def test_conflict_preserves_both_commits_and_worktree(self):
        self.put(self.config, "workspace.json", {"layout": "original"})
        self.run_sync("--init")
        other = self.clone()
        self.put(other, "workspace.json", {"layout": "remote"})
        self.publish(other)
        self.put(self.config, "workspace.json", {"layout": "local"})
        self.assertIn("Conflicts: workspace.json", self.run_sync(expected=1))
        self.assertEqual(self.git(self.config, "status", "--porcelain"), "")
        self.assertEqual(json.loads(self.git(self.config, "show", "HEAD:workspace.json")), {"layout": "local"})
        self.assertEqual(json.loads(self.git(self.bare, "show", "main:workspace.json")), {"layout": "remote"})

    def test_missing_settings_and_existing_remote(self):
        self.config.rmdir()
        self.assertIn("Open the vault", self.run_sync("--init", expected=1))
        self.put(self.config, "app.json", {"version": 1})
        self.run_sync("--init")
        second = self.root / "second-vault"
        self.put(second / ".obsidian", "app.json", {"version": 2})
        self.vault = second
        self.assertIn("Remote already has history", self.run_sync("--init", expected=1))
        self.assertEqual(json.loads((second / ".obsidian/app.json").read_text()), {"version": 2})


if __name__ == "__main__":
    unittest.main()
