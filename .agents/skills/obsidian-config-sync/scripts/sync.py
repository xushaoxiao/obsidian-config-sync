"""Synchronize a vault's configuration checkout with a dedicated GitHub remote."""

import argparse
import fcntl
import os
from pathlib import Path
import re
import subprocess
import sys


GITHUB_URL = re.compile(
    r"(?:https://github\.com/|git@github\.com:)[A-Za-z0-9-]+/[A-Za-z0-9_.-]+"
)


class SyncError(Exception):
    """A sync that needs attention before it can continue."""


def git(directory, *args, allowed=(0,)):
    env = os.environ.copy()
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(name, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ("git", *args),
        cwd=directory,
        env=env,
        text=True,
        capture_output=True,
        timeout=90 if args[0] in ("fetch", "push") else None,
    )
    if result.returncode not in allowed:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncError(f"git {args[0]} failed. {detail}")
    return result


def sync(vault, remote, branch, initialize):
    config = vault / ".obsidian"
    if config.is_symlink() or not config.is_dir():
        raise SyncError(f"Open the vault in Obsidian first to create {config}.")

    git(config, "check-ref-format", f"refs/heads/{branch}")
    metadata = config / ".git"
    if not metadata.exists() and initialize:
        git(config, "init", f"--initial-branch={branch}")
    if metadata.is_symlink() or not metadata.is_dir():
        raise SyncError("Expected a dedicated Git checkout inside .obsidian. Use --init for first setup.")

    checkout = git(config, "rev-parse", "--show-toplevel").stdout.strip()
    if Path(checkout).resolve() != config:
        raise SyncError("Git checkout is outside .obsidian.")

    with (metadata / "obsidian-config-sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "Sync already running."
        return sync_branch(config, metadata, remote, branch, initialize)


def sync_branch(config, metadata, remote, branch, initialize):
    operations = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer")
    if any((metadata / operation).exists() for operation in operations):
        raise SyncError("Finish the Git operation in .obsidian before syncing.")

    current_branch = git(config, "symbolic-ref", "--short", "HEAD").stdout.strip()
    if current_branch != branch:
        raise SyncError(f"Checked out {current_branch}, expected {branch}.")

    origin = git(config, "config", "--get-all", "remote.origin.url", allowed=(0, 1)).stdout.splitlines()
    if not origin and initialize:
        git(config, "remote", "add", "origin", remote)
        origin = [remote]
    push_urls = git(config, "config", "--get-all", "remote.origin.pushurl", allowed=(0, 1)).stdout.splitlines()
    if origin != [remote] or push_urls not in ([], [remote]):
        raise SyncError("The configured origin does not match the requested GitHub URL.")

    git(config, "fetch", "--no-tags", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*")
    remote_ref = f"refs/remotes/origin/{branch}"
    remote_exists = git(config, "show-ref", "--verify", "--quiet", remote_ref, allowed=(0, 1)).returncode == 0
    local_exists = git(config, "rev-parse", "--verify", "--quiet", "HEAD", allowed=(0, 1)).returncode == 0
    if not local_exists and git(config, "for-each-ref", "refs/remotes/origin").stdout:
        raise SyncError("Remote already has history. Clone it separately and compare settings before importing.")

    git(config, "add", "-f", "-A", "--", ".")
    index = git(config, "ls-files", "--stage", "-z").stdout.split("\0")
    if any(entry.startswith("160000 ") for entry in index):
        raise SyncError("An embedded Git repository prevents a complete configuration backup.")

    changed = git(config, "diff", "--cached", "--quiet", allowed=(0, 1)).returncode == 1
    if changed:
        git(config, "commit", "-m", "Sync Obsidian configuration")
    elif not local_exists:
        return "No configuration files to sync."

    head = git(config, "rev-parse", "HEAD").stdout.strip()
    if remote_exists:
        remote_head = git(config, "rev-parse", remote_ref).stdout.strip()
        if head == remote_head:
            return "Configuration is already up to date."
        try:
            git(config, "-c", "merge.autostash=false", "merge", "--no-edit", remote_ref)
        except SyncError:
            if not (metadata / "MERGE_HEAD").exists():
                raise
            conflicts = git(config, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
            git(config, "merge", "--abort")
            raise SyncError("Merge aborted. Both versions are preserved. Conflicts: " + ", ".join(conflicts)) from None
        if git(config, "rev-parse", "HEAD").stdout.strip() == remote_head:
            return "Pulled remote configuration."

    git(config, "push", "--no-follow-tags", "origin", f"HEAD:refs/heads/{branch}")
    return "Configuration synchronized."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--remote", required=True, help="Dedicated private GitHub repository URL")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--init", action="store_true", help="Initialize the .obsidian checkout")
    args = parser.parse_args()
    if not GITHUB_URL.fullmatch(args.remote):
        parser.error("--remote must be a GitHub HTTPS or SSH URL without embedded credentials")
    try:
        result = sync(args.vault.expanduser().resolve(), args.remote, args.branch, args.init)
    except subprocess.TimeoutExpired as error:
        print(f"Sync stopped: Git {error.cmd[1]} timed out. Retry when GitHub is reachable.", file=sys.stderr)
        return 1
    except (OSError, SyncError) as error:
        print(f"Sync stopped: {error}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
