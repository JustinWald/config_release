import subprocess
from pathlib import Path
import argparse
import re
from datetime import datetime

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Config release script.")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path.cwd(),
        help="Path to the repository (default: current working directory).",
    )
    return parser.parse_args()


def parse_project_metadata(changelog_file):
    """Extract customer and project names from the changelog."""
    METADATA_PATTERN = r"\*\*Customer Name:\*\* `(?P<customer_name>\w+)`\n\*\*Project Name:\*\* `(?P<project_name>\w+)`"

    with open(changelog_file, "r") as f:
        changelog = f.read()

    match = re.match(METADATA_PATTERN, changelog)

    if not match:
        raise ValueError("Customer or Project name not found in the changelog.")
    customer_name, project_name = match.groups()
    return customer_name, project_name


def read_latest_version(changelog_file):
    """Read the latest version from the changelog."""
    VERSION_PATTERN = r"## v(?P<version>\d+\.\d+\.\d+)"

    if not changelog_file.exists():
        raise FileNotFoundError("CHANGELOG.md not found. Unable to determine the latest version.")

    with open(changelog_file, "r") as f:
        lines = f.readlines()

    version = '0.0.0'
    for line in lines:
        match = re.match(VERSION_PATTERN, line)
        version = match.group("version") if match else version

    return version


def bump_version(version, bump_type):
    """Increment the version based on the bump type."""
    major, minor, patch = map(int, version.split("."))
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")
    return f"{major}.{minor}.{patch}"


def analyze_commits(repo_path):
    """Analyze commit messages to determine the bump type."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "log", "--pretty=%s", "--since=HEAD~10"],
        capture_output=True,
        text=True,
    )
    commit_messages = result.stdout.split("\n")
    bump_type = "patch"
    for message in commit_messages:
        if "BREAKING CHANGE" in message or message.startswith("feat!"):
            return "major"
        elif message.startswith("feat"):
            bump_type = "minor"
    return bump_type


def generate_changelog(repo_path, changelog_file, new_version):
    """Generate a changelog from recent commits."""
    timestamp = datetime.now().strftime("%b %d, %Y, %I:%M:%S %p")
    result = subprocess.run(
        ["git", "-C", str(repo_path), "log", "--pretty=%B", "-1"],
        capture_output=True,
        text=True,
    )
    change_description = result.stdout.strip()
    with open(changelog_file, "a") as f:
        f.write(f"## {new_version} - {timestamp}\n")
        f.write(change_description)
        f.write("\n\n")


def amend_commit_with_changelog(repo_path, changelog_file):
    """Amend the last commit to include the updated changelog."""
    subprocess.run(["git", "-C", str(repo_path), "add", str(changelog_file)])
    subprocess.run(["git", "-C", str(repo_path), "commit", "--amend", "--no-edit"])


def tag_version(repo_path, prefix, new_version):
    """Tag the repository with the new version and push it."""
    # Tag the version locally
    tag_name = f"{prefix}/{new_version}"
    subprocess.run(["git", "-C", str(repo_path), "tag", tag_name])


def main():
    args = parse_arguments()
    repo_path = args.repo_path
    changelog_file = repo_path / "CHANGELOG.md"

    if not changelog_file.exists():
        raise FileNotFoundError("CHANGELOG.md not found. Cannot proceed without changelog.")

    # Parse customer and project metadata
    customer_name, project_name = parse_project_metadata(changelog_file)
    prefix = f"{customer_name}/{project_name}"

    # Determine the current version from the changelog
    current_version = read_latest_version(changelog_file)

    # Determine the type of version bump based on commits
    bump_type = analyze_commits(repo_path)

    # Calculate the new version
    new_version = bump_version(current_version, bump_type)

    # Update the changelog with the new version
    generate_changelog(repo_path, changelog_file, new_version)

    # Amend the last commit to include the updated changelog
    amend_commit_with_changelog(repo_path, changelog_file)

    # Tag the repository and push the tag
    tag_version(repo_path, prefix, new_version)

    print(f"Released version: {prefix}/{new_version}")


if __name__ == "__main__":
    main()
