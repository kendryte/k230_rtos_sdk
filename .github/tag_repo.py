#!/usr/bin/env python3

import os
import sys
import subprocess
import textwrap

def run(cmd, cwd=None, capture_output=True, check=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        universal_newlines=True,
        check=check
    )
    return result.stdout.strip() if capture_output else ""

def tag_exists_local(tag, cwd):
    try:
        run(["git", "rev-parse", tag], cwd)
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
        return run(["git", "log", f"{from_tag}..HEAD", "--oneline", "--pretty=format:* %h %s"], cwd)
    except subprocess.CalledProcessError:
        return ""

def get_remote_url(remote, cwd):
    url = run(["git", "remote", "get-url", remote], cwd)
    return url.replace("git@github.com:", "https://github.com/").replace(".git", "")

def main():
    if len(sys.argv) != 3:
        print("Usage: tag_repo.py <repo-path> <tag-name>")
        sys.exit(1)

    repo_path = os.path.abspath(sys.argv[1])
    tag_name = sys.argv[2]

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"❌ Not a Git repository: {repo_path}")
        sys.exit(1)

    remote_name = 'github' # run(["git", "remote"], repo_path).splitlines()[0]

    print(f"\n📦 Processing repository: {repo_path}")
    print(f"🔖 Tag: {tag_name}")
    print(f"🌐 Remote: {remote_name} ({get_remote_url(remote_name, repo_path)})")

    tag_local = tag_exists_local(tag_name, repo_path)
    tag_remote = tag_exists_remote(tag_name, remote_name, repo_path)

    run(["git", "fetch", "--tags"], repo_path)

    if tag_local and tag_remote:
        print("✅ Tag exists locally and remotely. Pushing to ensure sync...")
        run(["git", "push", remote_name, tag_name], repo_path, capture_output=False)
        return

    if tag_remote and not tag_local:
        print("⬇️  Tag exists on remote but not locally. Fetching...")
        run(["git", "fetch", remote_name, "tag", tag_name], repo_path)
        run(["git", "tag", tag_name, "FETCH_HEAD"], repo_path)
        print("✔️  Tag created locally.")
        return

    if not tag_local and not tag_remote:
        print("🆕 Creating new annotated tag...")

        last_tag = get_last_tag(repo_path)
        if last_tag:
            print(f"ℹ️ Last tag found: {last_tag}")
            log = get_commit_log(last_tag, repo_path)
            compare_url = f"{get_remote_url(remote_name, repo_path)}/compare/{last_tag}...{tag_name}"
            tag_msg = textwrap.dedent(f"""\
                Release: {tag_name}

                **Changes since {last_tag}:**
                FullChangelog: {compare_url}

                {log if log else 'No new commits since last tag.'}
            """)
        else:
            print("ℹ️ No previous tag found.")
            tag_msg = f"Release: {tag_name}\n\nInitial release."

        run(["git", "tag", "-a", tag_name, "-m", tag_msg], repo_path)
        print("✔️ Tag created locally.")

    print("🚀 Pushing tag to remote...")
    run(["git", "push", remote_name, tag_name], repo_path, capture_output=False)
    print("✔️ Successfully pushed tag.")

if __name__ == "__main__":
    main()
