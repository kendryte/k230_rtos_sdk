#!/usr/bin/env python3
"""
Tag the two SDK root repos with a plain version tag (e.g. v1.6, v0.8).

These repos are the top-level SDK entries that get tagged WITHOUT an sdk
prefix — unlike the sub-repos handled by release.py which use canmv-vX.Y
or rtos-vX.Y names.

Usage:
    tag_repo.py <version> [repo-path ...] [--remote NAME] [--dry-run]

Examples:
    tag_repo.py v1.6 . src/canmv              # tag both SDK repos
    tag_repo.py v0.8 .                         # tag rtos SDK repo only
    tag_repo.py v1.6 src/canmv --dry-run       # preview
"""

import argparse
import os
import subprocess
import sys
import textwrap

# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_REMOTE = "github"

# ─── Colors ───────────────────────────────────────────────────────────────────

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
NC = "\033[0m"

# ─── Git Helpers ──────────────────────────────────────────────────────────────

def run(cmd, cwd=None, capture_output=True, check=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        universal_newlines=True,
        check=check,
    )
    return result.stdout.strip() if capture_output else ""


def get_remote_url(remote, cwd):
    url = run(["git", "remote", "get-url", remote], cwd)
    return url.replace("git@github.com:", "https://github.com/").replace(".git", "")


def tag_exists_local(tag, cwd):
    try:
        run(["git", "rev-parse", f"refs/tags/{tag}"], cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def tag_exists_remote(tag, remote, cwd):
    try:
        output = run(["git", "ls-remote", "--tags", remote], cwd)
        return any(line.endswith(f"refs/tags/{tag}") for line in output.splitlines())
    except subprocess.CalledProcessError:
        return False


def get_last_tag(cwd):
    try:
        return run(["git", "describe", "--tags", "--abbrev=0"], cwd)
    except subprocess.CalledProcessError:
        return None


def get_commit_log(from_tag, cwd):
    try:
        return run(
            ["git", "log", f"{from_tag}..HEAD", "--oneline", "--pretty=format:* %h %s"],
            cwd,
        )
    except subprocess.CalledProcessError:
        return ""

# ─── Tag Operation ────────────────────────────────────────────────────────────

def create_tag(repo_path, tag_name, remote, dry_run=False):
    """Create and push an annotated tag for a single repo."""
    print(f"🔖 Tag: {tag_name}")
    print(f"🌐 Remote: {remote} ({get_remote_url(remote, repo_path)})")

    local = tag_exists_local(tag_name, repo_path)
    on_remote = tag_exists_remote(tag_name, remote, repo_path)

    if not dry_run:
        run(["git", "fetch", "--tags"], repo_path)

    if local and on_remote:
        print("✅ Tag exists locally and remotely. Pushing to ensure sync...")
        if not dry_run:
            run(["git", "push", remote, tag_name], repo_path, capture_output=False)
        return True

    if on_remote and not local:
        print("⬇️  Tag exists on remote but not locally. Fetching...")
        if not dry_run:
            run(["git", "fetch", remote, "tag", tag_name], repo_path)
            run(["git", "tag", tag_name, "FETCH_HEAD"], repo_path)
        print("✔️  Tag created locally.")
        return True

    if not local and not on_remote:
        print("🆕 Creating new annotated tag...")

        last_tag = get_last_tag(repo_path)
        if last_tag:
            print(f"ℹ️  Last tag found: {last_tag}")
            log = get_commit_log(last_tag, repo_path)
            compare_url = f"{get_remote_url(remote, repo_path)}/compare/{last_tag}...{tag_name}"
            tag_msg = textwrap.dedent(f"""\
                Release: {tag_name}

                **Changes since {last_tag}:**
                FullChangelog: {compare_url}

                {log if log else 'No new commits since last tag.'}
            """)
        else:
            print("ℹ️  No previous tag found.")
            tag_msg = f"Release: {tag_name}\n\nInitial release."

        if dry_run:
            print(f"  Tag message preview:\n{textwrap.indent(tag_msg, '    ')}")
        else:
            run(["git", "tag", "-a", tag_name, "-m", tag_msg], repo_path)
        print("✔️  Tag created locally.")

    print("🚀 Pushing tag to remote...")
    if not dry_run:
        run(["git", "push", remote, tag_name], repo_path, capture_output=False)
    print("✔️  Successfully pushed tag.")
    return True

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Tag SDK root repos with a plain version tag.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s v1.6 . src/canmv
              %(prog)s v0.8 . --dry-run
              %(prog)s v1.6 src/canmv --remote origin
        """),
    )
    parser.add_argument("version", help="version tag, e.g. v1.6")
    parser.add_argument("repos", nargs="+", help="repo paths to tag")
    parser.add_argument(
        "--remote", default=DEFAULT_REMOTE,
        help=f"git remote name (default: {DEFAULT_REMOTE})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="preview actions without making git changes",
    )

    args = parser.parse_args()

    if args.dry_run:
        print(f"\n{YELLOW}🔍 DRY RUN — no git changes will be made{NC}\n")

    total = len(args.repos)
    success = 0
    failed = 0

    for idx, rel_path in enumerate(args.repos, 1):
        repo_path = os.path.abspath(rel_path)

        print("════════════════════════════════════════════════════════════════")
        print(f"{BOLD}[{idx}/{total}] {repo_path}{NC}")
        print("════════════════════════════════════════════════════════════════")

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir) and not os.path.isfile(git_dir):
            print(f"{RED}❌ Not a Git repository: {repo_path}{NC}")
            failed += 1
            continue

        try:
            create_tag(repo_path, args.version, args.remote, dry_run=args.dry_run)
            print(f"\n{GREEN}✅ Success{NC}\n")
            success += 1
        except subprocess.CalledProcessError as exc:
            print(f"\n{RED}❌ Failed (exit code {exc.returncode}){NC}\n")
            failed += 1
        except Exception as exc:
            print(f"\n{RED}❌ Error: {exc}{NC}\n")
            failed += 1

    # ── Summary ──────────────────────────────────────────────────────────
    print("════════════════════════════════════════════════════════════════")
    print(f"{BOLD}TAGGING COMPLETED — {success}/{total} succeeded{NC}")
    if args.dry_run:
        print(f"{YELLOW}🔍 DRY RUN — no changes were made{NC}")
    print("════════════════════════════════════════════════════════════════")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
