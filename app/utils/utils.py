# utils.py
import os
import sys
import json
import time
import logging
from pathlib import Path
import shutil
import tempfile
import subprocess
import google.generativeai as genai

# ------------------------------ Logging Configuration ------------------------------

def setup_logging(log_file: Path, level=logging.INFO, log_to_console=True):
    """
    Configures logging to output to a file and optionally to the console.
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid adding multiple handlers if already set
    if not logger.handlers:
        # Formatter
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

        # File Handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Stream Handler (Console) - Added conditional inclusion
        if log_to_console:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

# ------------------------------ Gemini API Configuration ------------------------------

def configure_genai_api(api_key: str):
    """
    Configures the Google Gemini API with the provided API key.
    """
    try:
        genai.configure(api_key=api_key)
        logging.info("Successfully configured Google Gemini API.")
    except Exception as e:
        logging.error(f"Failed to configure Google Gemini API: {e}")
        raise RuntimeError(f"Error configuring Google Gemini API: {e}")

# ------------------------------ Repository Utilities ------------------------------

def get_local_repo_path(repo_path: str) -> Path:
    """
    Validates that the local repository path exists and is a directory.
    """
    repo = Path(repo_path).resolve()
    if not repo.exists():
        logging.error(f"The path '{repo}' does not exist.")
        raise FileNotFoundError(f"The path '{repo}' does not exist.")
    if not repo.is_dir():
        logging.error(f"The path '{repo}' is not a directory.")
        raise NotADirectoryError(f"The path '{repo}' is not a directory.")
    logging.info(f"Local repository path set to: {repo}")
    return repo

def get_remote_repo_url(repo_url: str) -> str:
    """
    Validates the remote repository URL format.
    """
    if repo_url.startswith("https://github.com/") or repo_url.startswith("git@github.com:"):
        return repo_url
    else:
        logging.error("Invalid GitHub URL format.")
        raise ValueError("Invalid GitHub URL. Please enter a valid GitHub repository URL.")

def clone_remote_repo(repo_url: str) -> Path:
    """
    Clones the remote repository into a temporary directory.
    Returns the path to the cloned repository.
    """
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="cloned_repo_"))
        logging.info(f"Cloning remote repository {repo_url} into {temp_dir}")
        subprocess.run(["git", "clone", repo_url, str(temp_dir)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Successfully cloned repository to {temp_dir}")
        return temp_dir
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode().strip()
        logging.error(f"Git clone failed: {stderr_output}")
        raise RuntimeError(f"Error cloning repository: {stderr_output}")
    except Exception as e:
        logging.error(f"Unexpected error during cloning: {e}")
        raise RuntimeError(f"Unexpected error during cloning: {e}")

def convert_repo_to_txt(repo_path: Path, output_txt_path: Path):
    """
    Walks through the repository directory, captures the file tree,
    file names, and file contents, and writes them to a single .txt file.
    """
    try:
        with open(output_txt_path, 'w', encoding='utf-8') as txt_file:
            for root, dirs, files in os.walk(repo_path):
                # Write the directory path
                dir_path = Path(root).relative_to(repo_path)
                txt_file.write(f"\n### Directory: {dir_path}\n\n")

                for file in files:
                    file_path = Path(root) / file
                    relative_file_path = file_path.relative_to(repo_path)

                    # Convert to .txt if necessary
                    if file_path.suffix and file_path.suffix.lower() != '.txt' and file_path.suffix.lower() not in [
                        '.md', '.rst', '.py', '.js', '.java', '.cpp', '.c', '.json',
                        '.yaml', '.yml', '.sh', '.rb', '.go', '.ts', '.html',
                        '.css', '.xml', '.ini']:
                        # Skip non-text files based on extension
                        logging.info(f"Skipping non-text file: {relative_file_path}")
                        continue

                    # Write the file name
                    txt_file.write(f"#### File: {relative_file_path}\n\n")

                    # Read and write the file content
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        txt_file.write(content)
                        txt_file.write("\n\n")
                        logging.info(f"Added file to txt: {relative_file_path}")
                    except Exception as e:
                        logging.error(f"Failed to read file {relative_file_path}: {e}")
                        txt_file.write(f"<!-- Failed to read file: {e} -->\n\n")
        logging.info(f"Repository successfully converted to text at {output_txt_path}")
    except Exception as e:
        logging.error(f"Error converting repository to text: {e}")
        raise RuntimeError(f"Error converting repository to text: {e}")

# ------------------------------ File Upload Utilities ------------------------------

def upload_file_to_gemini(file_path: Path):
    """
    Uploads the specified file to Google Gemini.
    Returns the uploaded file object.
    """
    try:
        uploaded_file = genai.upload_file(file_path)
        logging.info(f"Successfully uploaded file: {file_path.name}")
        return uploaded_file
    except Exception as e:
        logging.error(f"Failed to upload file {file_path.name}: {e}")
        raise RuntimeError(f"Error uploading file {file_path.name}: {e}")
# utils.py (Add this function)

def convert_file_to_txt(source_file: Path, output_file: Path):
    """
    Reads the content of a source file and writes it to an output .txt file.
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as src:
            content = src.read()
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write(content)
        logging.info(f"Successfully converted {source_file} to {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"Error converting {source_file} to txt: {e}")
        raise RuntimeError(f"Error converting {source_file} to txt: {e}")
