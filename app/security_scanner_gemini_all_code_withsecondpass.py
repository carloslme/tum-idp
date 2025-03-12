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
API_KEY = "AIzaSyDV39V5_0X15G4LU2FPPJmRfea7iNs2Pck"  # Replace with your actual Gemini API key
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"  # First pass model
SECOND_PASS_MODEL = "gemini-2.0-flash-thinking-exp-01-21"  # Second pass model

# Output file names and repository content file
SECURITY_OUTPUT_FILE = "security_vulnerabilities.json"
IMPROVED_SECURITY_OUTPUT_FILE = "improved_security_vulnerabilities.json"  # For refined vulnerabilities
REPO_CONTENT_FILE = "repo_content.txt"  # Stores entire repository content as text

# Constants for API rate limiting and retry logic
RATE_LIMIT_SECONDS = 10
RATE_LIMIT_SECONDS_SECOND_PASS = 10
MAX_RETRIES = 3
BATCH_SIZE = 5  # Process vulnerabilities in batches

# File extensions to consider as code files
CODE_FILE_EXTENSIONS = [
    ".py", ".js", ".java", ".c", ".cpp", ".rb", ".go", ".ts", ".cs", ".php",
    ".swift", ".kt", ".rs", ".scala", ".sh", ".bat", ".ps1", ".html", ".css",
    ".xml", ".json", ".yaml", ".yml",
]

# Global counters for Gemini API statistics
gemini_stats_first = {"num_requests": 0, "num_errors": 0, "total_response_time": 0.0}
gemini_stats_second = {"num_requests": 0, "num_errors": 0, "total_response_time": 0.0}


def get_repo_source() -> dict:
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
    try:
        repo = git.Repo(repo_path)
        logging.info(f"Initialized local repository at {repo_path}")
        return repo
    except git.exc.InvalidGitRepositoryError:
        logging.error(f"The directory '{repo_path}' is not a Git repository.")
        print(f"Error: The directory '{repo_path}' is not a Git repository.")
        sys.exit(1)


def extract_code_files(repo: git.Repo) -> list:
    code_files = []
    for root, dirs, files in os.walk(repo.working_tree_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in CODE_FILE_EXTENSIONS):
                file_path = Path(root) / file
                code_files.append(file_path)
    return code_files


def extract_json(text: str) -> dict:
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
    global gemini_stats_first
    start_time = time.time()
    try:
        model = model or gemini_model
        response = model.generate_content(prompt)
        elapsed_time = time.time() - start_time
        gemini_stats_first["num_requests"] += 1
        gemini_stats_first["total_response_time"] += elapsed_time
    except Exception as e:
        gemini_stats_first["num_requests"] += 1
        gemini_stats_first["num_errors"] += 1
        logging.error(f"API Error processing {file_path}: {str(e)}")
        raise

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


def analyze_security(repo: git.Repo, repo_name: str) -> dict:
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
    try:
        relative_path = file_path.relative_to(Path(repo.working_tree_dir))
        return f"{repo_name}/{relative_path}"
    except ValueError:
        return str(file_path)


def save_json(data: dict, file_path: Path, description: str):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Successfully wrote {description} to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to {file_path}: {e}")


def load_repo_content_to_text(repo: git.Repo, repo_name: str, output_file_path: Path):
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


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(Exception),
)
def refine_vulnerability_report_gemini_batch(vulnerability_batch: dict, repo_content: str, uploaded_repo: str, model=None) -> dict:
    """
    Refine a batch of vulnerability reports using the Gemini API.
    The prompt instructs the model to return only refined reports for vulnerabilities that are true positives.
    Vulnerabilities that are false positives should be omitted from the output.
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
    Your task is to analyze and refine each vulnerability report using the full repository content provided below as context.
    
    IMPORTANT: For each vulnerability report, if you determine it is a false positive, do NOT include it in your output.
    Only output a refined report for vulnerabilities that are true positives.
    
    Input Vulnerability Reports (JSON List):
    ```json
    {prompt_json_input}
    ```
    
    Instructions:
    For each vulnerability in the input that is a true positive, output a refined report in the following JSON format:
    {{
      "vulnerability_name": (string, same as the input(Update or correct the vulnerability name if needed)),
      "vulnerability_description": (string, a detailed and precise refined description using the repository context),
      "location": (string, same as the input(Retain the location information, but improve clarity if possible)),
      "remediation": (string, same as the input( Refine or correct the remediation steps as necessary)),
      "threat_level": (string, (Update the threat level based on the full repository context; choose one of "code quality issue", "low", "medium", "high", or "critical"),
      "cwe_id": (string, same as the input( Correct the CWE identifier if applicable)),
      "cwe_name": (string, same as the input( Correct the CWE name if applicable))
    }}
    
    Output a JSON dictionary keyed by file paths, where each key's value is a list of refined vulnerability reports.
    Do not include any vulnerabilities that are false positives.
    Provide only the JSON response without any markdown formatting or additional explanations.
    """
    global gemini_stats_second
    start_time = time.time()
    try:
        model = model or gemini_model
        response = model.generate_content([uploaded_repo, "\n\n", prompt])
        elapsed_time = time.time() - start_time
        gemini_stats_second["num_requests"] += 1
        gemini_stats_second["total_response_time"] += elapsed_time
        refinement_report = response.text.strip()
        logging.debug(f"Batch refinement model response:\n{refinement_report}")
        refined_data_batch = extract_json(refinement_report)
        if not refined_data_batch:
            logging.warning("Could not extract valid JSON from batch refinement response.")
            return {}
        return refined_data_batch
    except Exception as e:
        gemini_stats_second["num_requests"] += 1
        gemini_stats_second["num_errors"] += 1
        logging.error(f"API Error during batch refinement: {str(e)}")
        return {}


def refine_security_report(security_report: dict, repo_content: str, repo_name: str, model=None, uploaded_repo: str = None) -> dict:
    """
    Refine the initial security report in batches using only the second pass output.
    The improved JSON file will be constructed solely from the refined reports produced in the second pass.
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
    # We ignore the first pass reports and solely use the refined reports from the second pass.
    for i in tqdm(range(0, len(file_paths), BATCH_SIZE), desc="Refining Security Report (Batches)"):
        logging.info(f"Starting batch: {i // BATCH_SIZE}")
        batch_files = file_paths[i:i + BATCH_SIZE]
        vulnerability_batch = {}
        for file_path in batch_files:
            vulnerabilities = security_report.get(file_path, [])
            # Only include vulnerabilities that were detected (ignore files with errors)
            if vulnerabilities and not ("error" in vulnerabilities):
                vulnerability_batch[file_path] = vulnerabilities
            else:
                improved_security_output[file_path] = vulnerabilities if vulnerabilities else []
        try:
            batch_refinement_results = refine_vulnerability_report_gemini_batch(vulnerability_batch, repo_content, uploaded_repo, model=model)
            logging.debug(f"Batch Refinement API Results: {batch_refinement_results}")
            for file_path in batch_files:
                refined_vulnerabilities = batch_refinement_results.get(file_path, [])
                for refined in refined_vulnerabilities:
                    level = refined.get("threat_level", "code quality issue").lower()
                    if level not in valid_levels:
                        level = "code quality issue"
                    improved_security_output["threat_summary"][level] = improved_security_output["threat_summary"].get(level, 0) + 1
                improved_security_output[file_path] = refined_vulnerabilities
        except Exception as e:
            logging.error(f"Exception in refine_security_report loop (batch {i+1}-{min(i+BATCH_SIZE, len(file_paths))}): {e}", exc_info=True)
            for file_path_error in batch_files:
                improved_security_output[file_path_error] = vulnerability_batch.get(file_path_error, [])
    logging.info("=== Exiting refine_security_report function ===")
    return improved_security_output


def main():
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

    analysis_mode = get_analysis_mode()

    security_report = analyze_security(repo, repo_name)
    security_report_path = script_dir / SECURITY_OUTPUT_FILE
    save_json(security_report, security_report_path, "security vulnerabilities (first pass)")

    if gemini_stats_first["num_requests"] > 0:
        avg_response_time_first = gemini_stats_first["total_response_time"] / gemini_stats_first["num_requests"]
    else:
        avg_response_time_first = 0.0
    logging.info(f"Gemini First Pass Stats: Requests sent: {gemini_stats_first['num_requests']}, Errors: {gemini_stats_first['num_errors']}, Average response time: {avg_response_time_first:.2f} seconds")

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
        if gemini_stats_second["num_requests"] > 0:
            avg_response_time_second = gemini_stats_second["total_response_time"] / gemini_stats_second["num_requests"]
        else:
            avg_response_time_second = 0.0
        logging.info(f"Gemini Second Pass Stats: Requests sent: {gemini_stats_second['num_requests']}, Errors: {gemini_stats_second['num_errors']}, Average response time: {avg_response_time_second:.2f} seconds")
    else:
        logging.info("Security analysis completed using single-agent approach. Second pass refinement skipped.")


if __name__ == "__main__":
    main()
