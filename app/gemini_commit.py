# gemini_commit.py
import os
import sys
import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from tqdm import tqdm
import google.generativeai as genai
import git

# Importing utility functions from utils.py
from utils.utils import (
    setup_logging,
    configure_genai_api,
    get_local_repo_path,
    get_remote_repo_url,
    clone_remote_repo,
    convert_repo_to_txt,
    upload_file_to_gemini
)

# ------------------------------ Configuration ------------------------------

API_KEY = "AIzaSyDZ_NxfviMdMPJ6ug3zPslWGLaGXrQ5oCU"  # Replace with your actual Gemini API key
MODEL_NAME = "gemini-2.0-flash-exp"   # Replace with your desired Gemini model

ORIGINAL_OUTPUT_FILE = "original_commit_messages.json"  # JSON file for original commit messages
AI_OUTPUT_FILE = "ai_improved_commit_messages.json"     # JSON file for AI-generated commit messages
MAX_DIFF_LENGTH = 1500  # Maximum number of characters for the diff
RATE_LIMIT_SECONDS = 7   # Wait time in seconds between each Gemini API request

# ------------------------------ Helper Functions ------------------------------

def get_repo_source() -> dict:
    """
    Prompts the user to specify whether to use a local repository directory or a remote repository URL.
    Returns a dictionary with the source type and path or URL.
    """
    while True:
        source_type = input("Do you want to provide a (1) Local repository directory or (2) Remote repository URL? Enter 1 or 2: ").strip()
        if source_type == '1':
            repo_path = input("Enter the path to your local repository directory: ").strip()
            repo = Path(repo_path).resolve()
            if not repo.exists():
                logging.error(f"The path '{repo}' does not exist.")
                print(f"Error: The path '{repo}' does not exist.")
                continue
            if not repo.is_dir():
                logging.error(f"The path '{repo}' is not a directory.")
                print(f"Error: The path '{repo}' is not a directory.")
                continue
            return {'type': 'local', 'path': repo}
        elif source_type == '2':
            repo_url = input("Enter the remote repository URL: ").strip()
            if not repo_url:
                logging.error("No URL provided.")
                print("Error: No URL provided.")
                continue
            return {'type': 'remote', 'url': repo_url}
        else:
            print("Invalid input. Please enter 1 for Local or 2 for Remote repository.")
            continue

def initialize_local_repo(repo_path: Path) -> git.Repo:
    """
    Initializes a Git repository object from a local directory.
    """
    try:
        repo = git.Repo(repo_path)
        logging.info(f"Initialized local repository at {repo_path}")
        return repo
    except git.exc.InvalidGitRepositoryError:
        logging.error(f"The directory '{repo_path}' is not a Git repository.")
        print(f"Error: The directory '{repo_path}' is not a Git repository.")
        print("Cannot proceed without a Git repository. Exiting.")
        sys.exit(1)

def get_all_commits(repo: git.Repo) -> list:
    """
    Retrieves all commits in the repository in chronological order.
    """
    try:
        commits = list(repo.iter_commits('--all', reverse=True))
        logging.info(f"Total commits found: {len(commits)}")
        print(f"Total commits found: {len(commits)}")
        return commits
    except Exception as e:
        logging.error(f"Failed to retrieve commits: {e}")
        print(f"Error: Failed to retrieve commits from the repository.")
        sys.exit(1)

def truncate_diff(diff: str, max_length=MAX_DIFF_LENGTH) -> str:
    """
    Truncates the diff if it exceeds the maximum allowed length.
    """
    if len(diff) > max_length:
        return diff[:max_length] + "\n[Diff truncated due to size]"
    return diff

def generate_commit_message(diff: str, commit_hash: str, original_message: str, model=None) -> str:
    """
    Generates an improved commit message using the Gemini model.
    After generating the message, wait 7 seconds to respect the rate limit.
    """
    prompt = f"""
You are a professional developer tasked with enhancing the clarity, specificity, and relevance of commit messages. The improved message should:

1. Clearly explain **why** this change was needed.
2. Clearly explain **what** was done to achieve it.
3. Assign the most appropriate **category** from the predefined list.

**Predefined Commit Categories:**
- feat: Introduces a new feature or functionality.
- fix: Resolves a bug or error.
- build: Changes that affect the build system or dependencies.
- chore: Routine tasks or maintenance (e.g., cleaning up code).
- docs: Changes to documentation only.
- style: Code style changes (e.g., formatting, linting) that do not affect functionality.
- refactor: Code changes that improve structure or readability without altering functionality or fixing a bug. This type is rare. Only use it if the code change is explicitly aimed at improving the codebase's design without introducing new features or fixing bugs.
- test: Adding or modifying tests without changing production code.
- perf: Code changes that improve performance.

**Guidelines for the commit message:**

- **Format:**
  1. Start the subject line with the category enclosed in square brackets, followed by a space.
     - Example: `[Feature] Add user authentication module`
  2. Separate the subject from the body with a blank line.
  3. Do not end the subject line with a period.
  4. Use sentence case for the subject line (capitalize only the first letter and proper nouns).
  5. Use the imperative mood in the subject line (e.g., "Add", "Fix", "Update").
  6. Wrap lines at 72 characters.

- **Content:**
  1. **Subject Line:** Briefly summarizes the change, prefixed with the appropriate category.
  2. **Body:**
     2.1 **Reason for Change:** Provide a concise explanation of the reason for the change.
     2.2 **What was done:** Describe what was changed to achieve the desired outcome.
     2.3 **Impact/Benefits:** (Optional but recommended) Explain the impact or benefits of the change to provide additional context.

  - Avoid unnecessary verbosity and do not include code snippets or stack traces.

Example output:
"[Fix] Fix data synchronization issue in SOC retrieval

Reason for Change: To ensure consistency between Meter and SoC data by aligning their timestamps, preventing discrepancies in displayed values.

What was done: Updated the Rtc class in rtc.py to filter SOC data based on the current timestamp before selecting relevant columns. Modified the data retrieval logic to ensure SOC data matches Meter data timestamps.

Impact/Benefits: This change eliminates data inconsistencies, enhancing data reliability and accuracy in energy market applications. It ensures that users receive consistent and trustworthy data for decision-making."

Original Commit Message:
{original_message}

Code Changes:
{diff}

**Instructions:**
Improve the original commit message based on the above guidelines. Ensure the message is clear, concise, and provides sufficient context about the change without being overly verbose. The output should contain only the improved commit message without any additional text.
"""

    if model is None:
        # If model not passed, use global model
        global gemini_model
        model = gemini_model

    try:
        # Generate content using Gemini
        response = model.generate_content([diff, "\n\n", prompt], stream=False)
        commit_message = response.text.strip()
        # Enforce rate limit after the request
        time.sleep(RATE_LIMIT_SECONDS)
        return commit_message
    except genai.Error as e:
        logging.error(f"API Error generating message for commit {commit_hash}: {e}")
        print(f"Error generating message for commit {commit_hash}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error generating message for commit {commit_hash}: {e}")
        print(f"Unexpected error for commit {commit_hash}: {e}")
        return None

def save_json(data: dict, file_path: Path, description: str):
    """
    Saves a dictionary to a JSON file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Successfully wrote {description} to {file_path}")
        print(f"Successfully wrote {description} to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to {file_path}: {e}")
        print(f"Error writing to {file_path}: {e}")

# ------------------------------ Main Execution ------------------------------

def main():
    # Define log file path
    script_dir = Path(__file__).parent.resolve()
    log_file = script_dir / "improve_commit_messages.log"
    setup_logging(log_file)
    logging.info("=== Commit Messages Improvement Script Started ===")

    # Configure Gemini API
    configure_genai_api(API_KEY)
    global gemini_model
    gemini_model = genai.GenerativeModel(MODEL_NAME)

    # Step 1: Get repository source from user
    repo_source = get_repo_source()

    # Step 2: Initialize or clone repository
    if repo_source['type'] == 'local':
        repo_path = get_local_repo_path(repo_source['path'])
        repo = initialize_local_repo(repo_path)
        temp_dir = None
    else:
        repo_url = get_remote_repo_url(repo_source['url'])
        repo_path = clone_remote_repo(repo_url)
        repo = initialize_local_repo(repo_path)
        temp_dir = repo_path.parent / repo_path.name  # Adjust as per clone_remote_repo's return

    # Step 3: Get all commits
    commits = get_all_commits(repo)

    # Step 4: Collect commit messages
    original_messages = {}
    ai_messages = {}

    # Step 5: Process each commit
    for commit in tqdm(commits, desc="Processing commits"):
        commit_hash = commit.hexsha
        original_message = commit.message.strip() if commit.message else "No original commit message provided."
        original_messages[commit_hash] = original_message

        # Get the diff for this commit
        if commit.parents:
            parent = commit.parents[0]
            try:
                diff = repo.git.diff(parent, commit)
            except Exception as e:
                logging.error(f"Error getting diff for commit {commit_hash[:7]}: {e}")
                print(f"Error getting diff for commit {commit_hash[:7]}: {e}")
                ai_messages[commit_hash] = None
                continue
        else:
            # Initial commit
            try:
                diff = repo.git.diff(commit)
            except Exception as e:
                logging.error(f"Error getting diff for initial commit {commit_hash[:7]}: {e}")
                print(f"Error getting diff for initial commit {commit_hash[:7]}: {e}")
                ai_messages[commit_hash] = None
                continue

        # Truncate the diff if necessary
        truncated_diff = truncate_diff(diff)

        # Generate improved commit message using Gemini with rate limit
        new_message = generate_commit_message(truncated_diff, commit_hash[:7], original_message)

        if new_message:
            ai_messages[commit_hash] = new_message
            logging.info(f"Successfully generated AI commit message for {commit_hash[:7]}")
        else:
            logging.warning(f"Failed to generate AI commit message for {commit_hash[:7]}")
            ai_messages[commit_hash] = None

    # Step 6: Write the original commit messages to a JSON file
    original_output_path = script_dir / ORIGINAL_OUTPUT_FILE
    save_json(original_messages, original_output_path, "original commit messages")

    # Step 7: Write the AI-generated commit messages to a separate JSON file
    ai_output_path = script_dir / AI_OUTPUT_FILE
    save_json(ai_messages, ai_output_path, "AI-generated commit messages")

    # Cleanup temporary directory if cloned from remote
    if temp_dir is not None and temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            logging.info(f"Cleaned up temporary directory {temp_dir}")
        except Exception as e:
            logging.error(f"Failed to clean up temporary directory {temp_dir}: {e}")
            print(f"Error: Failed to clean up temporary directory {temp_dir}. You may need to delete it manually.")

    logging.info("=== Commit Messages Improvement Script Completed Successfully ===")
    print("Process completed. Check the log file for details.")

if __name__ == "__main__":
    main()
