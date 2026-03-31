#!/usr/bin/env python3
"""
Unified release tool for K230 SDK projects.

Usage:
    release.py branch <rtos|canmv> <version> [--remote NAME] [--dry-run]
    release.py tag    <rtos|canmv> <version> [--remote NAME] [--dry-run]

Examples:
    release.py branch rtos v0.8          # create release/rtos-v0.8 branches + manifest
    release.py branch canmv v1.7         # create release/canmv-v1.7 branches + manifest
    release.py tag rtos v0.8             # create v0.8 tags on rtos repos
    release.py tag canmv v1.7 --dry-run  # preview tag creation
"""

import argparse
import os
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET

# ─── Repo Configuration ──────────────────────────────────────────────────────
# (path relative to repo root, github repo name)
# Only repos that actively receive release branches/tags.
# 3rd-party and commit-pinned repos (opensbi, mbedtls, freetype, lvgl, etc.)
# are intentionally excluded.

SHARED_REPOS = [
    (".", "kendryte/k230_rtos_sdk"),
    ("src/uboot/uboot", "canmv-k230/u-boot"),
    ("src/rtsmart/rtsmart", "canmv-k230/rtsmart"),
    ("src/rtsmart/libs", "canmv-k230/k230_rtsmart_lib"),
    ("src/rtsmart/mpp", "canmv-k230/mpp"),
]

RTOS_EXTRA_REPOS = [
    ("src/rtsmart/examples", "canmv-k230/k230_rtsmart_examples"),
]

CANMV_EXTRA_REPOS = [
    ("src/canmv", "kendryte/canmv_k230"),
    # ("src/canmv/resources/ybsdcard", "canmv-k230/ybsdcard"),
]

# Branch: both SDKs include shared repos (unique branch names per SDK)
BRANCH_REPOS = {
    "rtos": SHARED_REPOS + RTOS_EXTRA_REPOS,
    "canmv": SHARED_REPOS + CANMV_EXTRA_REPOS,
}

# Tag: canmv excludes k230_rtos_sdk (it gets the rtos version tag, not canmv)
SHARED_REPOS_NO_SDK = [r for r in SHARED_REPOS if r[0] != "."]
TAG_REPOS = {
    "rtos": SHARED_REPOS + RTOS_EXTRA_REPOS,
    "canmv": SHARED_REPOS_NO_SDK + CANMV_EXTRA_REPOS,
}

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


def branch_exists_local(branch, cwd):
    try:
        run(["git", "show-ref", "--verify", f"refs/heads/{branch}"], cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def branch_exists_remote(branch, remote, cwd):
    try:
        output = run(["git", "ls-remote", "--heads", remote], cwd)
        return f"refs/heads/{branch}" in output
    except subprocess.CalledProcessError:
        return False


def tag_exists_local(tag, cwd):
    try:
        run(["git", "rev-parse", f"refs/tags/{tag}"], cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def tag_exists_remote(tag, remote, cwd):
    try:
        output = run(["git", "ls-remote", "--tags", remote], cwd)
        return f"refs/tags/{tag}" in output
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

# ─── Branch Operation ─────────────────────────────────────────────────────────

def create_branch(repo_path, branch_name, remote, dry_run=False):
    """Create and push a release branch for a single repo."""
    print(f"🌿 Branch: {branch_name}")
    print(f"🌐 Remote: {remote} ({get_remote_url(remote, repo_path)})")

    local = branch_exists_local(branch_name, repo_path)
    on_remote = branch_exists_remote(branch_name, remote, repo_path)

    if not dry_run:
        run(["git", "fetch", remote], repo_path)

    if local and on_remote:
        print("✅ Branch exists locally and remotely. Pushing to ensure sync...")
        if not dry_run:
            run(["git", "push", remote, branch_name], repo_path, capture_output=False)
        return True

    if on_remote and not local:
        print("⬇️  Branch exists on remote but not locally. Fetching...")
        if not dry_run:
            run(["git", "checkout", "-b", branch_name, f"{remote}/{branch_name}"], repo_path)
        print("✔️  Branch created locally tracking remote.")
        return True

    if not local and not on_remote:
        print("🆕 Creating new branch...")
        if not dry_run:
            run(["git", "checkout", "-b", branch_name], repo_path)
        print("✔️  Branch created locally.")

    print("🚀 Pushing branch to remote...")
    if not dry_run:
        run(["git", "push", "-u", remote, branch_name], repo_path, capture_output=False)
    print("✔️  Successfully pushed branch.")
    return True

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

# ─── Manifest Generation ─────────────────────────────────────────────────────

def generate_manifest(sdk, branch_name, repo_root, dry_run=False):
    """
    Generate a release manifest XML by freezing with `repo manifest -r`,
    then updating branched repos' revision to the release branch name.
    """
    branched_paths = {path for path, _ in BRANCH_REPOS[sdk]}

    # Step 1: Use `repo manifest -r` to get a fully frozen manifest
    print("  Running: repo manifest -r")
    try:
        frozen_xml = run(["repo", "manifest", "-r"], cwd=repo_root)
    except subprocess.CalledProcessError:
        print(f"{RED}Error: 'repo manifest -r' failed{NC}")
        return None

    root = ET.fromstring(frozen_xml)

    # Step 2: Update branched repos — replace commit hash with branch name
    branched_projects = []
    frozen_projects = []

    for project in root.findall("project"):
        path = project.get("path", "")
        if path in branched_paths:
            project.set("revision", branch_name)
            # Remove upstream/dest-branch since these track the release branch directly
            for attr in ("upstream", "dest-branch"):
                if attr in project.attrib:
                    del project.attrib[attr]
            branched_projects.append(project)
        else:
            frozen_projects.append(project)

    # Step 3: Reorder — branched first, then frozen, with blank line separator
    for project in branched_projects + frozen_projects:
        root.remove(project)

    for proj in branched_projects:
        proj.tail = "\n  "
        root.append(proj)

    if branched_projects and frozen_projects:
        branched_projects[-1].tail = "\n\n  "

    for proj in frozen_projects:
        proj.tail = "\n  "
        root.append(proj)

    if len(root) > 0:
        root[-1].tail = "\n"

    # Step 4: Output
    version_short = branch_name.split("/")[-1] if "/" in branch_name else branch_name
    manifest_name = version_short.replace("-", "_") + ".xml"
    output_path = os.path.join(repo_root, manifest_name)

    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"

    if dry_run:
        print(f"\n\U0001f4c4 Manifest preview ({manifest_name}):")
        print("\u2500" * 64)
        print(xml_content)
        print("\u2500" * 64)
    else:
        with open(output_path, "w") as f:
            f.write(xml_content)
        print(f"\n\U0001f4c4 Manifest written to: {output_path}")

    return output_path

# ─── Orchestrator ─────────────────────────────────────────────────────────────

def resolve_repos(action, sdk):
    repo_map = BRANCH_REPOS if action == "branch" else TAG_REPOS
    repos = repo_map.get(sdk)
    if repos is None:
        print(f"{RED}Error: Unknown SDK type '{sdk}'. Choose from: {', '.join(repo_map)}{NC}")
        sys.exit(1)
    return repos


def process_repos(action, sdk, name, remote, dry_run, repo_root):
    """
    Run the given action (branch or tag) across all repos for an SDK type.

    Args:
        action: "branch" or "tag"
        sdk: "rtos" or "canmv"
        name: the branch or tag name
        remote: git remote name
        dry_run: if True, skip git write operations
        repo_root: absolute path to the workspace root
    """
    repos = resolve_repos(action, sdk)
    op_fn = create_branch if action == "branch" else create_tag
    op_label = "branching" if action == "branch" else "tagging"

    total = len(repos)
    success = 0
    failed = 0
    skipped = 0
    errors = []

    if dry_run:
        print(f"\n{YELLOW}🔍 DRY RUN — no git changes will be made{NC}\n")

    print(f"{BOLD}Action: {action} | SDK: {sdk} | Name: {name} | Remote: {remote}{NC}")
    print(f"{BOLD}Projects ({total}):{NC}")
    for path, repo_name in repos:
        print(f"  • {repo_name} ({path})")
    print()

    for idx, (rel_path, repo_name) in enumerate(repos, 1):
        abs_path = os.path.normpath(os.path.join(repo_root, rel_path))

        print("════════════════════════════════════════════════════════════════")
        print(f"{BOLD}[{idx}/{total}] {repo_name}{NC}")
        print("════════════════════════════════════════════════════════════════")

        if not os.path.isdir(abs_path):
            print(f"{YELLOW}⚠️  Skipping: directory not found ({rel_path}){NC}")
            skipped += 1
            errors.append(f"{repo_name}: directory not found at '{rel_path}'")
            continue

        git_dir = os.path.join(abs_path, ".git")
        if not os.path.isdir(git_dir) and not os.path.isfile(git_dir):
            print(f"{YELLOW}⚠️  Skipping: not a git repository ({rel_path}){NC}")
            skipped += 1
            errors.append(f"{repo_name}: not a git repository")
            continue

        print(f"📦 {abs_path}")

        try:
            op_fn(abs_path, name, remote, dry_run=dry_run)
            print(f"\n{GREEN}✅ {repo_name} — success{NC}\n")
            success += 1
        except subprocess.CalledProcessError as exc:
            print(f"\n{RED}❌ {repo_name} — failed (exit code {exc.returncode}){NC}\n")
            failed += 1
            errors.append(f"{repo_name}: git command failed (exit code {exc.returncode})")
        except Exception as exc:
            print(f"\n{RED}❌ {repo_name} — error: {exc}{NC}\n")
            failed += 1
            errors.append(f"{repo_name}: {exc}")

    # ── Generate manifest for branch action ──────────────────────────────
    if action == "branch" and failed == 0:
        print("════════════════════════════════════════════════════════════════")
        print(f"{BOLD}Generating release manifest...{NC}")
        print("════════════════════════════════════════════════════════════════")
        generate_manifest(sdk, name, repo_root, dry_run=dry_run)

    # ── Summary ──────────────────────────────────────────────────────────
    print("════════════════════════════════════════════════════════════════")
    print(f"{BOLD}{op_label.upper()} COMPLETED — SUMMARY{NC}")
    print("════════════════════════════════════════════════════════════════")
    print(f"  Total:    {total}")
    print(f"  Success:  {GREEN}{success}{NC}")
    print(f"  Failed:   {RED}{failed}{NC}")
    print(f"  Skipped:  {YELLOW}{skipped}{NC}")

    if errors:
        print(f"\n{BOLD}Issues:{NC}")
        for e in errors:
            print(f"  • {e}")

    if dry_run:
        print(f"\n{YELLOW}🔍 DRY RUN — no changes were made{NC}")

    if failed:
        print(f"\n{RED}💥 {failed} project(s) failed.{NC}")
        return 1
    if skipped:
        print(f"\n{YELLOW}⚠️  {success} succeeded, {skipped} skipped.{NC}")
        return 0
    print(f"\n{GREEN}🎉 All {success} project(s) {op_label.rstrip('ing')}ed successfully!{NC}")
    return 0

# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Unified release tool for K230 SDK projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s branch rtos v0.8
              %(prog)s branch canmv v1.7 --dry-run
              %(prog)s tag rtos v0.8
              %(prog)s tag canmv v1.7 --remote origin
        """),
    )
    parser.add_argument(
        "action", choices=["branch", "tag"], help="operation to perform"
    )
    parser.add_argument(
        "sdk", choices=list(BRANCH_REPOS), help="SDK type (determines repo set)"
    )
    parser.add_argument("version", help="version string, e.g. v0.8")
    parser.add_argument(
        "--remote",
        default=DEFAULT_REMOTE,
        help=f"git remote name (default: {DEFAULT_REMOTE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview actions without making git changes",
    )

    args = parser.parse_args()

    # Derive the ref name
    if args.action == "branch":
        name = f"release/{args.sdk}-{args.version}"
    else:
        name = args.version

    # Resolve repo root: script lives in .github/, root is one level up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    sys.exit(
        process_repos(args.action, args.sdk, name, args.remote, args.dry_run, repo_root)
    )


if __name__ == "__main__":
    main()
