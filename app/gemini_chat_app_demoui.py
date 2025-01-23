# gemini_chat_app.py
import os
import sys
import json
import time
import logging
from pathlib import Path
import shutil
import tempfile
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import google.generativeai as genai

# Importing utility functions
from utils.utils import (
    setup_logging,
    get_local_repo_path,
    get_remote_repo_url,
    clone_remote_repo,
    convert_repo_to_txt,
    configure_genai_api,
    upload_file_to_gemini
)

# ------------------------------ Configuration ------------------------------

API_KEY = "YOUR_GEMINI_API_KEY"  # Replace with your actual Gemini API key
MODEL_NAME = "gemini-1.5-flash"   # Replace with your desired Gemini model

# ------------------------------ Logging Configuration ------------------------------

# Setup Logging using utils
script_dir = Path(__file__).parent.resolve()
log_file = script_dir / "chat_with_gemini.log"
setup_logging(log_file)
logging.info("=== Gemini Chat Assistant Script Started ===")

# ------------------------------ Helper Functions ------------------------------

def chat_with_gemini(model, uploaded_file, user_question: str, response_queue: queue.Queue):
    """
    Initiates an interactive chat with Google Gemini about the repository using streaming.
    Sends the generated response to the response_queue.
    """
    try:
        prompt = f"""You are a helpful assistant for using and developing the repository. Based on the repository content provided, answer the following question. Do not include your name in the response:
        
Question: {user_question}

Answer:"""
    
        # Generate content with streaming
        response = model.generate_content([uploaded_file, "\n\n", prompt], stream=True)

        response_text = ""
        for chunk in response:
            chunk_text = chunk.text
            response_text += chunk_text
            response_queue.put(chunk_text)

        # Indicate completion
        response_queue.put("<END>")
        logging.info(f"Gemini responded to: {user_question} with: {response_text}")
    except Exception as e:
        logging.error(f"Failed during chat with Gemini: {e}")
        response_queue.put(f"Error during chat with Gemini: {e}")
        response_queue.put("<END>")

# ------------------------------ GUI Application ------------------------------

class GeminiChatAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gemini Chat Assistant")
        self.geometry("800x600")
        self.resizable(False, False)

        # Initialize variables
        self.repo_type = tk.StringVar(value="local")
        self.local_repo_path = tk.StringVar()
        self.remote_repo_url = tk.StringVar()
        self.api_key = tk.StringVar(value=API_KEY)
        self.model_name = tk.StringVar(value=MODEL_NAME)
        self.uploaded_file = None
        self.model = None
        self.response_queue = queue.Queue()

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both')

        # Create frames for each tab
        self.repo_selection_frame = ttk.Frame(self.notebook)
        self.processing_frame = ttk.Frame(self.notebook)
        self.chat_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)
        self.logs_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.repo_selection_frame, text="Repository Selection")
        self.notebook.add(self.processing_frame, text="Processing")
        self.notebook.add(self.chat_frame, text="Chat")
        self.notebook.add(self.settings_frame, text="Settings")
        self.notebook.add(self.logs_frame, text="Logs")

        # Initialize each frame
        self.init_repo_selection_frame()
        self.init_processing_frame()
        self.init_chat_frame()
        self.init_settings_frame()
        self.init_logs_frame()

        # Initially, disable Processing and Chat tabs; enable Settings and Logs
        self.notebook.tab(1, state="disabled")  # Processing
        self.notebook.tab(2, state="disabled")  # Chat
        self.notebook.tab(3, state="normal")    # Settings
        self.notebook.tab(4, state="normal")    # Logs

        # Start log monitoring
        self.after(100, self.update_logs)

    def init_repo_selection_frame(self):
        frame = self.repo_selection_frame

        # Repository Type Selection
        repo_type_label = ttk.Label(frame, text="Select Repository Type:", font=("Arial", 12))
        repo_type_label.pack(pady=10)

        repo_type_frame = ttk.Frame(frame)
        repo_type_frame.pack(pady=5)

        local_rb = ttk.Radiobutton(repo_type_frame, text="Local Repository", variable=self.repo_type, value="local", command=self.update_repo_type)
        remote_rb = ttk.Radiobutton(repo_type_frame, text="Remote Repository", variable=self.repo_type, value="remote", command=self.update_repo_type)
        local_rb.pack(side='left', padx=10)
        remote_rb.pack(side='left', padx=10)

        # Local Repository Path
        self.local_repo_frame = ttk.Frame(frame)
        self.local_repo_frame.pack(pady=10, fill='x', padx=20)

        local_path_label = ttk.Label(self.local_repo_frame, text="Repository Path:", font=("Arial", 10))
        local_path_label.pack(side='left', padx=5)

        local_path_entry = ttk.Entry(self.local_repo_frame, textvariable=self.local_repo_path, width=50)
        local_path_entry.pack(side='left', padx=5)

        browse_button = ttk.Button(self.local_repo_frame, text="Browse", command=self.browse_local_repo)
        browse_button.pack(side='left', padx=5)

        # Remote Repository URL
        self.remote_repo_frame = ttk.Frame(frame)
        self.remote_repo_frame.pack(pady=10, fill='x', padx=20)

        remote_url_label = ttk.Label(self.remote_repo_frame, text="GitHub Repository URL:", font=("Arial", 10))
        remote_url_label.pack(side='left', padx=5)

        remote_url_entry = ttk.Entry(self.remote_repo_frame, textvariable=self.remote_repo_url, width=50)
        remote_url_entry.pack(side='left', padx=5)

        # Initially hide remote repo frame
        self.remote_repo_frame.pack_forget()

        # Next Button
        next_button = ttk.Button(frame, text="Next", command=self.start_processing)
        next_button.pack(pady=20)

    def update_repo_type(self):
        if self.repo_type.get() == "local":
            self.local_repo_frame.pack(pady=10, fill='x', padx=20)
            self.remote_repo_frame.pack_forget()
        else:
            self.remote_repo_frame.pack(pady=10, fill='x', padx=20)
            self.local_repo_frame.pack_forget()

    def browse_local_repo(self):
        selected_path = filedialog.askdirectory()
        if selected_path:
            self.local_repo_path.set(selected_path)

    def init_processing_frame(self):
        frame = self.processing_frame

        status_label = ttk.Label(frame, text="Processing Repository...", font=("Arial", 12))
        status_label.pack(pady=20)

        self.progress_bar = ttk.Progressbar(frame, mode='indeterminate')
        self.progress_bar.pack(pady=10, fill='x', padx=50)
        self.progress_bar.start()

        self.processing_status = tk.StringVar(value="Initializing...")
        processing_status_label = ttk.Label(frame, textvariable=self.processing_status, font=("Arial", 10))
        processing_status_label.pack(pady=10)

    def init_chat_frame(self):
        frame = self.chat_frame

        # Chat Display Area
        chat_display = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state='disabled', font=("Arial", 10))
        chat_display.pack(pady=10, padx=10, expand=True, fill='both')
        self.chat_display = chat_display

        # Input Field and Send Button
        input_frame = ttk.Frame(frame)
        input_frame.pack(pady=10, padx=10, fill='x')

        self.chat_input = tk.StringVar()
        chat_entry = ttk.Entry(input_frame, textvariable=self.chat_input, width=70)
        chat_entry.pack(side='left', padx=5, fill='x', expand=True)
        chat_entry.bind("<Return>", self.send_chat)

        send_button = ttk.Button(input_frame, text="Send", command=self.send_chat)
        send_button.pack(side='left', padx=5)

        # Streaming Indicator
        self.streaming_label = ttk.Label(frame, text="", font=("Arial", 10))
        self.streaming_label.pack(pady=5)

    def init_settings_frame(self):
        frame = self.settings_frame

        # API Key Input
        api_label = ttk.Label(frame, text="Gemini API Key:", font=("Arial", 10))
        api_label.pack(pady=10, padx=10, anchor='w')

        api_entry = ttk.Entry(frame, textvariable=self.api_key, show="*", width=50)
        api_entry.pack(pady=5, padx=10, anchor='w')

        # Model Selection
        model_label = ttk.Label(frame, text="Select Gemini Model:", font=("Arial", 10))
        model_label.pack(pady=10, padx=10, anchor='w')

        model_combo = ttk.Combobox(frame, textvariable=self.model_name, state="readonly")
        model_combo['values'] = ["gemini-1.5-flash", "gemini-2.0-flash-exp","gemini-2.0-flash-thinking-exp-01-21"]  # Add available models here
        model_combo.current(0)
        model_combo.pack(pady=5, padx=10, anchor='w')

        # Save Settings Button
        save_button = ttk.Button(frame, text="Save Settings", command=self.save_settings)
        save_button.pack(pady=20)

    def init_logs_frame(self):
        frame = self.logs_frame

        # Log Display Area
        log_display = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state='disabled', font=("Arial", 10))
        log_display.pack(pady=10, padx=10, expand=True, fill='both')
        self.log_display = log_display

        # Export Logs Button
        export_button = ttk.Button(frame, text="Export Logs", command=self.export_logs)
        export_button.pack(pady=5)

    def start_processing(self):
        # Validate repository selection
        try:
            if self.repo_type.get() == "local":
                if not self.local_repo_path.get():
                    messagebox.showerror("Error", "Please select a local repository path.")
                    return
                repo_path = get_local_repo_path(self.local_repo_path.get())
            else:
                if not self.remote_repo_url.get():
                    messagebox.showerror("Error", "Please enter a GitHub repository URL.")
                    return
                repo_url = get_remote_repo_url(self.remote_repo_url.get())
                repo_path = clone_remote_repo(repo_url)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Disable Repository Selection Tab
        self.notebook.tab(0, state="disabled")

        # Switch to Processing Tab
        self.notebook.tab(1, state="normal")
        self.notebook.select(1)

        # Start processing in a separate thread
        processing_thread = threading.Thread(target=self.process_repository, args=(repo_path,))
        processing_thread.start()

    def process_repository(self, repo_path: Path):
        try:
            self.update_processing_status("Converting repository to text...")
            with tempfile.TemporaryDirectory() as temp_dir_name:
                temp_dir_path = Path(temp_dir_name)
                output_txt_path = temp_dir_path / "repo_content.txt"
                convert_repo_to_txt(repo_path, output_txt_path)

                # Save the converted repo text file to the repository (only for local repos)
                if self.repo_type.get() == 'local':
                    self.update_processing_status("Saving converted text file to repository...")
                    try:
                        destination_path = repo_path / "repo_content_converted.txt"
                        if destination_path.exists():
                            # Prompt user for overwrite
                            overwrite = self.prompt_overwrite(destination_path.name)
                            if overwrite:
                                shutil.copy(output_txt_path, destination_path)
                                logging.info(f"Overwritten existing file: {destination_path}")
                                self.show_info_message("Success", f"Converted repository content saved to {destination_path}")
                            else:
                                logging.info("User chose not to overwrite the existing converted repository file.")
                                self.show_info_message("Info", "Converted repository content not saved to the repository.")
                        else:
                            shutil.copy(output_txt_path, destination_path)
                            logging.info(f"Saved converted repository content to {destination_path}")
                            self.show_info_message("Success", f"Converted repository content saved to {destination_path}")
                    except Exception as e:
                        logging.error(f"Failed to save converted repository file to {destination_path}: {e}")
                        self.update_processing_status(f"Error saving converted repository file: {e}")
                        self.show_error_message("Error", f"Failed to save converted repository file: {e}")
                        self.enable_repo_selection_tab()
                        return
                else:
                    logging.info("Remote repository cloned to temporary directory. Skipping saving converted text to remote repository.")
                    self.update_processing_status("Converted repository content is available in the temporary directory.")

                # Configure Google Gemini API
                self.update_processing_status("Configuring Google Gemini API...")
                try:
                    configure_genai_api(self.api_key.get())
                except Exception as e:
                    self.update_processing_status(f"Error configuring Gemini API: {e}")
                    self.show_error_message("Error", f"Error configuring Gemini API: {e}")
                    self.enable_repo_selection_tab()
                    return

                # Upload the text file to Gemini
                self.update_processing_status("Uploading text file to Gemini...")
                try:
                    self.uploaded_file = upload_file_to_gemini(output_txt_path)
                except Exception as e:
                    self.update_processing_status(f"Error uploading file to Gemini: {e}")
                    self.show_error_message("Error", f"Error uploading file to Gemini: {e}")
                    self.enable_repo_selection_tab()
                    return

                # Initialize Gemini model
                self.update_processing_status("Initializing Gemini model...")
                try:
                    self.model = genai.GenerativeModel(self.model_name.get())
                    logging.info(f"Initialized model: {self.model_name.get()}")
                except Exception as e:
                    self.update_processing_status(f"Error initializing Gemini model: {e}")
                    self.show_error_message("Error", f"Error initializing Gemini model: {e}")
                    self.enable_repo_selection_tab()
                    return

                # Update processing status to complete
                self.update_processing_status("Processing complete. Switching to Chat tab.")

                # Disable Processing Tab and switch to Chat Tab in the main thread
                self.after(0, self.disable_processing_and_switch_to_chat)
        except Exception as e:
            logging.error(f"Error during processing: {e}")
            self.update_processing_status(f"Error during processing: {e}")
            self.show_error_message("Error", f"Error during processing: {e}")
            self.enable_repo_selection_tab()

    def prompt_overwrite(self, filename: str) -> bool:
        """
        Prompts the user to confirm overwriting an existing file.
        Returns True if the user chooses to overwrite, False otherwise.
        """
        return messagebox.askyesno("Overwrite Confirmation", 
                                   f"The file '{filename}' already exists in the repository. Do you want to overwrite it?")

    def show_info_message(self, title: str, message: str):
        """
        Displays an informational message box.
        """
        messagebox.showinfo(title, message)

    def show_error_message(self, title: str, message: str):
        """
        Displays an error message box.
        """
        messagebox.showerror(title, message)

    def disable_processing_and_switch_to_chat(self):
        """
        Disables the Processing tab and switches to the Chat tab.
        """
        # First, enable the Chat tab
        self.notebook.tab(2, state="normal")  # Chat tab index is 2
        # Then, select the Chat tab
        self.notebook.select(2)
        # Finally, disable the Processing tab
        self.notebook.tab(1, state="disabled")  # Processing tab index is 1

    def enable_repo_selection_tab(self):
        """
        Enables the Repository Selection tab after an error.
        """
        self.notebook.tab(0, state="normal")
        self.notebook.select(0)

    def update_processing_status(self, message: str):
        self.processing_status.set(message)

    def send_chat(self, event=None):
        user_question = self.chat_input.get().strip()
        if not user_question:
            return
        self.chat_input.set("")

        # Display user question
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"You: {user_question}\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

        # Start streaming response in a separate thread
        threading.Thread(target=self.handle_chat_response, args=(user_question,), daemon=True).start()

    def handle_chat_response(self, user_question: str):
        self.streaming_label.config(text="Gemini is typing...")
        self.response_queue = queue.Queue()
        chat_thread = threading.Thread(target=chat_with_gemini, args=(self.model, self.uploaded_file, user_question, self.response_queue))
        chat_thread.start()

        # Insert "Gemini: " once before starting to process the response
        self.after(0, self.insert_gemini_prefix)

        # Process the response queue
        self.after(100, self.process_response_queue)

    def insert_gemini_prefix(self):
        """
        Inserts the "Gemini: " prefix once before the response starts.
        """
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, "Gemini: ")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

    def process_response_queue(self):
        try:
            while True:
                chunk = self.response_queue.get_nowait()
                if chunk == "<END>":
                    self.streaming_label.config(text="")
                    return
                else:
                    self.chat_display.configure(state='normal')
                    # Append the chunk without adding "Gemini: " multiple times
                    self.chat_display.insert(tk.END, f"{chunk}")
                    self.chat_display.configure(state='disabled')
                    self.chat_display.see(tk.END)
        except queue.Empty:
            pass
        self.after(100, self.process_response_queue)

    def save_settings(self):
        # Save settings logic if needed
        messagebox.showinfo("Settings", "Settings saved successfully.")
        logging.info("User updated settings.")

    def export_logs(self):
        log_path = Path(__file__).parent.resolve() / "chat_with_gemini.log"
        if not log_path.exists():
            messagebox.showerror("Error", "Log file does not exist.")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".log",
                                                 filetypes=[("Log Files", "*.log"), ("All Files", "*.*")],
                                                 title="Save Log File")
        if save_path:
            try:
                shutil.copy(log_path, save_path)
                messagebox.showinfo("Export Logs", f"Logs exported successfully to {save_path}.")
                logging.info(f"Logs exported to {save_path}.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export logs: {e}")
                logging.error(f"Failed to export logs: {e}")

    def update_logs(self):
        try:
            log_path = Path(__file__).parent.resolve() / "chat_with_gemini.log"
            if log_path.exists():
                with open(log_path, 'r') as log_file:
                    logs = log_file.read()
                self.log_display.configure(state='normal')
                self.log_display.delete(1.0, tk.END)
                self.log_display.insert(tk.END, logs)
                self.log_display.configure(state='disabled')
        except Exception as e:
            logging.error(f"Failed to update logs: {e}")
        self.after(1000, self.update_logs)  # Update every second

# ------------------------------ Main Execution ------------------------------

def main():
    logging.info("=== Gemini Chat Assistant Script Started ===")

    # Initialize and run the GUI application
    app = GeminiChatAssistant()
    app.mainloop()

    logging.info("=== Gemini Chat Assistant Script Completed Successfully ===")

if __name__ == "__main__":
    main()
