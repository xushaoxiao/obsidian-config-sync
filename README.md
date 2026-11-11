# Obsidian Config Sync

Sync an Obsidian vault's `.obsidian/` directory with a dedicated private GitHub repository. Run the script directly or use the bundled Codex skill for setup, scheduled runs, and troubleshooting.

The checkout is rooted at `.obsidian/`. Git tracks workspace layouts, themes, snippets, plugin settings, and other files there, including normally ignored files. Notes and attachments elsewhere in the vault are outside the checkout. Git tracks files, so empty directories are omitted.

## Start

1. Open the vault in Obsidian so it creates `.obsidian/`.
2. Create an empty **private** repository on GitHub. Set up local Git authentication via SSH or a credential helper. Review plugin settings for any credentials before you publish a configuration snapshot.
3. Clone this project and run the initial sync with Python 3 and Git on macOS or Linux:

   ```sh
   git clone https://github.com/xushaoxiao/obsidian-config-sync.git
   cd obsidian-config-sync
   python3 .agents/skills/obsidian-config-sync/scripts/sync.py \
     --vault "$HOME/Documents/MyVault" \
     --remote https://github.com/OWNER/PRIVATE-REPO.git \
     --init
   ```

Use the same command without `--init` for subsequent runs. Add `--branch NAME` if your configuration repository uses a branch other than `main`. Use the same remote URL on every run.

The CLI checks the GitHub URL and the configured Git remote. Verify the repository is private on GitHub before running it.

## Codex and scheduled sync

Open the project in Codex to discover its [project skill](.agents/skills/obsidian-config-sync/SKILL.md). Run `$obsidian-config-sync` with the vault path and private remote. For scheduled runs, choose a **local** task with access to that vault. Use the script's absolute path so the task works from any directory.

## Sync and recovery

Each run fetches the remote and commits local changes, then merges compatible remote updates and pushes. If Git reports a merge conflict, the script aborts its merge and names the affected files. Both versions remain in Git for you to compare. A failed push leaves the local commit available for the next run.

To restore on another computer, close Obsidian and clone the configuration repository into the vault's `.obsidian/` directory when it is absent or empty. If the directory already has settings, clone somewhere else first and compare the two copies. Close Obsidian when applying a planned cross-device update to keep the app from rewriting a settings file during the operation.

## Development

Run the integration tests with `python3 -m unittest discover -s tests`. The tests use a temporary Git remote and need no GitHub credentials.
