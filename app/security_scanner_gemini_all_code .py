import git
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

# Import necessary functions from utils.py
from utils.utils import (
    setup_logging,
    configure_genai_api,
    get_local_repo_path,
    get_remote_repo_url,
    clone_remote_repo,
    convert_repo_to_txt,
    upload_file_to_gemini,
    convert_file_to_txt
)


API_KEY = os.getenv("GEMINI_API_KEY")  # Correctly retrieve your Gemini API key from environment variables
MODEL_NAME = "gemini-1.5-flash-002"        # Replace with your desired Gemini model

SECURITY_OUTPUT_FILE = "security_vulnerabilities.json"  # JSON file for security analysis results
RATE_LIMIT_SECONDS = 12  # Wait time (in seconds) between each Gemini API request

# List of code-related file extensions to scan
CODE_FILE_EXTENSIONS = [
    '.py', '.js', '.java', '.c', '.cpp', '.rb', '.go', '.ts', '.cs',
    '.php', '.swift', '.kt', '.rs', '.scala', '.sh', '.bat', '.ps1',
    '.html', '.css', '.xml', '.json', '.yaml', '.yml'
]


def get_repo_source() -> dict:
    """
    Prompts the user to specify whether to use a local repository directory or a remote repository URL.
    Returns a dictionary with the source type and path or URL.
    """
    while True:
        source_type = input("Do you want to provide a (1) Local repository directory or (2) Remote repository URL? Enter 1 or 2: ").strip()
        if source_type == '1':
            repo_path = input("Enter the path to your local repository directory: ").strip()
            try:
                repo = get_local_repo_path(repo_path)
                return {'type': 'local', 'path': repo}
            except (FileNotFoundError, NotADirectoryError) as e:
                print(f"Error: {e}")
                continue
        elif source_type == '2':
            repo_url = input("Enter the remote repository URL: ").strip()
            try:
                validated_url = get_remote_repo_url(repo_url)
                return {'type': 'remote', 'url': validated_url}
            except ValueError as e:
                print(f"Error: {e}")
                continue
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


def extract_code_files(repo: git.Repo) -> list:
    """
    Identifies all code-related files in the repository based on predefined file extensions.
    """
    code_files = []
    for root, dirs, files in os.walk(repo.working_tree_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in CODE_FILE_EXTENSIONS):
                file_path = Path(root) / file
                code_files.append(file_path)
    return code_files

def generate_security_report(file_content: str, file_path: str, model=None) -> dict:
    """
    Uses Gemini to analyze the given file content for security vulnerabilities.
    Returns a dictionary with findings or an error if parsing fails.
    """
    prompt = f"""
    You are a security expert analyzing the following code for potential security vulnerabilities. Identify any issues related to:
    
    Hardcoded API keys, passwords, or secrets
    
    Default login credentials
    
    Insecure data handling
    
    Any other security-related concerns
    
    File: {file_path}
    
    Code: {file_content}
    
    Instructions:
    
    List each identified vulnerability with a brief description.
    
    For each vulnerability, suggest remediation steps.
    
    Assign a threat level to each vulnerability: none, low, medium, high, or critical.
    
    Identify the corresponding CWE (Common Weakness Enumeration) number and name for each vulnerability.
    
    Present the findings in a structured JSON format with the following fields:
    
    "vulnerability_name": Name of the vulnerability
    
    "vulnerability_description": Detailed description of the issue
    
    "location": Line number or snippet where the issue is found
    
    "remediation": Suggested fix or improvement
    
    "threat_level": "none", "low", "medium", "high", or "critical"
    
    "cwe_number": CWE identifier number (e.g., "CWE-79")
    
    "cwe_name": CWE descriptive name (e.g., "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')")
    
    Response Format:
    
    Provide only the JSON data without any additional formatting, text, or markdown.
    
    Do not include triple backticks or any other code block syntax.
    """
    
    if model is None:
        # Use global gemini_model if no model is passed
        global gemini_model
        model = gemini_model
    
    try:
        # Generate content using Gemini
        response = model.generate_content(prompt)
        security_report = response.text.strip()
    
        # Enforce rate limit after the request
        time.sleep(RATE_LIMIT_SECONDS)
    
        # Clean the response by removing triple backticks if present
        if security_report.startswith("```") and security_report.endswith("```"):
            # Remove the starting and ending triple backticks and any language identifier
            lines = security_report.split('\n')
            if len(lines) >= 3:
                security_report = '\n'.join(lines[1:-1])
            else:
                # Unexpected format
                logging.error(f"Unexpected format for security report for {file_path}. Response: {security_report}")
                return {"error": "Unexpected response format from Gemini."}
    
        # Attempt to parse JSON from the response
        try:
            security_data = json.loads(security_report)
            # Ensure each vulnerability has the required fields
            for vuln in security_data:
                if 'vulnerability_name' not in vuln:
                    vuln['vulnerability_name'] = "Unknown Vulnerability"
                if 'vulnerability_description' not in vuln:
                    vuln['vulnerability_description'] = "No description provided."
                if 'location' not in vuln:
                    vuln['location'] = "Unknown location."
                if 'remediation' not in vuln:
                    vuln['remediation'] = "No remediation provided."
                if 'threat_level' not in vuln:
                    vuln['threat_level'] = "none"  # Default to none if not provided
                else:
                    # Ensure threat_level is one of the accepted values
                    if vuln['threat_level'].lower() not in ['none', 'low', 'medium', 'high', 'critical']:
                        vuln['threat_level'] = "none"
                if 'cwe_number' not in vuln:
                    vuln['cwe_number'] = "CWE-Unknown"
                if 'cwe_name' not in vuln:
                    vuln['cwe_name'] = "Unknown CWE Name"
            return security_data
        except json.JSONDecodeError:
            logging.error(f"Failed to parse security report for {file_path}. Response: {security_report}")
            return {"error": "Invalid JSON response from Gemini."}
    
    except genai.Error as e:
        logging.error(f"API Error generating security report for {file_path}: {e}")
        print(f"Error generating security report for {file_path}: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Unexpected error generating security report for {file_path}: {e}")
        print(f"Unexpected error for {file_path}: {e}")
        return {"error": str(e)}

def analyze_security(repo: git.Repo, repo_name: str) -> dict:
    """
    Analyzes the repository for security vulnerabilities using Gemini.
    Returns a dictionary with findings for each file and a threat summary.
    """
    security_output = {}
    code_files = extract_code_files(repo)
    
    if not code_files:
        logging.info("No code-related files detected for security analysis.")
        print("No code-related files detected for security analysis.")
        return security_output
    
    threat_summary = {"none": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    
    for file_path in tqdm(code_files, desc="Analyzing security vulnerabilities"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            security_output[get_relative_path(repo, file_path, repo_name)] = {"error": f"Failed to read file: {e}"}
            continue
    
        # Generate a security report for each file
        security_report = generate_security_report(file_content, get_relative_path(repo, file_path, repo_name))
        security_output[get_relative_path(repo, file_path, repo_name)] = security_report
    
        # Update threat summary
        if isinstance(security_report, list):
            for vuln in security_report:
                level = vuln.get("threat_level", "none").lower()
                if level in threat_summary:
                    threat_summary[level] += 1
                else:
                    threat_summary["none"] += 1  # Default to none if unknown level
        elif isinstance(security_report, dict) and "error" in security_report:
            continue  # Skip counting if there's an error
    
    # Add threat summary to the output
    security_output["threat_summary"] = threat_summary
    
    logging.info("Security analysis completed.")
    print("Security analysis completed.")
    return security_output

def get_relative_path(repo: git.Repo, file_path: Path, repo_name: str) -> str:
    """
    Returns the relative path of the file with respect to the repository root, prefixed by the repository name.
    Format: repo_name\relative_path
    """
    try:
        relative_path = file_path.relative_to(Path(repo.working_tree_dir))
        return f"{repo_name}\\{relative_path}"
    except ValueError:
        # If the file is not relative to the repo (unlikely), return the original path
        return str(file_path)


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


def main():
    # Define log file path
    script_dir = Path(__file__).parent.resolve()
    log_file = script_dir / "security_scanner.log"
    setup_logging(log_file, log_to_console=True)  # Using imported setup_logging
    logging.info("=== Security Analysis Script Started ===")
    
    # Validate API Key
    if not API_KEY:
        logging.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
        print("Error: Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
        sys.exit(1)
    
    # Configure Gemini API
    try:
        configure_genai_api(API_KEY)  # Using imported configure_genai_api
        global gemini_model
        gemini_model = genai.GenerativeModel(MODEL_NAME)
    except RuntimeError as e:
        logging.error(f"Failed to configure Gemini API: {e}")
        print(f"Error: Failed to configure Gemini API: {e}")
        sys.exit(1)
    
    # Step 1: Get repository source from user
    repo_source = get_repo_source()
    
    # Step 2: Initialize or clone repository
    if repo_source['type'] == 'local':
        repo_path = repo_source['path']
        repo = initialize_local_repo(repo_path)
        temp_dir = None
    else:
        repo_url = repo_source['url']
        try:
            repo_path = clone_remote_repo(repo_url)  # Using imported clone_remote_repo
            repo = initialize_local_repo(repo_path)
            temp_dir = None  # Since utils.clone_remote_repo doesn't return temp_dir
        except RuntimeError as e:
            logging.error(f"Failed to clone repository: {e}")
            print(f"Error: Failed to clone repository: {e}")
            sys.exit(1)
    
    # Extract repository name
    repo_name = repo_path.name  # Corrected line
    
    # Step 3: Analyze security vulnerabilities
    security_output = analyze_security(repo, repo_name)
    
    # Step 4: Write the security vulnerabilities to a JSON file
    security_output_path = script_dir / SECURITY_OUTPUT_FILE
    save_json(security_output, security_output_path, "security vulnerabilities")
    
    # Cleanup temporary directory if cloned from remote
    # Note: Since utils.clone_remote_repo doesn't return temp_dir, cleanup is not needed here
    # If you need temp_dir, consider modifying utils.clone_remote_repo to return it
    
    logging.info("=== Security Analysis Script Completed Successfully ===")
    print("Process completed. Check the log file for details.")

if __name__ == "__main__":
    main()
