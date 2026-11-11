---
name: obsidian-config-sync
description: Back up and synchronize an Obsidian vault's .obsidian configuration with a dedicated private GitHub repository. Use when setting up, running, scheduling, or troubleshooting local Obsidian Git sync.
---

# Obsidian Config Sync

1. Resolve the local vault path and the user's dedicated private GitHub repository. Confirm that Obsidian has created the vault's `.obsidian/` directory. The Git checkout lives inside that directory, so vault notes and attachments are outside its scope.
2. For first setup, verify on GitHub that the destination is private and empty. Run the bundled Python script with `--init`. The CLI validates the URL and local remote binding, so check visibility independently if the destination changes. Keep authentication in the local Git credential helper or SSH agent.
3. For subsequent runs, use the same command without `--init`:

   ```sh
   python3 /absolute/path/to/this/skill/scripts/sync.py \
     --vault "/absolute/path/to/vault" \
     --remote "https://github.com/OWNER/PRIVATE-REPO.git"
   ```

4. After a successful manual run, configure the requested recurrence in the local Codex scheduler. Bind it to the computer and project with write access to the vault. Pass absolute paths and the same remote on every run. If the user has no cadence preference, start with daily sync.
5. Report the result from the script. On a conflict, both committed versions remain available. Identify the files that need a decision and leave Git history intact. On an authentication or connectivity error, keep the same target and retry after access is restored.

For another computer, clone the private repository directly into the vault's `.obsidian/` when that directory is absent or empty. If it already contains settings, compare it with a separate clone before deciding what to carry over.
