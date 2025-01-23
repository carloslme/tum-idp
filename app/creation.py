import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import yaml
from utils import toolkit, file_tree
import utils.llm_api as llm_api

def convert_repo_to_txt():
    pass

def create_part(part_name, info):
    '''
    Create the given section by gemini.
    :param: part_name: name of section
    :param: content: content of section
    btw, it seems that parameter can be improved. This will be done once UI is designed.
    :return: improved section
    '''
    with open("app/prompts/creation_prompt.yaml", 'r') as file:
        prompts_repo = yaml.safe_load(file)

    meta_prompt = prompts_repo["meta-prompt"]
    output_prompt = prompts_repo["output-meta"]
    # title need both title_prompt and about_prompt
    if info:
        output_prompt = prompts_repo["a_" + part_name] + info + "\n\n" + output_prompt
    
    prompt = (meta_prompt + "\n\n"
        + prompts_repo[part_name] + "\n\n"
        + output_prompt + "\n\n"
    )
    result = llm_api.together_api(prompt)

    # add section name if LLM misses it.
    if not result.startswith("##") and not part_name == "title":
        result = "## " + part_name[0].upper() + part_name[1:] + "\n\n" + result

    return result
