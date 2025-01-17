import google.generativeai as genai
import time

def gemini_api(prompt: str) -> str:
    """
    Get answer via API of gemini.
    NOTICE: time.sleep(5) is to avoid reach rate limit per minutes, this can be deleted if there's a pro account.
    :param prompt: the given prompt to LLM-gemini.
    :return: the answer from LLM.
    """
    YOUR_API_KEY = "AIzaSyCLTh9QBhEQlr1GLL8d_aRr_cZ1SIZdmTs"
    genai.configure(api_key=YOUR_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    response = model.generate_content(prompt)
    result = response.text
    # Request per minute is 15, sleep for 5 seconds can avoid crash.
    time.sleep(5)
    return result

