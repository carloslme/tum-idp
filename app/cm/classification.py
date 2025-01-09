import json
import pandas as pd
from sklearn.metrics import classification_report
import os
import re
from llm_api import gemini_api, together_api
import yaml

def get_dataset():
    """
    ***Not useful for the repo, only for test***
    Get local dataset
    """
    file_path = "autoGPT_dataset.csv"
    df = pd.read_csv(file_path)
    # random_df = df.sample(n=100, random_state=42)
    # random_df.to_csv('random_output.csv', index=False, encoding='utf-8')
    x = df["Code Changes"].tolist()
    y_true = df["type"].tolist()
    return x, y_true

def get_prompt() -> str:
    """
    Get prompt from yaml file.
    :return: A prompt to guide LLM to get a better answer.
    """
    with open("prompts.yaml", 'r') as file:
        prompts_repo = yaml.safe_load(file)

    generation_prompts = prompts_repo["generation"]
    task_description = generation_prompts["task_description"]
    domain_knowledge = generation_prompts["domain_knowledge"]
    solution_guidance = generation_prompts["solution_guidance"]
    guideline_for_cm = generation_prompts["guideline_for_cm"]
    general_task = generation_prompts["general_task"]
    output_formatting = generation_prompts["output_formatting"]
    example_output = generation_prompts["example_output"]
    input_code = generation_prompts["input_code"]

    prompt = (task_description + "\n\n" 
    + domain_knowledge + "\n\n" 
    + solution_guidance + "\n\n" 
    + guideline_for_cm + "\n\n" 
    + general_task + "\n\n" 
    + output_formatting + "\n\n" 
    + example_output + "\n\n" 
    + input_code + "\n\n")

    return prompt
    

def get_answer(x: list[str], prompt: str) -> list[str]:
    """
    Get answers from LLM.
    This function can be used for multiple commit message modification.
    :param x: A list of code change of commit messages.
    :param prompt: prompt to guide LLM to generate desired answer.
    :return: A list of LLM's answers.
    """
    raw_answer = []
    # Print the progress, can be improved by a progress bar.
    count = 1
    # Having a result folder is help for to analyze the result, but only for test.
    os.makedirs("output_folder/")
    for code_change in x:

        query = prompt + code_change

        result = together_api(query)
        raw_answer.append(result)

        # Having a result folder is help for to analyze the result, but only for test.
        with open("output_folder/answer" + str(count) + ".txt", "w") as f:
            f.write(f"{result}\n")

        print(count)
        count += 1

    return raw_answer

def json_converter(raw_answer):
    """
    ***Not useful for the repo, only for test***
    To test the accuracy of the CM classification, json format is easy to assemble the answer and calculate.
    """
    y_pred = []
    for ra in raw_answer:
        json_match = re.search(r'\{.*?\}', ra, re.DOTALL)
        if json_match:
            json_str = json_match.group(0) 
            # may problematic, e.g. type error, fix later
            data = json.loads(json_str)
            y_pred.append(data["type"])
        else:
            y_pred.append("None")
    return y_pred

def pipeline():
    """
    ***Not useful for the repo, only for test***
    Pipeline to get the result and calculate the accuracy.
    """
    x, y_true = get_dataset()
    prompt = get_prompt()
    print(prompt)
    raw_answer = get_answer(x, prompt)
    y_pred = json_converter(raw_answer)
    result = classification_report(y_true, y_pred)
    with open("y_pred.txt", "w") as f:
        for item in y_pred:
            f.write(f"{item}\n")

    with open("y_true.txt", "w") as f:
        for item in y_true:
            f.write(f"{item}\n")

    with open("classification_result.json", "w") as f:
        json.dump(result, f, indent=4)
    

if __name__ == "__main__":
    pipeline()