import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()

def select_folder():
    '''
    Get the directory of a repo by opening a window to select.
    :return: the directory of a repo.
    '''
    folder_path = filedialog.askdirectory(title="Select folder")
    if folder_path:
        return folder_path
    # TODO warning if there's problem
    # else:

def select_file():
    '''
    Get the directory of a file (readme.md) by opening a window to select.
    :return: the directory of a file.
    '''
    file_path = filedialog.askopenfilename(title="Select file")
    if file_path:
        return file_path
    # TODO warning if there's problem
    # else:

def export_markdown(content):
    '''
    Export ReadMe.md to selected position
    :param: content: content of readme
    '''
    file_path = filedialog.asksaveasfilename(
        defaultextension=".md",
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        title="Save Markdown File"
    )

    if file_path:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"File saved at: {file_path}")
    # TODO warning if there's problem
    # else:
    #     print("Save operation cancelled.")