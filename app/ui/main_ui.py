import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from improvement_main_window import split_sections, improve_part
from creation import create_part

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x700")
        self.root.title("Beautiful repo")

        title_label = tk.Label(root, text="Select a function", font=("Arial", 16))
        title_label.pack(pady=20)

        self.button1 = tk.Button(root, text="ReadMe improvement", command=self.open_screen1)
        self.button1.pack(pady=10)

        self.button2 = tk.Button(root, text="ReadMe creation", command=self.open_screen2)
        self.button2.pack(pady=10)

    def open_screen1(self):
        '''
        Open improvement page.
        First open a filedialog to select an original readme file.
        '''
        # Destroy current page and go into Improvement page
        for widget in self.root.winfo_children():
            widget.destroy()
        file = filedialog.askopenfilename(title="Select file")
        Improvement(self.root, file)

    def open_screen2(self):
        '''
        Open creation page.
        '''
        # Destroy current page and go into Creation page
        for widget in self.root.winfo_children():
            widget.destroy()
        Creation(self.root)

class Improvement:
    def __init__(self, root, file):
        self.root = root
        self.root.title("ReadMe Improvement")

        self.label = tk.Label(root, text="ReadMe Improvement")
        self.label.pack(pady=10)

        self.left_frame = tk.Frame(root, bg="darkgray", width=200)
        self.left_frame.pack(side="left", fill="y")

        self.section_text = split_sections(file)
        self.saved_text = {}

        # record the which section button has been lastly clicked.
        # help to let llm know which section it should improve.
        self.last_button_pressed = tk.StringVar(value="None")

        # buttons part
        self.sections = list(self.section_text.keys())
        for section in self.sections:
            btn = tk.Button(self.left_frame, 
                            text=section, 
                            width=15, 
                            height=2, 
                            bg="white", 
                            fg="black",
                            command=lambda s = section: self.show_original_text(s))
            btn.pack(pady=5, padx=10)
        
        file_tree_btn = tk.Button(self.left_frame, text="File Tree", width=15, height=2, bg="white", fg="black")
        file_tree_btn.pack(pady=(20, 5), padx=10)

        export_btn = tk.Button(self.left_frame, text="Export", width=15, height=2, bg="black", fg="white", command=self.export)
        export_btn.pack(pady=5, padx=10)

        back_button = tk.Button(self.left_frame, text="Back", command=self.go_back)
        back_button.pack(pady=10)

        # original part
        self.middle_frame = tk.Frame(root, bg="white", width=300)
        self.middle_frame.pack(side="left", fill="both")

        middle_label = tk.Label(self.middle_frame, text="Original", font=("Arial", 14), bg="white")
        middle_label.pack(pady=5)

        self.middle_text = tk.Text(self.middle_frame, wrap="word", bg="#f0f4ff", font=("Arial", 12), width=40)
        self.middle_text.pack(padx=5, pady=10, fill="both")

        # suggetion part
        self.right_frame = tk.Frame(root, bg="white", width=300)
        self.right_frame.pack(side="right", fill="both")

        right_label = tk.Label(self.right_frame, text="Suggestions", font=("Arial", 14), bg="white")
        right_label.pack(pady=5)

        self.right_text = tk.Text(self.right_frame, wrap="word", bg="#f0f4ff", font=("Arial", 12), width=40)
        self.right_text.pack(padx=5, pady=10, fill="both")

        generate_btn = tk.Button(self.right_frame, 
                                 text="Generate", 
                                 width=15, 
                                 height=2, 
                                 bg="white", 
                                 fg="black", 
                                 command= lambda: self.show_improved_text(self.right_text, self.last_button_pressed.get()))
        generate_btn.pack(pady=10)

        save_btn = tk.Button(self.right_frame, 
                            text="Save", 
                            width=15, 
                            height=2, 
                            bg="white", 
                            fg="black",
                            command= lambda: self.save_improved_text(self.last_button_pressed.get()))
        save_btn.pack(pady=10)

    def show_original_text(self, section):
        '''
        Display original text of given section in middle text.
        :param: section: the given section
        '''
        content = self.section_text.get(section, "No original text.")
        # delete text displayed before
        self.middle_text.delete("1.0", tk.END)
        self.right_text.delete("1.0", tk.END)
        self.middle_text.insert(tk.END, content)
        self.last_button_pressed.set(section)
        if (section in self.saved_text):
            self.right_text.insert(tk.END, self.saved_text[section])
    
    def save_improved_text(self, section):
        '''
        Save improved text of given section in right text.
        :param: section: the given section
        '''
        key = section
        value = self.right_text.get("1.0", "end")
        self.saved_text.update({key: value})
        print(self.saved_text)

    def show_improved_text(self, text, section):
        '''
        Show improved text of given section in right text.
        :param: text: the text has been generated and saved.
        :param: section: the given section
        '''
        text.delete("1.0", tk.END)
        original = self.section_text.get(section, "No original text.")
        improved = improve_part(section, original)
        text.insert(tk.END, improved)

    def export(self):
        '''
        Export generated markdown.
        '''
        file_path = filedialog.asksaveasfilename(
        defaultextension=".md",
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        title="Save Markdown File"
    )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as file:
                # The sections should be in order like original one.
                ordered_text = ''.join(self.saved_text[key] for key in self.sections if key in self.saved_text)
                file.write(ordered_text)
            messagebox.showinfo(f"File saved at: {file_path}")

    def go_back(self):
        '''
        Return to main page.
        '''
        for widget in self.root.winfo_children():
            widget.destroy()
        MainApp(self.root)


# 界面2类
class Creation:
    def __init__(self, root):
        self.root = root
        self.root.title("ReadMe Creation")

        self.label = tk.Label(root, text="ReadMe Creation")
        self.label.pack(pady=10)

        self.left_frame = tk.Frame(root, bg="darkgray", width=200)
        self.left_frame.pack(side="left", fill="y")

        # information input by user to create a readme file.
        self.saved_text = {}
        self.title_name= tk.StringVar()
        self.description = tk.StringVar()
        self.softwares = tk.StringVar()
        self.ide = tk.StringVar()
        self.package_manager = tk.StringVar()
        self.address = tk.StringVar()
        self.usage = tk.StringVar()
        self.email_or_website = tk.StringVar()
        self.contact_name = tk.StringVar()
        self.selected_license = tk.StringVar()
        self.features = []
        self.locked_features = [False, False, False, False] 
        self.lock_buttons = [] 

        self.last_button_pressed = tk.StringVar(value="None")

        # buttons part
        self.sections = ["title", "description", "feature", "requirement", "installation", "usage", "contact", "license"]
        for section in self.sections:
            btn = tk.Button(self.left_frame, 
                            text=section, 
                            width=15, 
                            height=2, 
                            bg="white", 
                            fg="black",
                            command=lambda s = section: self.call_func(s))
            btn.pack(pady=5, padx=10)
        
        file_tree_btn = tk.Button(self.left_frame, text="File Tree", width=15, height=2, bg="white", fg="black")
        file_tree_btn.pack(pady=(20, 5), padx=10)

        export_btn = tk.Button(self.left_frame, text="Export", width=15, height=2, bg="black", fg="white", command=self.export)
        export_btn.pack(pady=5, padx=10)

        back_button = tk.Button(self.left_frame, text="Back", command=self.go_back)
        back_button.pack(pady=10)

        # suggetion part
        self.right_frame = tk.Frame(root, bg="white", width=300)
        self.right_frame.pack(side="right", fill="both")

        right_label = tk.Label(self.right_frame, text="Suggestions", font=("Arial", 14), bg="white")
        right_label.pack(pady=5)

        self.right_text = tk.Text(self.right_frame, wrap="word", bg="#f0f4ff", font=("Arial", 12), width=40)
        self.right_text.pack(padx=5, pady=10, fill="both")

        generate_btn = tk.Button(self.right_frame, 
                                 text="Generate", 
                                 width=15, 
                                 height=2, 
                                 bg="white", 
                                 fg="black", 
                                 command= lambda: self.show_created_text(self.right_text, self.last_button_pressed.get()))
        generate_btn.pack(pady=10)

        save_btn = tk.Button(self.right_frame, 
                            text="Save", 
                            width=15, 
                            height=2, 
                            bg="white", 
                            fg="black",
                            command= lambda: self.save_created_text(self.last_button_pressed.get()))
        save_btn.pack(pady=10)

    def call_func(self, section):
        '''
        Since only feature and license popup are different from other sections.
        I use one call_func to assemble them.
        :param: section: the section buttom user clicks.
        '''
        self.last_button_pressed.set(section)
        self.right_text.delete("1.0", tk.END)
        if (section == "feature"):
            self.feature()
        elif (section == "license"):
            self.license()
        else:
            self.general_info(section)
        created_part = self.saved_text.get(section, "No text.")
        self.right_text.insert(tk.END, created_part)

    def save_created_text(self, section):
        '''
        Save created text of given section in right text.
        :param: section: the given section
        '''
        key = section
        value = self.right_text.get("1.0", tk.END)
        self.saved_text.update({key: value})
        print(self.saved_text)

    def show_created_text(self, text, section):
        '''
        Display original text of given section in middle text.
        :param: section: the given section
        '''
        text.delete("1.0", tk.END)
        info = None
        if (section == 'title'):
            info = self.title_name.get()
        elif (section == 'description'):
            info = self.description.get()
        elif (section == 'requirement'):
            info = self.softwares.get()
        elif (section == 'installation'):
            info = self.ide.get() + ", " + self.package_manager.get() + ", " + self.address.get()
        elif (section == 'usage'):
            info = self.usage.get()
        elif (section == 'contact'):
            info = self.contact_name.get() + ", " + self.email_or_website.get()
        elif (section == 'license'):
            info = self.selected_license.get()
        
        improved = create_part(section, info)
        text.insert(tk.END, improved)
    
    def feature(self):
        '''
        remain TODO
        '''
        popup = tk.Toplevel(self.root)
        popup.geometry("600x600")
        popup.title("Features")

        for i in range(4):
            feature_label = tk.Label(popup, text=f"Feature {i + 1}:")
            feature_label.grid(row=i, column=0, padx=10, pady=5)

            feature_entry = tk.Entry(popup)
            feature_entry.grid(row=i, column=1, padx=10, pady=5)
            self.features.append(feature_entry)

            lock_button = tk.Button(
                popup, 
                text="Lock", 
                command=lambda idx=i: self.lock_feature(idx)
            )
            lock_button.grid(row=i, column=2, padx=10, pady=5)
            self.lock_buttons.append(lock_button)

        generate_button = tk.Button(
            popup, 
            text="Generate", 
            command=self.generate
        )
        generate_button.grid(row=4, column=0, columnspan=3, pady=20)

    def lock_feature(self, index):
        '''
        lock features that users like.
        reamin TODO
        '''
        self.locked_features[index] = not self.locked_features[index] 
        if self.locked_features[index]:
            self.lock_buttons[index].config(text="Unlock")
        else:
            self.lock_buttons[index].config(text="Lock")

    def generate(self):
        '''
        generate features
        remain TODO
        '''
        for i, feature in enumerate(self.features):
            if not self.locked_features[i]: 
                feature.delete(0, tk.END)
                new_feature = "new_"
                feature.insert(0, new_feature)
    
    def general_info(self, section):
        '''
        Since most popup has similar layout and function, I write only one popup function.
        Input variable will be changed section by section.
        :param: section: the given section.
        '''
        popup = tk.Toplevel(root)
        popup.geometry("300x300")
        popup.title(section)
        if (section == "title"):
            tk.Label(popup, text="Project name:").pack(pady=5)
            project_entry = tk.Entry(popup)
            project_entry.pack(pady=5)
            if (self.title_name.get()):
                project_entry.insert(0, self.title_name.get()) 
        elif (section == "description"):
            tk.Label(popup, text="Short decription:").pack(pady=5)
            description_entry = tk.Entry(popup)
            description_entry.pack(pady=5)
            if (self.description.get()):
                description_entry.insert(0, self.description.get()) 
        elif (section == "requirement"):
            tk.Label(popup, text="Softwares:").pack(pady=5)
            softwares_entry = tk.Entry(popup)
            softwares_entry.pack(pady=5)
            if (self.softwares.get()):
                softwares_entry.insert(0, self.softwares.get()) 
        elif (section == "installation"):
            tk.Label(popup, text="IDE:").pack(pady=5)
            ide_entry = tk.Entry(popup)
            ide_entry.pack(pady=5)
            if (self.ide.get()):
                ide_entry.insert(0, self.ide.get()) 

            tk.Label(popup, text="Package Manager:").pack(pady=5)
            pm_entry = tk.Entry(popup)
            pm_entry.pack(pady=5)
            if (self.package_manager.get()):
                pm_entry.insert(0, self.package_manager.get()) 

            tk.Label(popup, text="Git address:").pack(pady=5)
            address_entry = tk.Entry(popup)
            address_entry.pack(pady=5)
            if (self.address.get()):
                address_entry.insert(0, self.address.get()) 
        elif (section == "usage"):
            tk.Label(popup, text="Usage:").pack(pady=5)
            usage_entry = tk.Entry(popup)
            usage_entry.pack(pady=5)
            if (self.usage.get()):
                usage_entry.insert(0, self.usage.get()) 
        elif (section == "contact"):
            tk.Label(popup, text="Name:").pack(pady=5)
            name_entry = tk.Entry(popup)
            name_entry.pack(pady=5)
            if (self.contact_name.get()):
                name_entry.insert(0, self.contact_name.get()) 
            tk.Label(popup, text="Email or Website:").pack(pady=5)
            email_entry = tk.Entry(popup)
            email_entry.pack(pady=5)
            if (self.email_or_website.get()):
                email_entry.insert(0, self.email_or_website.get()) 

        def save_info(section):
            '''
            Save the info given by users to each variable.
            After save, close the popup.
            :param: section: the given section
            '''
            if (section == "title"):
                self.title_name.set(project_entry.get())
            elif (section == "description"):
                self.description.set(description_entry.get())
            elif (section == "requirement"):
                self.softwares.set(softwares_entry.get())
            elif (section == "installation"):
                self.ide.set(ide_entry.get())
                self.package_manager.set(pm_entry.get())
                self.address.set(address_entry.get())
            elif (section == "usage"):
                self.usage.set(usage_entry.get())
            elif (section == "contact"):
                self.email_or_website.set(email_entry.get())
                self.contact_name.set(name_entry.get())

            popup.destroy()

        save_button = tk.Button(popup, text="Save", command= lambda s = section: save_info(s))
        save_button.pack(pady=10)

    def export(self):
        '''
        Export generated markdown.
        '''
        file_path = filedialog.asksaveasfilename(
        defaultextension=".md",
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        title="Save Markdown File"
    )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as file:
                ordered_text = ''.join(self.saved_text[key] for key in self.sections if key in self.saved_text)
                file.write(ordered_text)
            messagebox.showinfo(f"File saved at: {file_path}")

    def license(self):
        '''
        The popup of license.
        '''
        popup = tk.Toplevel(root)
        popup.title("License")
        popup.geometry("300x200")

        # Save license's type selected by user and close popup.
        def save_choice(choice):
            self.selected_license.set(choice) 
            popup.destroy() 
        
        tk.Label(popup, text=self.selected_license.get()).pack(pady=5)
        
        button1 = tk.Button(popup, text="MIT License", command=lambda: save_choice("MIT License"))
        button1.pack(pady=10)

        button2 = tk.Button(popup, text="GNU License", command=lambda: save_choice("GNU License"))
        button2.pack(pady=10)

        button3 = tk.Button(popup, text="Apache License", command=lambda: save_choice("Apache License"))
        button3.pack(pady=10)


    def go_back(self):
        '''
        Return to main page.
        '''
        for widget in self.root.winfo_children():
            widget.destroy()
        MainApp(self.root)

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
