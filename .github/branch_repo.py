#!/usr/bin/env python3

import os
import sys
import subprocess

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

def get_remote_url(remote, cwd):
    url = run(["git", "remote", "get-url", remote], cwd)
    return url.replace("git@github.com:", "https://github.com/").replace(".git", "")

def main():
    if len(sys.argv) != 3:
        print("Usage: branch_repo.py <repo-path> <branch-name>")
        sys.exit(1)

    repo_path = os.path.abspath(sys.argv[1])
    branch_name = sys.argv[2]

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"❌ Not a Git repository: {repo_path}")
        sys.exit(1)

    remote_name = 'github' # run(["git", "remote"], repo_path).splitlines()[0]

    print(f"\n📦 Processing repository: {repo_path}")
    print(f"🌿 Branch: {branch_name}")
    print(f"🌐 Remote: {remote_name} ({get_remote_url(remote_name, repo_path)})")

    branch_local = branch_exists_local(branch_name, repo_path)
    branch_remote = branch_exists_remote(branch_name, remote_name, repo_path)

    run(["git", "fetch", remote_name], repo_path)

    if branch_local and branch_remote:
        print("✅ Branch exists locally and remotely. Pushing to ensure sync...")
        run(["git", "push", remote_name, branch_name], repo_path, capture_output=False)
        return

    if branch_remote and not branch_local:
        print("⬇️  Branch exists on remote but not locally. Fetching...")
        run(["git", "checkout", "-b", branch_name, f"{remote_name}/{branch_name}"], repo_path)
        print("✔️  Branch created locally tracking remote.")
        return

    if not branch_local and not branch_remote:
        print("🆕 Creating new branch...")
        run(["git", "checkout", "-b", branch_name], repo_path)
        print("✔️ Branch created locally.")

    print("🚀 Pushing branch to remote...")
    run(["git", "push", "-u", remote_name, branch_name], repo_path, capture_output=False)
    print("✔️ Successfully pushed branch.")

if __name__ == "__main__":
    main()
