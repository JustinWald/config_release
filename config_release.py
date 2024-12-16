import os
import subprocess

VERSION_FILE = "VERSION"  # Path to your version file
CHANGELOG_FILE = "CHANGELOG.md"  # Path to your changelog file


def read_current_version():
    """Read the current version from the VERSION file."""
    with open(VERSION_FILE, "r") as f:
        return f.read().strip()


def write_new_version(new_version):
    """Write the new version to the VERSION file."""
    with open(VERSION_FILE, "w") as f:
        f.write(new_version)


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


def analyze_commits():
    """Analyze commit messages to determine the bump type."""
    result = subprocess.run(
        ["git", "log", "--pretty=%s", "--since=HEAD~10"], capture_output=True, text=True
    )
    commit_messages = result.stdout.split("\n")
    bump_type = "patch"
    for message in commit_messages:
        if "BREAKING CHANGE" in message or message.startswith("feat!"):
            return "major"
        elif message.startswith("feat"):
            bump_type = "minor"
    return bump_type


def generate_changelog(new_version):
    """Generate a changelog from recent commits."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:- %s", "--since=HEAD~10"], capture_output=True, text=True
    )
    changelog_entries = result.stdout.strip()
    with open(CHANGELOG_FILE, "a") as f:
        f.write(f"## {new_version}\n")
        f.write(changelog_entries)
        f.write("\n\n")


def tag_version(new_version):
    """Tag the repository with the new version."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN is not set in the environment.")

    # Configure Git to use the token
    repo = os.getenv("GITHUB_REPOSITORY")  # Automatically available in GitHub Actions
    remote_url = f"https://{token}@github.com/{repo}.git"

    # Set the remote URL using the token
    subprocess.run(["git", "remote", "set-url", "origin", remote_url])

    # Create and push the tag
    subprocess.run(["git", "tag", f"v{new_version}"])
    subprocess.run(["git", "push", "origin", f"v{new_version}"])


def main():
    current_version = read_current_version()
    bump_type = analyze_commits()
    new_version = bump_version(current_version, bump_type)
    write_new_version(new_version)
    generate_changelog(new_version)
    tag_version(new_version)
    print(f"Released version: {new_version}")


if __name__ == "__main__":
    main()
