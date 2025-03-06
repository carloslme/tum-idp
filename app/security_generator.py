# security_generator.py
import sys
import json
import logging
from pathlib import Path
import shutil
import tempfile
import google.generativeai as genai

# Importing utility functions from utils.py
from utils.utils import (
    setup_logging,
    configure_genai_api,
    get_local_repo_path,
    get_remote_repo_url,
    clone_remote_repo,
    convert_file_to_txt,          # Updated import
    upload_file_to_gemini
)

# ------------------------------ Configuration ------------------------------

API_KEY = "apikey"  # Replace with your actual Gemini API key 
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"   # Replace with your desired Gemini model

# ------------------------------ Prompt Definition ------------------------------

PROMPT = """
I am working on creating a `SECURITY.md` file for my GitHub repository. I want you to create a `SECURITY.md` that follows the sections below and uses information from the `README.md` file. Ensure that all website links are formatted in Markdown as "[text...](http://...)". The output should be in Markdown.

## Summary
Provide a brief overview of the security policy and its importance to the project.

## Reporting Vulnerabilities
Please do not report security vulnerabilities through public issues, discussions, or pull requests.
Instead, report them using one of the following methods:
- Contact the [security team](mailto:security@example.com) via email. *(Replace with the actual contact information from your `README.md`.)*

**Please include as much of the information listed below as possible to help us better understand and resolve the issue:**

- **Type of issue:** (e.g., buffer overflow, SQL injection, cross-site scripting)
- **Affected version(s):**
- **Impact of the issue:** Including how an attacker might exploit the issue
- **Step-by-step instructions to reproduce the issue:**
- **Location of the affected source code:** (tag/branch/commit or direct URL)
- **Full paths of source file(s) related to the issue:**
- **Configuration required to reproduce the issue:**
- **Log files related to the issue:** (if possible)
- **Proof-of-concept or exploit code:** (if possible)

This information will help us triage your report more quickly.

## Disclosure Policy
We follow a responsible disclosure policy. Upon receiving a vulnerability report, we will acknowledge it within 7 days and work to resolve the issue within two weeks. Details of fixed vulnerabilities will be publicly disclosed once the fix is released.

## Preferred Languages
We prefer all communications to be in English.

## License
Include the license information from the `LICENSE` file or `README.md`.
"""

# ------------------------------ Helper Functions ------------------------------

def generate_security_md(readme_file, license_file, prompt: str, model_name: str) -> str:
    """
    Generates the SECURITY.md content using the Gemini model.
    """
    try:
        model = genai.GenerativeModel(model_name)
        logging.info(f"Initialized model: {model_name}")

        # Combine the uploaded files and prompt
        inputs = [
            readme_file,
            "\n\n",
            license_file,
            "\n\n",
            prompt
        ]

        response = model.generate_content(inputs)
        security_md_content = response.text.strip()
        logging.info("Successfully generated SECURITY.md content.")
        return security_md_content
    except Exception as e:
        logging.error(f"Failed to generate SECURITY.md: {e}")
        sys.exit(1)

def save_output(content: str, output_path: Path):
    """
    Saves the generated SECURITY.md content to the specified path.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"SECURITY.md successfully written to {output_path}")
        print(f"SECURITY.md successfully generated at {output_path}")
    except Exception as e:
        logging.error(f"Failed to write SECURITY.md: {e}")
        sys.exit(1)

def get_repository_selection() -> dict:
    """
    Prompts the user to select between a local or remote repository.
    Returns a dictionary with the selection type and corresponding path or URL.
    """
    while True:
        choice = input("Do you want to use a (1) Local repository or (2) Remote repository? Enter 1 or 2: ").strip()
        if choice == '1':
            repo_path_input = input("Enter the path to your local repository: ").strip()
            repo_path = get_local_repo_path(repo_path_input)
            return {'type': 'local', 'path': repo_path}
        elif choice == '2':
            repo_url_input = input("Enter the URL of the remote repository: ").strip()
            repo_url = get_remote_repo_url(repo_url_input)
            return {'type': 'remote', 'url': repo_url}
        else:
            print("Invalid input. Please enter 'local' or 'remote'.")

# ------------------------------ Main Execution ------------------------------

def main():
    # Define log file path
    script_dir = Path(__file__).parent.resolve()
    log_file = script_dir / "security_generator.log"
    setup_logging(log_file)
    logging.info("Starting SECURITY.md generation process.")

    # Step 0: Get repository selection from user
    repo_selection = get_repository_selection()

    if repo_selection['type'] == 'local':
        repo_path = repo_selection['path']
        logging.info(f"Repository type: Local")
    else:
        repo_url = repo_selection['url']
        repo_path = clone_remote_repo(repo_url)
        logging.info(f"Repository type: Remote, cloned to {repo_path}")

    # Define file paths based on repository location
    README_PATH = repo_path / "README.md"       # Original README.md
    LICENSE_PATH = repo_path / "LICENSE"        # Original LICENSE without extension

    # Determine output path
    if repo_selection['type'] == 'local':
        OUTPUT_PATH = repo_path / "SECURITY.md"
    else:
        OUTPUT_PATH = script_dir / "SECURITY.md"

    # Step 1: Configure Google Gemini API
    configure_genai_api(API_KEY)  # Replace with your actual API key

    # Step 2: Create a temporary directory for .txt files
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        logging.info(f"Created temporary directory at {temp_dir}")

        # Step 3: Convert README and LICENSE to .txt using the new function
        readme_txt_path = temp_dir / "README.txt"
        license_txt_path = temp_dir / "LICENSE.txt"

        convert_file_to_txt(README_PATH, readme_txt_path)       # Updated conversion
        convert_file_to_txt(LICENSE_PATH, license_txt_path)     # Updated conversion

        # Step 4: Upload the .txt files
        readme_file = upload_file_to_gemini(readme_txt_path)
        license_file = upload_file_to_gemini(license_txt_path)

        # Step 5: Use the embedded prompt
        prompt = PROMPT

        # Step 6: Generate SECURITY.md content
        security_md_content = generate_security_md(readme_file, license_file, prompt, MODEL_NAME)

        # Step 7: Save the generated SECURITY.md
        save_output(security_md_content, OUTPUT_PATH)

    logging.info("SECURITY.md generation process completed successfully.")

    # If remote repo was cloned, clean up the temporary cloned repository
    if repo_selection['type'] == 'remote' and repo_path.exists():
        try:
            shutil.rmtree(repo_path)
            logging.info(f"Cleaned up temporary cloned repository at {repo_path}")
        except Exception as e:
            logging.warning(f"Failed to clean up temporary repository at {repo_path}: {e}")
            print(f"Warning: Failed to clean up temporary repository at {repo_path}. You may need to delete it manually.")

if __name__ == "__main__":
    main()
