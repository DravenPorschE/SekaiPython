import requests
import os


def text_to_speech_api(text, api_key, voice_id="tc_632a759503f3cb7b9c8a717b"):
    """
    Convert text to speech using TypeCast.ai API
    Always saves as response_audio.wav (deletes previous)
    Returns the path to the saved audio file
    """
    url = "https://api.typecast.ai/v1/text-to-speech"
    
    payload = {
        "voice_id": voice_id,
        "text": text,
        "model": "ssfm-v21",
        "language": "eng",
        "prompt": {
            "emotion_preset": "normal",
            "emotion_intensity": 1
        },
        "output": {
            "volume": 100,
            "audio_pitch": 0,
            "audio_tempo": 1,
            "audio_format": "wav"
        },
        "seed": 42
    }
    
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    # Always use this filename
    filename = "response_audio.wav"
    
    try:
        print(f"📞 Calling TypeCast.ai API for text: '{text[:50]}...'")
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            # Get the audio content
            audio_content = response.content
            
            # Check if it's JSON (error) or binary (audio)
            if response.headers.get('Content-Type', '').startswith('application/json'):
                # It's JSON, check for errors
                data = response.json()
                if 'error' in data:
                    print(f"❌ API Error: {data['error']}")
                    return None
                else:
                    print("⚠️ Unexpected JSON response")
                    print(f"Response: {data}")
                    return None
            else:
                # Delete previous audio file if it exists
                if os.path.exists(filename):
                    os.remove(filename)
                
                # Save the audio file
                with open(filename, 'wb') as f:
                    f.write(audio_content)
                
                print(f"✅ Audio saved as: {filename}")
                print(f"   File size: {len(audio_content)} bytes")
                
                return filename
                
        else:
            print(f"❌ API request failed with status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error in TTS API call: {e}")
        return None

# Usage example
if __name__ == "__main__":
    API_KEY = "__pltMzLwjRtejoHYcjCEi984cBgKa6qMU6EiSkEs2Xne "  # Replace with your actual API key
    
    # Test text
    test_text = "Hello. I am Sekai, your personal robot assistant. How can I help you today?"
    
    # Generate speech
    audio_file = text_to_speech_api(test_text, API_KEY)
    
    if audio_file and os.path.exists(audio_file):
        print(f"\n🎵 To play the audio on Raspberry Pi:")
        print(f"   aplay {audio_file}")
        
        # Optional: Play it automatically
        import subprocess
        try:
            subprocess.run(['aplay', audio_file], check=True)
        except:
            print("   Could not play audio automatically")