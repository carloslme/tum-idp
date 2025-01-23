import google.generativeai as genai
from together import Together
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

def together_api(prompt: str) -> str:
    from together import Together

    client = Together(api_key="09198cedc0012a80b53ba6353de2571ff2aaf4523ef59ce9de0b61045bc0f3cd")

    response = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3-8B-Instruct-Turbo",
        messages=[{"role": "user", 
                   "content": prompt}],
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    prompt = "whats the capital of france?"
    print (together_api(prompt))
