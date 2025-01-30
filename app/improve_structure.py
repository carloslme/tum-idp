# improve_structure.py
import os
import sys
import json
import time
import logging
from pathlib import Path
import shutil
import tempfile
import google.generativeai as genai

# Import utility functions from utils.py
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
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"   # Replace with your desired Gemini model

# ------------------------------ Helper Functions ------------------------------

def select_repository() -> Path:
    """
    Allows the user to select between a local repository and a remote repository.
    Returns the path to the repository.
    """
    while True:
        choice = input("Do you want to use a (1) Local repository or (2) Remote repository? Enter 1 or 2: ").strip()
        if choice == '1':
            repo_path_input = input("Enter the path to your local repository folder: ").strip()
            try:
                repo = get_local_repo_path(repo_path_input)
                return repo
            except Exception as e:
                print(e)
                continue
        elif choice == '2':
            repo_url_input = input("Enter the remote repository URL (GitHub): ").strip()
            try:
                repo_url = get_remote_repo_url(repo_url_input)
                repo = clone_remote_repo(repo_url)
                return repo
            except Exception as e:
                print(e)
                continue
        else:
            print("Invalid choice. Please enter 1 for Local or 2 for Remote.")

def save_improved_structure(script_dir: Path, content: str):
    """
    Saves the improved project structure content to the script's directory.
    Backs up the original structure file before overwriting.
    """
    structure_path = script_dir / "suggested_project_structure.md"
    backup_path = script_dir / "PROJECT_STRUCTURE_backup.md"

    try:
        if structure_path.exists():
            shutil.copy(structure_path, backup_path)
            logging.info(f"Backed up original project structure to {backup_path}")
            print(f"Original project structure backed up to {backup_path}")
        
        with open(structure_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Improved project structure successfully written to {structure_path}")
        print(f"Improved project structure successfully generated at {structure_path}")
    except Exception as e:
        logging.error(f"Failed to save improved project structure: {e}")
        print(f"Error saving improved project structure: {e}")
        sys.exit(1)

def save_converted_repo_txt(script_dir: Path, content_path: Path):
    """
    Saves the converted repository text file to the script's directory.
    If the file already exists, prompts the user to overwrite or cancel.
    """
    destination_path = script_dir / "repo_content_converted.txt"

    if destination_path.exists():
        while True:
            user_input = input(f"The file '{destination_path.name}' already exists in the script directory. Overwrite? (y/n): ").strip().lower()
            if user_input == 'y':
                try:
                    shutil.copy(content_path, destination_path)
                    logging.info(f"Overwritten existing file: {destination_path}")
                    print(f"Converted repository content saved to {destination_path}")
                except Exception as e:
                    logging.error(f"Failed to overwrite file {destination_path}: {e}")
                    print(f"Error overwriting file {destination_path}: {e}")
                    sys.exit(1)
                break
            elif user_input == 'n':
                logging.info("User chose not to overwrite the existing converted repository file.")
                print("Converted repository content not saved to the script directory.")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    else:
        try:
            shutil.copy(content_path, destination_path)
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
    log_file = script_dir / "improve_structure.log"
    setup_logging(log_file)
    logging.info("=== Project Structure Improvement Script Started ===")

    # Step 1: Select repository (Local or Remote)
    repo_path = select_repository()

    # Step 2: Convert repository to text
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        output_txt_path = temp_dir / "repo_content.txt"
        convert_repo_to_txt(repo_path, output_txt_path)

        # Step 3: Save the converted repo text file to the script's directory
        save_converted_repo_txt(script_dir, output_txt_path)

        # Step 4: Configure Google Gemini API
        configure_genai_api(API_KEY)

        # Step 5: Upload the text file to Gemini
        uploaded_file = upload_file_to_gemini(output_txt_path)

        # Step 6: Define the prompt
        prompt = """
I am working on improving the project structure of a GitLab repository. I want you to check the following templates for different projects and choose the best one for my repository. Please provide an improved file tree and project structure according to the chosen template.

### Available Templates:

1. Cookiecutter Data Science
Purpose: Standardized structure for data science projects.

File Tree:


├── data
│   ├── external
│   ├── interim
│   ├── processed
│   └── raw
├── notebooks
├── references
├── reports
│   └── figures
├── src
│   ├── data
│   ├── features
│   ├── models
│   └── visualization
├── tests
├── .gitignore
├── README.md
└── environment.yml
2. Cookiecutter Django
Purpose: Django web application with best practices.

File Tree:


├── config
│   ├── settings
│   ├── urls.py
│   └── wsgi.py
├── apps
│   └── [app_name]
├── static
├── templates
├── tests
├── manage.py
├── requirements.txt
├── .env
└── README.md
3. Cookiecutter Flask
Purpose: Flask web application with modular structure.

File Tree:


├── app
│   ├── templates
│   ├── static
│   ├── routes.py
│   ├── models.py
│   └── __init__.py
├── tests
├── migrations
├── config.py
├── requirements.txt
├── run.py
├── .env
└── README.md
4. Cookiecutter PyPackage
Purpose: Python package template for library development.

File Tree:


├── src
│   └── [package_name]
│       ├── __init__.py
│       └── module.py
├── tests
│   └── test_module.py
├── docs
├── .gitignore
├── LICENSE
├── README.md
├── setup.py
├── setup.cfg
└── requirements.txt
5. Cookiecutter FastAPI
Purpose: FastAPI application setup with best practices.

File Tree:


├── app
│   ├── api
│   ├── core
│   ├── models
│   ├── routers
│   ├── schemas
│   └── main.py
├── tests
├── alembic
├── requirements.txt
├── .env
├── Dockerfile
└── README.md
6. Cookiecutter React
Purpose: React.js frontend application setup.

File Tree:


├── public
│   ├── index.html
│   └── favicon.ico
├── src
│   ├── components
│   ├── pages
│   ├── assets
│   ├── App.js
│   ├── index.js
│   └── styles.css
├── tests
├── .gitignore
├── package.json
├── webpack.config.js
└── README.md
7. Cookiecutter Node.js
Purpose: Node.js backend application with Express.

File Tree:


├── src
│   ├── controllers
│   ├── models
│   ├── routes
│   ├── middlewares
│   └── app.js
├── tests
├── config
│   └── default.json
├── .gitignore
├── package.json
├── package-lock.json
├── .env
└── README.md
8. Cookiecutter Vue
Purpose: Vue.js frontend application setup.

File Tree:


├── public
│   └── index.html
├── src
│   ├── assets
│   ├── components
│   ├── views
│   ├── router
│   ├── store
│   ├── App.vue
│   └── main.js
├── tests
├── .gitignore
├── package.json
├── vue.config.js
└── README.md
9. Cookiecutter Spring Boot
Purpose: Spring Boot Java application setup.

File Tree:


├── src
│   ├── main
│   │   ├── java
│   │   │   └── com
│   │   │       └── example
│   │   │           └── [app_name]
│   │   │               ├── controllers
│   │   │               ├── models
│   │   │               ├── repositories
│   │   │               └── Application.java
│   │   └── resources
│   │       ├── application.properties
│   │       └── templates
│   └── test
│       └── java
│           └── com
│               └── example
│                   └── [app_name]
│                       └── ApplicationTests.java
├── .gitignore
├── pom.xml
├── README.md
└── Dockerfile
10. Cookiecutter Angular
Purpose: Angular frontend application setup.

File Tree:


├── e2e
├── src
│   ├── app
│   │   ├── components
│   │   ├── services
│   │   ├── app.module.ts
│   │   └── app.component.ts
│   ├── assets
│   ├── environments
│   ├── index.html
│   └── styles.css
├── .gitignore
├── angular.json
├── package.json
├── tsconfig.json
└── README.md
11. Cookiecutter Ruby on Rails
Purpose: Ruby on Rails web application setup.

File Tree:


├── app
│   ├── controllers
│   ├── models
│   ├── views
│   ├── helpers
│   ├── assets
│   └── mailers
├── config
│   ├── environments
│   ├── initializers
│   ├── locales
│   └── routes.rb
├── db
│   ├── migrate
│   └── seeds.rb
├── spec
├── log
├── tmp
├── public
├── Gemfile
├── Rakefile
├── config.ru
└── README.md
12. Cookiecutter Express
Purpose: Express.js backend application with MVC structure.

File Tree:


├── src
│   ├── controllers
│   ├── models
│   ├── routes
│   ├── views
│   ├── middlewares
│   └── app.js
├── config
│   └── default.json
├── tests
├── public
├── .gitignore
├── package.json
├── package-lock.json
├── .env
└── README.md
13. Cookiecutter Go
Purpose: Go application with modular structure.

File Tree:


├── cmd
│   └── [app_name]
│       └── main.go
├── pkg
│   └── [package]
├── internal
│   └── [module]
├── api
├── configs
├── scripts
├── tests
├── .gitignore
├── go.mod
├── go.sum
└── README.md
14. Cookiecutter Electron
Purpose: Electron desktop application setup.

File Tree:


├── src
│   ├── main.js
│   ├── renderer.js
│   ├── index.html
│   └── styles.css
├── assets
├── tests
├── .gitignore
├── package.json
├── webpack.config.js
├── main.js
└── README.md
15. Cookiecutter Laravel
Purpose: Laravel PHP framework application setup.

File Tree:


├── app
│   ├── Console
│   ├── Exceptions
│   ├── Http
│   ├── Models
│   └── Providers
├── bootstrap
├── config
├── database
│   ├── factories
│   ├── migrations
│   └── seeders
├── public
├── resources
│   ├── js
│   ├── lang
│   └── views
├── routes
├── storage
├── tests
├── .env
├── artisan
├── composer.json
├── package.json
└── README.md
16. Cookiecutter Svelte
Purpose: Svelte.js frontend application setup.

File Tree:


├── public
│   ├── index.html
│   └── global.css
├── src
│   ├── components
│   ├── routes
│   ├── stores
│   ├── App.svelte
│   └── main.js
├── tests
├── .gitignore
├── package.json
├── rollup.config.js
└── README.md
17. Cookiecutter Spark
Purpose: Apache Spark project setup.

File Tree:

├── src
│   ├── main
│   │   └── scala
│   │       └── [project_name]
│   │           └── App.scala
│   └── test
│       └── scala
│           └── [project_name]
│               └── AppTest.scala
├── data
├── notebooks
├── config
├── scripts
├── .gitignore
├── build.sbt
├── README.md
└── requirements.txt
18. Cookiecutter Hugo
Purpose: Hugo static site generator setup.

File Tree:

├── archetypes
├── content
│   ├── posts
│   └── about.md
├── layouts
│   ├── _default
│   ├── partials
│   └── index.html
├── static
│   ├── css
│   ├── js
│   └── images
├── themes
├── config.toml
├── .gitignore
└── README.md
19. Cookiecutter Jupyter
Purpose: Jupyter Notebook project setup.

File Tree:


├── notebooks
│   ├── 01_data_cleaning.ipynb
│   ├── 02_exploratory_analysis.ipynb
│   └── 03_modeling.ipynb
├── data
│   ├── raw
│   ├── processed
│   └── external
├── scripts
│   ├── data_cleaning.py
│   └── modeling.py
├── reports
│   └── figures
├── environment.yml
├── requirements.txt
├── .gitignore
└── README.md
20. Cookiecutter Sparkly
Purpose: Sparklyr (R) project setup for Apache Spark.

File Tree:
├── R
│   ├── app.R
│   ├── helpers.R
│   └── models.R
├── data
│   ├── raw
│   └── processed
├── tests
│   └── test_app.R
├── scripts
│   └── deploy.R
├── .gitignore
├── DESCRIPTION
├── NAMESPACE
├── README.md
└── LICENSE

**Output Requirement:**
Please only provide the title of the chosen template and the improved file structure with explanations, nothing else.
"""

        # Step 7: Generate improved project structure
        improved_structure = generate_improved_structure(uploaded_file, prompt)

    # Step 8: Save the improved project structure to the script's directory
    save_improved_structure(script_dir, improved_structure)

    logging.info("=== Project Structure Improvement Script Completed Successfully ===")
    print("Process completed. Check the log file for details.")

def generate_improved_structure(uploaded_file, prompt: str) -> str:
    """
    Uses Google Gemini to generate an improved project structure based on the prompt.
    Returns the improved project structure content.
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        logging.info(f"Initialized model: {MODEL_NAME}")

        inputs = [
            uploaded_file,
            "\n\n",
            prompt
        ]

        response = model.generate_content(inputs)
        improved_structure = response.text.strip()
        logging.info("Successfully generated improved project structure.")
        return improved_structure
    except Exception as e:
        logging.error(f"Failed to generate improved project structure: {e}")
        print(f"Error generating improved project structure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
