import git
import os
import sys
import json
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path
from tqdm import tqdm
import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Import utility functions from utils.py
from utils.utils import (
    setup_logging,              # Set up logging to file and console
    configure_genai_api,        # Configure the Gemini API with the provided API key
    get_local_repo_path,        # Validate and return a local repository path
    get_remote_repo_url,        # Validate a remote repository URL
    clone_remote_repo,          # Clone a remote repository locally
    convert_repo_to_txt,        # Convert repository content to a text file
    upload_file_to_gemini,      # Upload a file to Gemini (returns a file reference)
    convert_file_to_txt,        # Convert a file to text (if needed)
)

# API key and model settings
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"  # First pass model
SECOND_PASS_MODEL = "gemini-2.0-flash-thinking-exp-01-21"  # Second pass model

# Output file names and repository content file
SECURITY_OUTPUT_FILE = "security_vulnerabilities.json"
IMPROVED_SECURITY_OUTPUT_FILE = "improved_security_vulnerabilities.json"  # For refined vulnerabilities
REPO_CONTENT_FILE = "repo_content.txt"  # Stores entire repository content as text

# Constants for API rate limiting and retry logic
RATE_LIMIT_SECONDS = 12
RATE_LIMIT_SECONDS_SECOND_PASS = 12
MAX_RETRIES = 3
BATCH_SIZE = 5  # Process vulnerabilities in batches

# File extensions to consider as code files
CODE_FILE_EXTENSIONS = [
    ".py", ".js", ".java", ".c", ".cpp", ".rb", ".go", ".ts", ".cs", ".php",
    ".swift", ".kt", ".rs", ".scala", ".sh", ".bat", ".ps1", ".html", ".css",
    ".xml", ".json", ".yaml", ".yml",
]

def get_repo_source() -> dict:
    """
    Prompt the user to choose a repository source.
    Returns a dictionary with either a local path or a remote URL.
    """
    while True:
        source_type = input(
            "Do you want to provide a (1) Local repository directory or (2) Remote repository URL? Enter 1 or 2: "
        ).strip()
        if source_type == "1":
            repo_path = input("Enter the path to your local repository directory: ").strip()
            try:
                repo = get_local_repo_path(repo_path)
                return {"type": "local", "path": repo}
            except (FileNotFoundError, NotADirectoryError) as e:
                print(f"Error: {e}")
                continue
        elif source_type == "2":
            repo_url = input("Enter the remote repository URL: ").strip()
            try:
                validated_url = get_remote_repo_url(repo_url)
                return {"type": "remote", "url": validated_url}
            except ValueError as e:
                print(f"Error: {e}")
                continue
        else:
            print("Invalid input. Please enter 1 for Local or 2 for Remote repository.")

def get_analysis_mode() -> str:
    """
    Prompt the user to choose the analysis mode.
    Option 1: Single-agent analysis – one AI checks your code for vulnerabilities.
    Option 2: Two-agent analysis – a second AI refines the initial results (this may take longer).
    Returns "1" for single-agent or "2" for two-agent.
    """
    while True:
        mode = input(
            "Select analysis mode:\n"
            "1. Single-agent analysis (one AI reviews your code for vulnerabilities).\n"
            "2. Two-agent analysis (a second AI refines the initial results for improved accuracy, which may take longer).\n"
            "Enter 1 or 2: "
        ).strip()
        if mode in ["1", "2"]:
            return mode
        else:
            print("Invalid input. Please enter 1 or 2.")

def initialize_local_repo(repo_path: Path) -> git.Repo:
    """
    Initialize a Git repository object using the provided path.
    Exits if the directory is not a valid Git repository.
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
    Walk through the repository directory and collect files with code-related extensions.
    Returns a list of Path objects.
    """
    code_files = []
    for root, dirs, files in os.walk(repo.working_tree_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in CODE_FILE_EXTENSIONS):
                file_path = Path(root) / file
                code_files.append(file_path)
    return code_files

def extract_json(text: str) -> dict:
    """
    Extract a JSON object from a string that may include markdown formatting.
    Strips code blocks and returns the first valid JSON dictionary.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n```$", "", text, flags=re.IGNORECASE)
    start_idx = text.find("{")
    end_idx = text.rfind("}") + 1
    if start_idx == -1 or end_idx == 0:
        return None
    try:
        return json.loads(text[start_idx:end_idx])
    except json.JSONDecodeError:
        return None

def validate_vulnerability(vuln: dict, file_path: str) -> dict:
    """
    Validate and sanitize a vulnerability report.
    Ensures required fields exist and the threat level is valid.
    """
    validated = {}
    threat_level = vuln.get("threat_level", "code quality issue")
    if isinstance(threat_level, list):
        threat_level = threat_level[0] if threat_level else "code quality issue"
    validated["threat_level"] = str(threat_level).lower()
    valid_levels = ["code quality issue", "low", "medium", "high", "critical"]
    if validated["threat_level"] not in valid_levels:
        validated["threat_level"] = "code quality issue"
    string_fields = {
        "vulnerability_name": "Unknown Vulnerability",
        "vulnerability_description": "No description available",
        "location": "Unknown location",
        "remediation": "No remediation provided",
        "cwe_id": "CWE-Unknown",
        "cwe_name": "Unknown CWE",
    }
    for field, default in string_fields.items():
        value = vuln.get(field)
        if isinstance(value, list):
            value = ", ".join(map(str, value)) if value else default
        validated[field] = str(value) if value else default
    location = validated["location"]
    if "line" in location.lower() and ":" not in location:
        validated["location"] = location.replace("line", "Line ") + ":"
    elif not any(x in location.lower() for x in ["line", "lines", ":"]):
        validated["location"] = f"Code snippet: {location[:100]}..."
    return validated

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(Exception),
)
def generate_security_report(file_content: str, file_path: str, model=None) -> dict:
    """
    Generate a security report for a given file by invoking the Gemini API.
    Returns a dictionary with a "vulnerabilities" key containing a list of reports.
    """
    prompt = f"""
    You are a security expert analyzing the following code for potential security vulnerabilities:

    File: {file_path}
    Code: {file_content}

    Instructions:
    - List each vulnerability with line numbers or code snippets showing exact location.
    - For each vulnerability, include:
      * Vulnerability name
      * Detailed description
      * Exact location (line numbers or code snippet)
      * Suggested remediation steps
      * Threat level (code quality issue/low/medium/high/critical)
      * CWE number and name

    Response Format:
    {{
      "vulnerabilities": [
        {{
          "vulnerability_name": "XSS Vulnerability",
          "vulnerability_description": "Detailed description...",
          "location": "Line 42: user_input = request.GET.get('q')",
          "remediation": "Sanitize input using...",
          "threat_level": "high",
          "cwe_id": "CWE-79",
          "cwe_name": "Cross-site Scripting"
        }}
      ]
    }}
    Provide only the JSON data without any formatting or markdown.
    """
    try:
        model = model or gemini_model
        response = model.generate_content(prompt)
        security_report = response.text.strip()
        logging.debug(f"Raw model response for {file_path}:\n{security_report}")
        security_data = extract_json(security_report)
        if not security_data:
            logging.warning(f"Could not extract valid JSON from response for {file_path}")
            return {"vulnerabilities": []}
        if "vulnerabilities" not in security_data:
            logging.warning(f"No 'vulnerabilities' key found in JSON response for {file_path}")
            return {"vulnerabilities": []}
        vulnerabilities = security_data.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            vulnerabilities = [vulnerabilities]
        processed = []
        for vuln in vulnerabilities:
            try:
                processed.append(validate_vulnerability(vuln, file_path))
            except Exception as e:
                logging.error(f"Invalid vulnerability format in {file_path}: {str(e)}")
                continue
        time.sleep(RATE_LIMIT_SECONDS)
        return processed
    except Exception as e:
        logging.error(f"API Error processing {file_path}: {str(e)}")
        raise

def analyze_security(repo: git.Repo, repo_name: str) -> dict:
    """
    Perform first pass security analysis on the repository.
    Iterates through all code files, generates a report for each,
    and aggregates the findings into a dictionary.
    """
    security_output = {}
    code_files = extract_code_files(repo)
    if not code_files:
        logging.info("No code-related files detected for security analysis.")
        print("No code-related files detected for security analysis.")
        return security_output
    threat_summary = {
        "code quality issue": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }
    for file_path in tqdm(code_files, desc="Analyzing security vulnerabilities"):
        relative_file_path = get_relative_path(repo, file_path, repo_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            security_output[relative_file_path] = {"error": f"Failed to read file: {e}"}
            continue
        try:
            security_report = generate_security_report(file_content, relative_file_path)
            if security_report == {"vulnerabilities": []}:
                security_output[relative_file_path] = []
            elif "error" in security_report and security_report["error"] == "No valid JSON found in response":
                security_output[relative_file_path] = {"error": "No valid JSON found in response"}
            elif isinstance(security_report, list):
                security_output[relative_file_path] = security_report
                for vuln in security_report:
                    if "error" in vuln:
                        continue
                    level = vuln.get("threat_level", "code quality issue")
                    threat_summary[level] = threat_summary.get(level, 0) + 1
            else:
                security_output[relative_file_path] = security_report
        except Exception as e:
            logging.error(f"Final error processing {file_path}: {str(e)}")
            security_output[relative_file_path] = {"error": f"Failed to analyze: {str(e)}"}
    security_output["threat_summary"] = threat_summary
    logging.info("Security analysis completed.")
    return security_output

def get_relative_path(repo: git.Repo, file_path: Path, repo_name: str) -> str:
    """
    Return the file path relative to the repository root, prefixed with the repository name.
    """
    try:
        relative_path = file_path.relative_to(Path(repo.working_tree_dir))
        return f"{repo_name}/{relative_path}"
    except ValueError:
        return str(file_path)

def save_json(data: dict, file_path: Path, description: str):
    """
    Save the provided dictionary as a formatted JSON file.
    Logs the output path and any errors.
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Successfully wrote {description} to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to {file_path}: {e}")

def load_repo_content_to_text(repo: git.Repo, repo_name: str, output_file_path: Path):
    """
    Convert the entire repository content to a single text file.
    If conversion does not return content, attempt to read from the file.
    Returns the repository content as a string.
    """
    try:
        repo_txt_content = convert_repo_to_txt(repo.working_tree_dir, output_file_path)
        logging.info(f"Repository content converted to text and saved at: {output_file_path}")
        if not repo_txt_content:
            with open(output_file_path, "r", encoding="utf-8") as f:
                repo_txt_content = f.read()
        return repo_txt_content
    except Exception as e:
        logging.error(f"Error converting repository to text: {e}")
        print(f"Error: Failed to convert repository to text: {e}")
        return None

def refine_individual_vulnerability(vuln: dict, file_path: str, repo_content: str, uploaded_repo: str, model=None) -> dict:
    """
    Fallback function to refine an individual vulnerability report if the batch response is missing.
    If the API returns a 429 error (quota exhausted), this function waits for RATE_LIMIT_SECONDS
    before retrying. If the API still fails, it returns the original vulnerability with a note.
    Returns a refined vulnerability report as a dictionary.
    """
    fallback_message = "Refinement result missing from batch response, review manually."
    prompt = f"""
    You are a highly skilled security expert reviewing a preliminary security vulnerability report for a code repository.
    The repository has been uploaded to Gemini and is available at the following reference: {uploaded_repo}
    Using the full repository content as context, refine the following vulnerability report:

    File: {file_path}
    Vulnerability Report:
    {json.dumps(vuln, indent=2)}

    Full Repository Content:
    {repo_content}

    Instructions:
    - Determine if the vulnerability is a true positive or a false positive.
    - If true, provide an improved description and update its threat level (critical, high, medium, low, or code quality issue).
    - Output a JSON dictionary with keys:
      - is_false_positive (boolean)
      - vulnerability_name (string)
      - improved_description (string) [if true positive]
      - new_threat_level (string) [if true positive]
    Provide only the JSON output.
    """
    try:
        model = model or gemini_model
        # Explicitly wait before the API call to help respect rate limits
        time.sleep(RATE_LIMIT_SECONDS_SECOND_PASS)
        response = model.generate_content(prompt)
        result = extract_json(response.text.strip())
        if result is None or (fallback_message in result.get("improved_description", "")):
            return {
                "is_false_positive": False,
                "vulnerability_name": vuln.get("vulnerability_name", "Unknown Vulnerability"),
                "improved_description": vuln.get("vulnerability_description", "Original result retained due to quota exhaustion."),
                "new_threat_level": vuln.get("threat_level", "code quality issue"),
                "manual_review": True,
                "note": "Quota exhausted during individual refinement; original result retained."
            }
        return result
    except Exception as e:
        error_str = str(e)
        if "429" in error_str:
            # Wait before giving up if quota error is detected.
            time.sleep(RATE_LIMIT_SECONDS_SECOND_PASS)
            return {
                "is_false_positive": False,
                "vulnerability_name": vuln.get("vulnerability_name", "Unknown Vulnerability"),
                "improved_description": vuln.get("vulnerability_description", "Original result retained due to quota exhaustion."),
                "new_threat_level": vuln.get("threat_level", "code quality issue"),
                "manual_review": True,
                "note": "Quota exhausted during individual refinement; original result retained."
            }
        logging.error(f"Error in individual refinement for {file_path}: {e}")
        return {
            "is_false_positive": False,
            "vulnerability_name": vuln.get("vulnerability_name", "Unknown Vulnerability"),
            "improved_description": "Manual review required (error during individual refinement)",
            "manual_review": True
        }

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(Exception),
)
def refine_vulnerability_report_gemini_batch(vulnerability_batch: dict, repo_content: str, uploaded_repo: str, model=None) -> dict:
    """
    Refine a batch of vulnerability reports using the Gemini API.
    The prompt includes both the full repository content and the uploaded repository reference.
    """
    prompt_vulnerabilities_list = []
    for file_path, vulnerabilities in vulnerability_batch.items():
        for vuln in vulnerabilities:
            prompt_vulnerabilities_list.append({
                "file_path": file_path,
                "vulnerability": vuln,
            })
    prompt_json_input = json.dumps(prompt_vulnerabilities_list, indent=2)
    prompt = f"""
    You are a highly skilled security expert reviewing a batch of preliminary security vulnerability reports for a code repository.
    The repository has been uploaded to Gemini and is available at the following reference: {uploaded_repo}
    Your task is to validate and refine these findings to reduce false positives and improve accuracy.

    Full Repository Content:
    ```text
    {repo_content}
    ```

    Input Vulnerability Reports (JSON List):
    ```json
    {prompt_json_input}
    ```

    Instructions:
    1. Analyze each vulnerability report using the repository content as context.
    2. Determine if each vulnerability is a true positive or a false positive.
    3. If true, optionally update its threat level (critical, high, medium, low, or code quality issue).
    4. Output a JSON dictionary keyed by file paths, where each value is a list of refined vulnerability reports.
       - For false positives: {{ "is_false_positive": true, "vulnerability_name": "[Original Vulnerability Name]" }}
       - For true positives: {{ "is_false_positive": false, "vulnerability_name": "[Original Vulnerability Name]", "improved_description": "A refined description...", "new_threat_level": "updated threat level" }}
    Provide only the JSON response without markdown formatting or explanations.
    """
    try:
        model = model or gemini_model
        response = model.generate_content([uploaded_repo, "\n\n", prompt])
        refinement_report = response.text.strip()
        logging.debug(f"Batch refinement model response:\n{refinement_report}")
        refined_data_batch = extract_json(refinement_report)
        if not refined_data_batch:
            logging.warning("Could not extract valid JSON from batch refinement response.")
            return {}
        return refined_data_batch
    except Exception as e:
        logging.error(f"API Error during batch refinement: {str(e)}")
        return {}

def refine_security_report(security_report: dict, repo_content: str, repo_name: str, model=None, uploaded_repo: str = None) -> dict:
    """
    Refine the initial security report in batches to remove false positives and update threat levels.
    The uploaded_repo reference is included in the prompt for additional context.
    If individual vulnerability results are missing from the batch, the fallback function is used.
    """
    logging.info("=== Entered refine_security_report function ===")
    logging.info(f"Input security_report: {json.dumps(security_report, indent=2)}")
    logging.info(f"repo_content length: {len(repo_content)}")
    improved_security_output = {"threat_summary": {
        "code quality issue": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }}
    file_paths = [key for key in security_report.keys() if key != "threat_summary"]
    valid_levels = ["code quality issue", "low", "medium", "high", "critical"]
    for i in tqdm(range(0, len(file_paths), BATCH_SIZE), desc="Refining Security Report (Batches)"):
        logging.info(f"Starting batch: {i // BATCH_SIZE}")
        batch_files = file_paths[i:i + BATCH_SIZE]
        vulnerability_batch = {}
        for file_path in batch_files:
            vulnerabilities = security_report.get(file_path, [])
            if not vulnerabilities or ("error" in vulnerabilities):
                improved_security_output[file_path] = vulnerabilities if vulnerabilities else []
                continue
            vulnerability_batch[file_path] = vulnerabilities
        try:
            batch_refinement_results = refine_vulnerability_report_gemini_batch(vulnerability_batch, repo_content, uploaded_repo, model=model)
            logging.debug(f"Batch Refinement API Results: {batch_refinement_results}")
            for file_path in batch_files:
                refined_vulnerabilities = []
                original_vulnerabilities = vulnerability_batch.get(file_path, [])
                if not original_vulnerabilities or ("error" in original_vulnerabilities):
                    continue
                file_refined_results = batch_refinement_results.get(file_path, [])
                logging.debug(f"File Refinement Results for {file_path}: {file_refined_results}")
                for index, vuln in enumerate(original_vulnerabilities):
                    if "error" in vuln:
                        refined_vulnerabilities.append(vuln)
                        continue
                    if index < len(file_refined_results):
                        refinement_result = file_refined_results[index]
                    else:
                        # Fallback: refine individual vulnerability
                        refinement_result = refine_individual_vulnerability(vuln, file_path, repo_content, uploaded_repo, model=model)
                    logging.debug(f"Vulnerability Refinement Result for {file_path} - {vuln.get('vulnerability_name')}: {refinement_result}")
                    if refinement_result.get("is_false_positive"):
                        logging.info(f"False Positive identified and removed: {file_path} - {vuln.get('vulnerability_name')}")
                        continue
                    else:
                        if "improved_description" in refinement_result:
                            vuln["vulnerability_description"] = refinement_result["improved_description"]
                            logging.info(f"Improved description for {file_path} - {vuln.get('vulnerability_name')}: {refinement_result['improved_description']}")
                        if "new_threat_level" in refinement_result:
                            new_level = refinement_result["new_threat_level"].lower()
                            if new_level not in valid_levels:
                                new_level = "code quality issue"
                            vuln["threat_level"] = new_level
                            logging.info(f"Updated threat level for {file_path} - {vuln.get('vulnerability_name')}: {new_level}")
                        refined_vulnerabilities.append(vuln)
                        level = vuln.get("threat_level", "code quality issue").lower()
                        if level not in valid_levels:
                            level = "code quality issue"
                        improved_security_output["threat_summary"][level] = improved_security_output["threat_summary"].get(level, 0) + 1
                improved_security_output[file_path] = refined_vulnerabilities
        except Exception as e:
            logging.error(f"Exception in refine_security_report loop (batch {i+1}-{min(i + BATCH_SIZE, len(file_paths))}): {e}", exc_info=True)
            for file_path_error in batch_files:
                improved_security_output[file_path_error] = vulnerability_batch.get(file_path_error, [])
    logging.info("=== Exiting refine_security_report function ===")
    return improved_security_output

def main():
    """
    Main function:
    - Sets up logging and configures the Gemini API.
    - Prompts for repository source and loads the repository.
    - Converts repository content to text and uploads the file to Gemini.
    - Prompts for analysis mode (single-agent or two-agent) BEFORE running the first pass.
    - Performs first pass security analysis.
    - Optionally refines results in a second pass using a different model and the uploaded repository reference.
    - Saves the report(s) as JSON.
    """
    script_dir = Path(__file__).parent.resolve()
    log_file = script_dir / "security_scanner.log"
    setup_logging(log_file, log_to_console=True)
    logging.info("=== Security Analysis Script Started ===")
    if not API_KEY:
        logging.error("Gemini API key not found.")
        print("Error: Set GEMINI_API_KEY environment variable.")
        sys.exit(1)
    try:
        configure_genai_api(API_KEY)
        global gemini_model
        gemini_model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        logging.error(f"Failed to configure Gemini API: {e}")
        sys.exit(1)
    repo_source = get_repo_source()
    if repo_source["type"] == "local":
        repo_path = repo_source["path"]
        repo = initialize_local_repo(repo_path)
    else:
        try:
            repo_path = clone_remote_repo(repo_source["url"])
            repo = initialize_local_repo(repo_path)
        except Exception as e:
            logging.error(f"Failed to clone repository: {e}")
            sys.exit(1)
    repo_name = repo_path.name
    repo_content_output_path = script_dir / REPO_CONTENT_FILE
    repo_content = load_repo_content_to_text(repo, repo_name, repo_content_output_path)
    if not repo_content:
        logging.error("Failed to load repository content for analysis.")
        sys.exit(1)
    try:
        uploaded_repo = upload_file_to_gemini(repo_content_output_path)
        logging.info(f"Repository text uploaded to Gemini. Reference: {uploaded_repo}")
    except Exception as e:
        logging.error(f"Failed to upload repository content to Gemini: {e}")
        sys.exit(1)

    # Prompt user to choose analysis mode BEFORE running first pass analysis
    analysis_mode = get_analysis_mode()

    # Perform first pass security analysis
    security_report = analyze_security(repo, repo_name)
    security_report_path = script_dir / SECURITY_OUTPUT_FILE
    save_json(security_report, security_report_path, "security vulnerabilities (first pass)")

    if analysis_mode == "2":
        try:
            gemini_model_second = genai.GenerativeModel(SECOND_PASS_MODEL)
            logging.info(f"Using model '{SECOND_PASS_MODEL}' for second pass refinement.")
        except Exception as e:
            logging.error(f"Failed to configure second pass model '{SECOND_PASS_MODEL}': {e}")
            sys.exit(1)
        improved_security_report = refine_security_report(security_report, repo_content, repo_name, model=gemini_model_second, uploaded_repo=uploaded_repo)
        improved_security_report_path = script_dir / IMPROVED_SECURITY_OUTPUT_FILE
        save_json(improved_security_report, improved_security_report_path, "improved security vulnerabilities (second pass)")
        logging.info("Security analysis and refinement process completed with two agents.")
    else:
        logging.info("Security analysis completed using single-agent approach. Second pass refinement skipped.")

if __name__ == "__main__":
    main()
