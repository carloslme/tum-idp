import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import yaml
# from utils import toolkit, file_tree
import utils.llm_api as llm_api

def split_sections(file_path):
    '''
    Readme has a lot of sections. To improve section by section, we need to split it.
    All the sections start wil ## will be stored in the dict.
    :param: file_path: the original readme file
    :return: the dictionary of readme about each section. (key: section name; value: content)
    '''
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Content before first '##' is saved as title & about
    title_pattern = r"^(.*?)(?=\n## |\Z)" 
    title_match = re.match(title_pattern, content, re.DOTALL)
    title = title_match.group(0).strip() if title_match else ""

    # only match sections begin with '##'
    sections_pattern = r"(## .*?)\n(.*?)(?=\n## |\Z)"  
    matches = re.findall(sections_pattern, content, re.DOTALL)

    # result in dict
    sections = {"title": title}
    sections.update({match[0].removeprefix('## '): match[1].strip() for match in matches})

    sections = {key.lower().rstrip('s'): value for key, value in sections.items()}  

    return sections

def suggestion_box():
    '''
    Can-have function
    For those sections whose prompt we haven't prepared, we can ask users to write suggestions to improve them.
    '''
    pass

def check_section_existence(sections):
    '''
    Split the sections into 3 different types: empty, suggestion, ready.
    Empty: The readme should have this section but they haven't wrote it. 
        This type need readme creation.
    Suggestion: The original readme has this part but we haven't prompt for it.
        Users can write suggestion to improve this type of sections.
    Ready: The readme should have this section and we have prompts prepared.
        Use function improve_part(part_name, content)
    :param: sections: dictionary of readme sections 
    :return: empty_list: name list of empty sections.
    :return: suggestion_dict: dictionary of suggetion sections.
    :return: ready_dict: dictionary of ready sections.
    '''
    default_list = ['title', 'description', 'feature', 'requirement', 'installation', 'usage', 'contact', 'license']
    suggestion_dict = {}
    ready_dict = {}
    for index, (key, value) in enumerate(sections.items()):
        temp_key = key.lower().rstrip('s')
        if temp_key not in default_list:
            suggestion_dict.update({temp_key: value})
        else:
            if value.strip():
                default_list.remove(temp_key)
                ready_dict.update({temp_key: value})
    empty_list = default_list
    return empty_list, suggestion_dict, ready_dict

def improve_part(part_name, content, file_tree):
    '''
    Improve the given section by gemini.
    :param: part_name: name of section
    :param: content: content of section
    btw, it seems that parameter can be improved. This will be done once UI is designed.
    :return: improved section
    '''
    with open("app/prompts/improvements_prompt.yaml", 'r') as file:
        prompts_repo = yaml.safe_load(file)

    meta_prompt = prompts_repo["meta-prompt"]
    output_prompt = prompts_repo["output-meta"]
    # title need both title_prompt and about_prompt
    if file_tree:
        file_tree_prompt = prompts_repo["file-tree"] + "\n\n" + file_tree
    else:
        file_tree_prompt = ""

    if part_name == "title":
        prompt = (meta_prompt + "\n\n"
                  + prompts_repo["title"] + "\n\n"
                  + prompts_repo["about"] + "\n\n"
                  + output_prompt + "\n\n"
                  + content)
    else:
        prompt = (meta_prompt + "\n\n"
            + prompts_repo.get(part_name, "improve it.") + "\n\n"
            + file_tree_prompt + "\n\n"
            + output_prompt + "\n\n"
            + content)
        
    # During development I use together_ai since it's faster.
    print(prompt)
    result = llm_api.together_api(prompt)

    # add section name if LLM misses it.
    if not result.startswith("##") and not part_name == "title":
        result = "## " + part_name[0].upper() + part_name[1:] + "\n\n" + result

    return result

