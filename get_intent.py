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
def getSekaiIntent(user_command):

    # Default identity prompt (reference style like SmartMeetingReader)
    base_prompt = {
        "role": "system",
        "content":
            "You are sekai, a companion ai designed to understand human intent\n"
            "Depending on the command of the user, you must output a json formatted style ouptut\n"
            "There are only three intents you need to understand:\n"
            "1. Is all about opening the calendar, you cant add an event on calendar, and you cant change the current display of date"
            "2. Is all about opening the weather view, you cant show more than past 4 days of the current day, like today is Monday, you can only show Tueday to Friday\n"
            "But you can still show saturday and sunday if the day changes like to get the sunday forecast, the day must be Wednesday\n"
            "If none of those two did not meet with the intent of the command or did not match with the command of the user, you must instead respond with json formatted text where it says None\n"
            "Now all about the JSON Formatting, the format should follow this:\n"
            "{"
            '"command":' "open_calendar | open weather | none"
            "}"
    }

    # User message injected as placeholder
    user_prompt = {
        "role": "user",
        "content": user_command
    }

    messages = [base_prompt, user_prompt]

    # Call API
    result = call_api(messages)
    import json

    return result

