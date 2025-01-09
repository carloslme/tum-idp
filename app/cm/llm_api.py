import google.generativeai as genai
import time
from together import Together
import os

def gemini_api(prompt: str) -> str:
    """
    Get answer via API of gemini.
    NOTICE: time.sleep(6) is to avoid reach rate limit per minutes, this can be deleted if there's a pro account.
    :param prompt: the given prompt to LLM-gemini.
    :return: the answer from LLM.
    """
    YOUR_API_KEY = "AIzaSyCLTh9QBhEQlr1GLL8d_aRr_cZ1SIZdmTs"
    genai.configure(api_key=YOUR_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    response = model.generate_content(prompt)
    result = response.text
    time.sleep(6)
    return result

def together_api(prompt: str) -> str:
    """
    Get answer via API of together.ai.
    :param prompt: the given prompt to LLM-selected model.
    :return: the answer from LLM.
    """
    client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
    MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content
    return result