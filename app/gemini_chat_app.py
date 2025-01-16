# ui mockup - Copy.py
import sys
import json
import logging
from pathlib import Path
import shutil
import tempfile
import subprocess
import google.generativeai as genai

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
MODEL_NAME = "gemini-1.5-flash"   # Replace with your desired Gemini model

# ------------------------------ Helper Functions ------------------------------

def choose_repo_type() -> str:
    """
    Prompts the user to choose between a local or remote repository.
    Returns the choice as 'local' or 'remote'.
    """
    while True:
        choice = input("Do you want to work with a local or remote repository? (local/remote): ").strip().lower()
        if choice in ['local', 'remote']:
            return choice
        else:
            print("Invalid input. Please enter 'local' or 'remote'.")

def chat_with_gemini(uploaded_file):
    """
    Initiates an interactive chat with Google Gemini about the repository using streaming.
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        logging.info(f"Initialized model: {MODEL_NAME}")

        print("\nYou can now chat with Gemini about your repository.")
        print("Type 'exit' to end the chat.\n")

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                print("Ending chat with Gemini.")
                logging.info("User ended the chat session.")
                break

            # Define the prompt for each user input
            prompt = f"""You are a helpful assistant for using and developing the repository. Based on the repository content provided, answer the following question:

Question: {user_input}

Answer:"""

            # Generate content with streaming
            response = model.generate_content([uploaded_file, "\n\n", prompt], stream=True)
            print("Gemini: ", end="", flush=True)  # Initial prefix

            gemini_response = ""
            for chunk in response:
                chunk_text = chunk.text
                gemini_response += chunk_text
                print(chunk_text, end="", flush=True)  # Print chunk as it arrives

            print("\n")  # Newline after response
            logging.info(f"User asked: {user_input}")
            logging.info(f"Gemini responded: {gemini_response}")

    except Exception as e:
        logging.error(f"Failed during chat with Gemini: {e}")
        print(f"Error during chat with Gemini: {e}")
        sys.exit(1)

def save_converted_repo_txt(temp_txt_path: Path, repo_path: Path):
    """
    Saves the converted repository text file to the repository directory.
    If the file already exists, prompts the user to overwrite or cancel.
    """
    destination_path = repo_path / "repo_content_converted.txt"

    if destination_path.exists():
        while True:
            user_input = input(f"The file '{destination_path.name}' already exists in the repository. Overwrite? (y/n): ").strip().lower()
            if user_input == 'y':
                try:
                    shutil.copy(temp_txt_path, destination_path)
                    logging.info(f"Overwritten existing file: {destination_path}")
                    print(f"Converted repository content saved to {destination_path}")
                except Exception as e:
                    logging.error(f"Failed to overwrite file {destination_path}: {e}")
                    print(f"Error overwriting file {destination_path}: {e}")
                    sys.exit(1)
                break
            elif user_input == 'n':
                logging.info("User chose not to overwrite the existing converted repository file.")
                print("Converted repository content not saved to the repository.")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    else:
        try:
            shutil.copy(temp_txt_path, destination_path)
            logging.info(f"Saved converted repository content to {destination_path}")
            print(f"Converted repository content saved to {destination_path}")
        except Exception as e:
            logging.error(f"Failed to save converted repository file to {destination_path}: {e}")
            print(f"Error saving converted repository file to {destination_path}: {e}")
            sys.exit(1)

# ------------------------------ Main Execution ------------------------------

def main():
    # Define log file path
    script_dir = Path(__file__).parent.resolve()
    log_file = script_dir / "repository_chat.log"
    # Configure logging to only write to the file
    setup_logging(log_file, log_to_console=False)
    logging.info("=== Repository Chat Assistant Script Started ===")

    # Step 1: Choose repository type
    repo_type = choose_repo_type()

    # Step 2: Get repository path
    if repo_type == 'local':
        repo_path_str = input("Enter the path to your local repository: ").strip()
        repo_path = get_local_repo_path(repo_path_str)
        temp_dir = None  # No temporary directory needed
    else:
        repo_url_input = input("Enter the URL of the remote repository: ").strip()
        repo_url = get_remote_repo_url(repo_url_input)
        repo_path = clone_remote_repo(repo_url)
        temp_dir = repo_path  # To keep track for cleanup

    # Step 3: Convert repository to text
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir_path = Path(temp_dir_name)
        output_txt_path = temp_dir_path / "repo_content.txt"
        convert_repo_to_txt(repo_path, output_txt_path)

        # Step 4: Save the converted repo text file to the repository (only for local repos)
        if repo_type == 'local':
            save_converted_repo_txt(output_txt_path, repo_path)
        else:
            # For remote repos cloned to temp, you might choose not to save back
            logging.info("Remote repository cloned to temporary directory. Skipping saving converted text to remote repository.")
            print("Converted repository content is available in the temporary directory.")

        # Step 5: Configure Google Gemini API
        configure_genai_api(API_KEY)

        # Step 6: Upload the text file to Gemini
        uploaded_file = upload_file_to_gemini(output_txt_path)

        # Step 7: Initiate chat with Gemini
        chat_with_gemini(uploaded_file)

    # Cleanup cloned remote repository if any
    if repo_type == 'remote' and temp_dir:
        try:
            shutil.rmtree(repo_path)
            logging.info(f"Cleaned up temporary cloned repository at {repo_path}")
        except Exception as e:
            logging.warning(f"Failed to clean up temporary repository at {repo_path}: {e}")

    logging.info("=== Repository Chat Assistant Script Completed Successfully ===")
    print("Process completed. Check the log file for details.")

if __name__ == "__main__":
    main()