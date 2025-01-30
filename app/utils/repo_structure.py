import os
import sys
import json
import time
import logging
from pathlib import Path
import shutil
import tempfile

def generate_file_tree(root_path: str, max_depth: int = None, show_files: bool = True, prefix: str = "") -> str:
    """
    Generate a file tree in string format. 
    This can help LLM to understand the structure of repo, which decrease the potential of lowering LLM's attention on other important information.
    This function can be used on ReadME.
    :param root_path: selected root path of the repo
    # TODO: Open a window to let user select root path. (Must)
    :param max_depth: Max depth of the file tree. Control the size of file tree.
    # TODO: Automatically generate the max depth of file tree. (Should)
    :param show_files: Only show folders' name or detailed files' name.
    :param prefix: a parameter to bring blank space for sub tree.
    :return: a file tree in string format.
    """
    # TODO more logic to prevent buggy parameter
    if max_depth is not None and max_depth < 1:
        return ""

    tree = []
    entries = sorted(
        [entry for entry in os.listdir(root_path) if not entry.startswith(".")]
    )
    for i, entry in enumerate(entries):
        entry_path = os.path.join(root_path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        
        # if folder or show_files is allowed, add to tree
        if os.path.isdir(entry_path) or show_files:
            tree.append(f"{prefix}{connector}{entry}")
        
        # recursive add sub tree
        if os.path.isdir(entry_path):
            subtree_prefix = f"{prefix}{'    ' if i == len(entries) - 1 else '│   '}"
            subtree = generate_file_tree(
                entry_path,
                max_depth=None if max_depth is None else max_depth - 1,
                show_files=show_files,
                prefix=subtree_prefix
            )
            if subtree:
                tree.append(subtree)

    return "\n".join(tree)

'''
Following are from Mete
'''

def get_repo_path() -> Path:
    """
    Prompts the user to input the repository folder path.
    Validates that the path exists and is a directory.
    """
    repo_path = input("Enter the path to your repository folder: ").strip()
    repo = Path(repo_path).resolve()
    if not repo.exists():
        logging.error(f"The path '{repo}' does not exist.")
        print(f"Error: The path '{repo}' does not exist.")
        sys.exit(1)
    if not repo.is_dir():
        logging.error(f"The path '{repo}' is not a directory.")
        print(f"Error: The path '{repo}' is not a directory.")
        sys.exit(1)
    logging.info(f"Repository path set to: {repo}")
    return repo

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
                    if file_path.suffix and file_path.suffix.lower() != '.txt' and file_path.suffix.lower() not in ['.md', '.rst', '.py', '.js', '.java', '.cpp', '.c', '.json', '.yaml', '.yml', '.sh', '.rb', '.go', '.ts', '.html', '.css', '.xml', '.ini']:
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
        print(f"Error converting repository to text: {e}")
        sys.exit(1)