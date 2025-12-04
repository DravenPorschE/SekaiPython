import requests
import json

API_KEY = "sk-gRXRiL2TT9FXCx0Cw1d9jw"
URL = "https://api.blackbox.ai/chat/completions"

def call_api(messages):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "blackboxai/openai/gpt-4",
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 500,
        "stream": False
    }

    response = requests.post(URL, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    return "[API Error]"


# -------------------------------------------------------
#  MAIN FUNCTION YOU WILL CALL
# -------------------------------------------------------
def getSekaiResponse(user_message, mood):
    """
    user_message
    mood → 'happy' or 'angry'
    returns: pure text output (Sekai's answer)
    """

    # Mood placeholder prompt
    mood_prompt = {
        "role": "system",
        "content": (
            f"You are Sekai if the user says a similar name like sky or sound phonetically like sekai you should still respond, but if its a completely different name like jeff or nothing short of sekai you should also mention it, a dramatic AI girl. Your current mood is **{mood.upper()}**.\n"
            f"{'Act extremely angry, loud, offended, sarcastic, and tsundere!!!!' if mood == 'angry' else 'Be very sweet, excited, cute, affectionate and playful!'}\n"
            "You MUST express strong emotions. ALWAYS stay in character.\n"
            "Output ONLY the response text. No explanations, no formatting."
        )
    }

    # Default identity prompt (reference style like SmartMeetingReader)
    base_prompt = {
        "role": "system",
        "content":
            "You are Sekai. You speak English unless a language is explicitly ordered.\n"
            "Your tone depends entirely on the supplied MOOD variable.\n"
            "Do NOT add extra JSON or metadata. Only produce raw dialogue text.\n"
            "If its all about a command like opening weather or opening of calendar, you should respond short by saying opening calendar or similar with a hint of the mood to spice it up a bit"
    }

    # User message injected as placeholder
    user_prompt = {
        "role": "user",
        "content": user_message
    }

    messages = [mood_prompt, base_prompt, user_prompt]

    # Call API
    result = call_api(messages)

    return result

