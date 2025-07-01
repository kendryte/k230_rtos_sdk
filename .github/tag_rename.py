#!/usr/bin/env python3
import subprocess
import sys

def run(cmd):
    return subprocess.check_output(cmd, universal_newlines=True).strip()

def main():
    if len(sys.argv) != 3:
        print("Usage: rename_git_tag.py <old_tag> <new_tag>")
        sys.exit(1)

    old_tag = sys.argv[1]
    new_tag = sys.argv[2]

    # Get the commit hash pointed to by the old tag
    try:
        commit_hash = run(["git", "rev-list", "-n", "1", old_tag])
    except subprocess.CalledProcessError:
        print(f"Error: Tag '{old_tag}' not found.")
        sys.exit(1)

    # Get the tag message (if annotated)
    try:
        message = run(["git", "for-each-ref", f"refs/tags/{old_tag}", "--format=%(contents)"])
    except subprocess.CalledProcessError:
        message = ""

    print(f"Renaming tag '{old_tag}' -> '{new_tag}' on commit {commit_hash}")

    # Delete old tag
    subprocess.check_call(["git", "tag", "-d", old_tag])

    # Create new tag with same message
    if message:
        subprocess.check_call(["git", "tag", "-a", new_tag, "-m", message, commit_hash])
    else:
        # Lightweight tag if no message
        subprocess.check_call(["git", "tag", new_tag, commit_hash])

    print(f"Tag renamed successfully.")

if __name__ == "__main__":
    main()

