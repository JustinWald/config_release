import subprocess
from pathlib import Path
import argparse
import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def parse_arguments():
    """Parse command-line arguments."""
    logging.info("Parsing command-line arguments.")
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
    logging.info("Parsing project metadata from CHANGELOG.md.")
    METADATA_PATTERN = r"\*\*Customer Name:\*\* `(?P<customer_name>\w+)`\n\*\*Project Name:\*\* `(?P<project_name>\w+)`"

    try:
        with open(changelog_file, "r") as f:
            changelog = f.read()

        match = re.search(METADATA_PATTERN, changelog)
        if not match:
            raise ValueError("Customer or Project name not found in the changelog.")

        customer_name, project_name = match.group("customer_name"), match.group("project_name")
        logging.info(f"Extracted metadata: Customer Name = {customer_name}, Project Name = {project_name}")
        return customer_name, project_name
    except Exception as e:
        logging.error(f"Error parsing project metadata: {e}")
        raise


def read_latest_version(changelog_file):
    """Read the latest version from the changelog."""
    logging.info("Reading the latest version from CHANGELOG.md.")
    VERSION_PATTERN = r"## v(?P<version>\d+\.\d+\.\d+)"

    if not changelog_file.exists():
        logging.error("CHANGELOG.md not found. Unable to determine the latest version.")
        raise FileNotFoundError("CHANGELOG.md not found.")

    with open(changelog_file, "r") as f:
        lines = f.readlines()

    for line in lines:
        match = re.match(VERSION_PATTERN, line)
        if match:
            version = match.group("version")
            logging.info(f"Latest version found: {version}")
            return version

    logging.warning("No version found in CHANGELOG.md. Defaulting to '0.0.0'.")
    return "0.0.0"


def bump_version(version, bump_type):
    """Increment the version based on the bump type."""
    logging.info(f"Bumping version {version} with bump type '{bump_type}'.")
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
        logging.error(f"Invalid bump type: {bump_type}")
        raise ValueError(f"Unknown bump type: {bump_type}")
    new_version = f"{major}.{minor}.{patch}"
    logging.info(f"New version calculated: {new_version}")
    return new_version


def analyze_commits(repo_path):
    """Analyze commit messages to determine the bump type."""
    logging.info("Analyzing commit messages for version bump determination.")
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--pretty=%s", "--since=HEAD~10"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit_messages = result.stdout.split("\n")
        bump_type = "patch"
        for message in commit_messages:
            if "BREAKING CHANGE" in message or message.startswith("feat!"):
                logging.info("Detected 'major' bump from commit message.")
                return "major"
            elif message.startswith("feat"):
                bump_type = "minor"
        logging.info(f"Bump type determined: {bump_type}")
        return bump_type
    except subprocess.CalledProcessError as e:
        logging.error(f"Error analyzing commits: {e}")
        raise


def generate_changelog(repo_path, changelog_file, new_version):
    """Generate a changelog from recent commits."""
    logging.info(f"Generating changelog for version {new_version}.")
    timestamp = datetime.now().strftime("%b %d, %Y, %I:%M:%S %p")
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--pretty=format:- %s", "--since=HEAD~10"],
            capture_output=True,
            text=True,
            check=True,
        )
        change_description = result.stdout.strip()
        with open(changelog_file, "a") as f:
            f.write(f"## v{new_version} - {timestamp}\n")
            f.write(change_description)
            f.write("\n\n")
        logging.info("Changelog updated successfully.")
    except Exception as e:
        logging.error(f"Error generating changelog: {e}")
        raise


def amend_commit_with_changelog(repo_path, changelog_file):
    """Amend the last commit to include the updated changelog."""
    try:
        # Stage the updated changelog file
        subprocess.run(["git", "-C", str(repo_path), "add", str(changelog_file)], check=True)

        # Get the original committer name and email
        committer_name = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--pretty=format:%an"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        committer_email = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--pretty=format:%ae"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Amend the commit using the original committer identity
        subprocess.run(
            ["git", "-C", str(repo_path), "commit", "--amend", "--no-edit"],
            check=True,
            env={
                **os.environ,
                "GIT_COMMITTER_NAME": committer_name,
                "GIT_COMMITTER_EMAIL": committer_email,
            },
        )
        logging.info("Changelog added to the last commit successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error amending the commit: {e}")
        raise


def tag_version(repo_path, prefix, new_version):
    """Tag the repository with the new version."""
    logging.info(f"Tagging repository with version {new_version} (prefix: {prefix}).")
    tag_name = f"{prefix}/v{new_version}"
    try:
        subprocess.run(["git", "-C", str(repo_path), "tag", tag_name], check=True)
        logging.info(f"Tag {tag_name} created successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error creating tag: {e}")
        raise


def main():
    logging.info("Starting the Config Release Script.")
    args = parse_arguments()
    repo_path = args.repo_path
    changelog_file = repo_path / "CHANGELOG.md"

    if not changelog_file.exists():
        logging.error("CHANGELOG.md not found. Cannot proceed without changelog.")
        raise FileNotFoundError("CHANGELOG.md not found.")

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

    # Tag the repository
    tag_version(repo_path, prefix, new_version)

    logging.info(f"Released version: {prefix}/v{new_version}")


if __name__ == "__main__":
    main()
