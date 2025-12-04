import tkinter as tk
from tkinter import PhotoImage
import calendar
from datetime import date
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
import threading
import random
import os
from datetime import datetime, timedelta, date
from weather import get_weather_for_city_json
from sekai_wakeword_detection import SekaiDetector

from send_audio import transcribe_wav_file
import requests
import os
from typecast_api import text_to_speech_api
from ai_talk import getSekaiResponse
from get_intent import getSekaiIntent
import json

today = date.today()
year = today.year
month = today.month
day = today.day

timesClicked = 0
isClicking = False

# ----------------------------
# LED Setup
# ----------------------------
LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# ----------------------------
# I2C Setup for ADS1115
# ----------------------------
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

# ----------------------------
# FSR on channel 0 (A0)
# ----------------------------
fsr_channel = AnalogIn(ads, 0)  # Renamed from 'chan' to 'fsr_channel' for clarity

# ----------------------------
# FSR Thresholds
# ----------------------------
FSR_THRESHOLD = 100  # Minimum value to detect touch
FSR_DOUBLE_TAP_TIMEOUT = 0.5  # Seconds between taps for double tap
FSR_COOLDOWN = 2.0  # Seconds before accepting new touch

# FSR state tracking
fsr_last_tap_time = 0
fsr_tap_count = 0
fsr_last_state = False
fsr_cooldown_until = 0
fsr_is_active = False

calendar.setfirstweekday(calendar.SUNDAY)

root = tk.Tk()
root.title("Calendar UI")

# Set fixed screen size
screen_width = 480
screen_height = 320
root.geometry(f"{screen_width}x{screen_height}")
root.resizable(False, False)
root.configure(bg="white")

# Current view state
current_view = "calendar"

# GRID SETUP
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

# Container for all views
container = tk.Frame(root, bg="white")
container.grid(row=0, column=0, sticky="nsew")
container.rowconfigure(0, weight=1)
container.columnconfigure(0, weight=1)

# CALENDAR VIEW FRAME
calendar_frame = tk.Frame(container, bg="white")
calendar_frame.grid(row=0, column=0, sticky="nsew")
calendar_frame.columnconfigure(0, weight=0)
calendar_frame.columnconfigure(1, weight=1)
calendar_frame.rowconfigure(0, weight=1)

# SEKAI FACE VIEW FRAME
face_frame = tk.Frame(container, bg="white")
face_frame.rowconfigure(0, weight=1)
face_frame.columnconfigure(0, weight=1)

# Label to display Sekai's face
face_label = tk.Label(face_frame, bg="white")
face_label.grid(row=0, column=0, sticky="nsew")

# Variables for mood and sleep timer
current_mood = "happy"
current_photo = None
sleep_timer_id = None
last_interaction_time = time.time()
idle_timer_start = None
is_idle = False

# Create Vosk-based wake word detector (listens for "hey girl")
wake_detector = SekaiDetector()

def load_image(image_name):
    """Load JPG image from sekai_faces folder and resize to fit screen"""
    try:
        from PIL import Image, ImageTk
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sekai_faces_dir = os.path.join(script_dir, "sekai_faces")
        
        # Try different possible extensions
        possible_extensions = ['.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG']
        image_path = None
        
        # First try with extension
        for ext in possible_extensions:
            test_path = os.path.join(sekai_faces_dir, image_name + ext)
            if os.path.exists(test_path):
                image_path = test_path
                print(f"Found image: {image_path}")
                break
        
        # If not found with extension, try the name as-is
        if not image_path:
            test_path = os.path.join(sekai_faces_dir, image_name)
            if os.path.exists(test_path):
                image_path = test_path
                print(f"Found image: {image_path}")
        
        if not image_path:
            print(f"Image not found: {image_name}")
            # List available files for debugging
            if os.path.exists(sekai_faces_dir):
                available_files = os.listdir(sekai_faces_dir)
                print(f"Available files in sekai_faces: {available_files}")
            else:
                print(f"Directory not found: {sekai_faces_dir}")
            return None
        
        # Open and resize image
        img = Image.open(image_path)
        
        # Calculate scaling to fit screen while maintaining aspect ratio
        img_width, img_height = img.size
        screen_ratio = screen_width / screen_height
        img_ratio = img_width / img_height
        
        if img_ratio > screen_ratio:
            # Image is wider than screen
            new_width = screen_width
            new_height = int(screen_width / img_ratio)
        else:
            # Image is taller than screen
            new_height = screen_height
            new_width = int(screen_height * img_ratio)
        
        # Resize with high-quality filtering
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(img)
        
        print(f"Loaded image: {image_name} ({img_width}x{img_height} -> {new_width}x{new_height})")
        return photo
        
    except ImportError as e:
        print(f"PIL import error: {e}")
        print("Install PIL with: pip install Pillow")
        return None
    except Exception as e:
        print(f"Error loading image {image_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

def activate_sekai(mode="touch", emotion=None):
    """
    Activate Sekai robot with specified emotion
    mode: "touch" (FSR), "voice" (wake word), or "manual"
    emotion: "happy", "angry", or None for random
    """
    global fsr_is_active, current_view
    
    print(f"\n{'🎯'*20}")
    print(f"🎯 SEKAI ACTIVATED via {mode.upper()}")
    print(f"{'🎯'*20}\n")
    
    # Determine emotion
    if emotion is None:
        if mode == "voice":
            emotion = "happy"
        else:
            emotion = random.choices(["happy", "angry"], weights=[7, 3])[0]
    
    # Switch to face view if not already
    if current_view != "face":
        root.after(0, show_sekai_face)
    else:
        reset_idle_timer()
    
    # Set the mood
    root.after(100, lambda e=emotion: set_mood(e))
    
    # Turn on LED (greeting phase)
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    # Play appropriate audio
    audio_folder = "voices_happy" if emotion == "happy" else "voices_angry"
    
    try:
        files = os.listdir(audio_folder)
        if files:
            audio_file = os.path.join(audio_folder, random.choice(files))
            print(f"Playing: {audio_file}")
            
            # Play greeting
            os.system(f"aplay {audio_file} 2>/dev/null")
            
            # After greeting, start recording
            start_recording()
            
        else:
            print(f"No audio files found in {audio_folder}")
            # Start recording immediately
            start_recording()
            
    except Exception as e:
        print(f"Audio error: {e}")
        # Start recording on error
        start_recording()
    
    # Set active state
    fsr_is_active = True


def start_recording():
    """Start recording a 5-second audio clip"""
    print("🎤 Starting 5-second recording...")
    
    # LED stays ON during recording
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    # Always save as recorded_command.wav (overwrites previous)
    recording_file = "recorded_command.wav"
    print(f"Recording to: {recording_file}")
    
    # Record for 5 seconds
    # Using arecord with parameters suitable for Whisper
    arecord_command = f"arecord -d 5 -f S16_LE -t wav -r 16000 -c 1 {recording_file}"
    return_code = os.system(arecord_command)
    
    if return_code == 0:
        print(f"✅ Recording finished: {recording_file}")
        if os.path.exists(recording_file):
            file_size = os.path.getsize(recording_file)
            print(f"📁 File size: {file_size} bytes ({file_size/1024:.1f} KB)")
        else:
            print(f"⚠️ File created but not found: {recording_file}")
    else:
        print(f"❌ Recording failed with code: {return_code}")
    
    
    result = transcribe_wav_file("recorded_command.wav")
    
    if result:
        print("Transcription:")
        print(result)

        API_KEY = "__pltMzLwjRtejoHYcjCEi984cBgKa6qMU6EiSkEs2Xne "  # Replace with your actual API key
    
        # Test text
        #test_text = ai_response

        ai_intent = getSekaiIntent(result)

        print(ai_intent)
        data = json.loads(ai_intent)  # Parse JSON string to dictionary
        command_value = data["command"]  # Access the value

        ai_response = getSekaiResponse(result, current_mood)

        # Generate speech
        audio_file = text_to_speech_api(ai_response, API_KEY)
        
        if audio_file and os.path.exists(audio_file):
            print(f"\n🎵 To play the audio on Raspberry Pi:")
            print(f"   aplay {audio_file}")
            
            # Optional: Play it automatically
            import subprocess
            try:
                subprocess.run(['aplay', audio_file], check=True)
            except:
                print("   Could not play audio automatically")
        
        else:
            print("Transcription failed.")
    # Deactivate Sekai after recording
    deactivate_sekai()


def deactivate_sekai():
    """Deactivate Sekai robot"""
    global fsr_is_active
    
    fsr_is_active = False
    GPIO.output(LED_PIN, GPIO.LOW)  # Turn off LED
    print("Sekai deactivated")
    
    # Reset to happy face after cooldown
    root.after(1000, lambda: set_mood("happy"))

# 2. Define the callback function IN YOUR MAIN SCRIPT
def on_wake_detected():
    """Called when wake word 'hey girl' is detected"""
    print("🔊 Wake word 'hey girl' detected! Activating Sekai...")
    activate_sekai(mode="voice", emotion="happy")

# 3. Monkey-patch the SekaiDetector class to add missing methods
def patched_on_hey_girl_detected(self):
    """Patched version that calls our callback"""
    print("👧 [SEKAI] Hey there! You called?")
    print("   *Activates robot mode*")
    
    # Call our callback
    if hasattr(self, '_wake_callback') and self._wake_callback:
        self._wake_callback()
    
    time.sleep(2)  # Cooldown period

# Replace the method in the class
SekaiDetector.on_hey_girl_detected = patched_on_hey_girl_detected

# 4. Add start() method to the class
def start_detector(self):
    """Start listening in background thread"""
    import threading
    print("🚀 Starting wake word detector in background...")
    self.listening_thread = threading.Thread(
        target=self.start_listening,
        args=(0,),  # Use default device
        daemon=True
    )
    self.listening_thread.start()
    print("✅ Wake word detector started")

SekaiDetector.start = start_detector

# 5. Add stop() method to the class  
def stop_detector(self):
    """Stop listening"""
    print("🛑 Stopping wake word detector...")

SekaiDetector.stop = stop_detector

# 6. Set the callback on the INSTANCE (not the class)
wake_detector._wake_callback = on_wake_detected

# 7. Start the detector
wake_detector.start()

def set_mood(mood):
    """Set Sekai's mood and display the appropriate JPG image"""
    global current_mood, current_photo, last_interaction_time, idle_timer_start, is_idle
    
    # Cancel any existing sleep timer
    if sleep_timer_id:
        root.after_cancel(sleep_timer_id)
    
    current_mood = mood
    last_interaction_time = time.time()
    
    # Reset idle state if we're setting a mood explicitly
    if mood != "sleeping":
        is_idle = False
        idle_timer_start = None
    
    print(f"Setting mood to: {mood}")
    
    # Define mood to file mapping
    mood_mapping = {
        'happy': ['happy', 'hapy', 'smile', 'smiling'],
        'angry': ['angry', 'mad', 'angry_face'],
        'sleeping': ['sleeping', 'sleep', 'asleep', 'zzz']
    }
    
    # Try different possible filenames for the mood
    photo = None
    possible_names = mood_mapping.get(mood, [mood])
    
    for name in possible_names:
        photo = load_image(name)
        if photo:
            print(f"Successfully loaded image for {mood} using filename: {name}")
            break
    
    if not photo:
        print(f"Failed to load any image for mood: {mood}")
        # Create a colored rectangle as fallback
        from PIL import Image, ImageDraw, ImageFont
        colors = {'happy': '#4CAF50', 'angry': '#F44336', 'sleeping': '#2196F3'}
        color = colors.get(mood, '#9E9E9E')
        
        # Create a simple colored image with text
        img = Image.new('RGB', (screen_width, screen_height), color)
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fall back to default
        try:
            # Try different font paths
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc"
            ]
            font = None
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, 40)
                        break
                    except:
                        continue
            if not font:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Draw text
        text = f"Sekai is {mood}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (screen_width - text_width) // 2
        y = (screen_height - text_height) // 2
        
        draw.text((x, y), text, fill="white", font=font)
        photo = ImageTk.PhotoImage(img)
    
    # Display the image
    face_label.config(image=photo)
    face_label.image = photo  # Keep reference to prevent garbage collection
    current_photo = photo
    
    # If setting to sleeping mood, don't start a new sleep timer
    if mood != "sleeping":
        reset_idle_timer()
    
    print(f"Mood set to: {mood}")

def reset_idle_timer():
    """Reset the idle timer that triggers sleeping mode"""
    global sleep_timer_id, idle_timer_start, is_idle
    
    if is_idle:
        return
    
    # Cancel existing timer
    if sleep_timer_id:
        root.after_cancel(sleep_timer_id)
    
    # Start new timer for 20 seconds
    sleep_timer_id = root.after(20000, go_to_sleep)
    idle_timer_start = time.time()
    print(f"Idle timer reset. Will sleep in 20 seconds.")

def go_to_sleep():
    """Switch to sleeping mode after 20 seconds of inactivity"""
    global current_mood, is_idle
    
    if current_view == "face" and current_mood != "sleeping":
        print("20 seconds idle detected. Going to sleep...")
        is_idle = True
        set_mood("sleeping")

def check_available_images():
    """Check if required image files exist and are readable"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sekai_faces_dir = os.path.join(script_dir, "sekai_faces")
    
    if not os.path.exists(sekai_faces_dir):
        print(f"ERROR: Directory not found: {sekai_faces_dir}")
        print("Please create a 'sekai_faces' folder in the same directory as this script.")
        return False
    
    print(f"Checking image files in: {sekai_faces_dir}")
    available_files = os.listdir(sekai_faces_dir)
    print(f"Available files: {available_files}")
    
    # Check for each mood
    moods = ['happy', 'angry', 'sleeping']
    image_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
    
    for mood in moods:
        found = False
        for filename in available_files:
            name_lower = filename.lower()
            mood_lower = mood.lower()
            
            # Check if mood is in filename and has image extension
            if mood_lower in name_lower and any(name_lower.endswith(ext) for ext in image_extensions):
                print(f"✓ Found {mood}: {filename}")
                found = True
                break
        
        if not found:
            print(f"✗ Missing or could not identify image for mood: {mood}")
            print(f"  Expected files like: {mood}.jpg, {mood}.png, etc.")
    
    return True

def fetch_weather(city="Lipa", api_key=None):
    try:
        data = get_weather_for_city_json(city, api_key=api_key)
        # Map Sekai UI format
        weather_data = {
            "current": {
                "day": data["current"]["day"],
                "time": datetime.now().strftime("%I:%M %p"),
                "temp": f"{data['current']['temp']}°C",
                "location": f"{data['city']}",
                "icon": f"{data['current']['simple'].replace(' ', '_')}_weather.png"
            },
            "forecast": []
        }
        for f in data["forecast"]:
            weather_data["forecast"].append({
                "day": f["day"],
                "time": datetime.now().strftime("%I:%M %p"),
                "temp": f"{f['temp']}°C",  # CHANGED FROM 'temp_day' TO 'temp'
                "icon": f"{f['simple'].replace(' ', '_')}_weather.png"
            })
        return weather_data
    except Exception as e:
        print(f"Failed to fetch weather: {e}")
        # Return fallback static data
        return {
            "current": {
                "day": "Monday",
                "time": "12:00 PM",
                "temp": "34 C",
                "location": "Lipa City",
                "icon": "partly_cloudy_weather.png"
            },
            "forecast": [
                {"day": "Tuesday", "time": "1:40 PM", "temp": "37C", "icon": "partly_cloudy_weather.png"},
                {"day": "Wednesday", "time": "1:40 PM", "temp": "37C", "icon": "sunny_weather.png"},
                {"day": "Thursday", "time": "1:40 PM", "temp": "37C", "icon": "thunderstorm_weather.png"},
                {"day": "Friday", "time": "1:40 PM", "temp": "37C", "icon": "cloudy_weather.png"}
            ]
        }

# Function to load weather icon with fallback
def load_weather_icon(icon_name, size=(80, 80)):
    try:
        from PIL import Image, ImageTk
        img_path = os.path.join("weather_assets", icon_name)
        img = Image.open(img_path)
        img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Error loading icon {icon_name}: {e}")
        # Try to load a default/fallback image
        try:
            # Try cloudy as fallback since it's most generic
            fallback_path = os.path.join("weather_assets", "cloudy_weather.png")
            if os.path.exists(fallback_path):
                img = Image.open(fallback_path)
                img = img.resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception as e2:
            print(f"Failed to load fallback icon: {e2}")
        return None

# WEATHER VIEW FRAME
weather_frame = tk.Frame(container, bg="white")
weather_frame.rowconfigure(0, weight=1)
weather_frame.columnconfigure(0, weight=1)
weather_frame.columnconfigure(1, weight=1)

# Weather data (test data matching your image)
weather_data = fetch_weather("Lipa")
    
def refresh_weather(interval=3600):  # every hour
    global weather_data
    weather_data = fetch_weather("Lipa")
    build_weather_view()
    root.after(interval * 1000, refresh_weather)

# Build weather view
def build_weather_view():
    # Clear existing widgets
    for widget in weather_frame.winfo_children():
        widget.destroy()
    
    # Left panel - Current weather
    left_weather = tk.Frame(weather_frame, bg="#f0f0f0", highlightbackground="gray", highlightthickness=1)
    left_weather.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    
    # Day and time
    tk.Label(left_weather, text=f"{weather_data['current']['day']} {weather_data['current']['time']}", 
             bg="#f0f0f0", font=("Arial", 14), anchor="w").pack(pady=(10, 5), padx=10, fill="x")
    
    # Weather icon
    icon_current = load_weather_icon(weather_data['current']['icon'], (120, 120))
    if icon_current:
        icon_label = tk.Label(left_weather, image=icon_current, bg="#f0f0f0")
        icon_label.image = icon_current  # Keep reference
        icon_label.pack(pady=10)
    
    # Temperature
    tk.Label(left_weather, text=weather_data['current']['temp'], 
             bg="#f0f0f0", font=("Arial", 32, "bold")).pack(pady=5)
    
    # Location
    tk.Label(left_weather, text=weather_data['current']['location'], 
             bg="#f0f0f0", font=("Arial", 16)).pack(pady=(5, 10))
    
    # Right panel - Forecast
    right_weather = tk.Frame(weather_frame, bg="white")
    right_weather.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
    
    for idx, forecast in enumerate(weather_data['forecast']):
        forecast_card = tk.Frame(right_weather, bg="#f0f0f0", highlightbackground="gray", highlightthickness=1)
        forecast_card.pack(fill="x", pady=5, padx=5)
        
        # Create inner frame for icon and text
        inner = tk.Frame(forecast_card, bg="#f0f0f0")
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Icon on the left
        icon = load_weather_icon(forecast['icon'], (40, 40))
        if icon:
            icon_lbl = tk.Label(inner, image=icon, bg="#f0f0f0")
            icon_lbl.image = icon  # Keep reference
            icon_lbl.pack(side="left", padx=(0, 10))
        
        # Text on the right
        text_frame = tk.Frame(inner, bg="#f0f0f0")
        text_frame.pack(side="left", fill="both", expand=True)
        
        tk.Label(text_frame, text=forecast['day'], bg="#f0f0f0", 
                font=("Arial", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(text_frame, text=f"{forecast['time']} - {forecast['temp']}", 
                bg="#f0f0f0", font=("Arial", 10), anchor="w").pack(fill="x")

# LEFT PANEL (Calendar view)
left_width = int(screen_width * 0.35)
left = tk.Frame(calendar_frame, bg="white", highlightbackground="black", highlightthickness=2, width=left_width)
left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
left.grid_propagate(False)

left.rowconfigure(0, weight=1)
left.rowconfigure(1, weight=4)
left.rowconfigure(2, weight=1)
left.columnconfigure(0, weight=1)

weekday_name = today.strftime("%A")
header = tk.Label(left, text=weekday_name, bg="#27ae60", fg="white",
                  font=("Arial", max(int(left_width*0.08), 12), "bold"))
header.grid(row=0, column=0, sticky="nsew")

day_label = tk.Label(left, text=str(day), bg="white", fg="black",
                     font=("Arial", max(int(left_width*0.3), 36), "bold"))
day_label.grid(row=1, column=0, sticky="nsew")

year_label = tk.Label(left, text=str(year), bg="white", fg="red",
                      font=("Arial", max(int(left_width*0.07), 14), "bold"))
year_label.grid(row=2, column=0, sticky="nsew")

# RIGHT PANEL (Calendar view)
right = tk.Frame(calendar_frame, bg="white")
right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

cols = 7
rows = 7
for i in range(cols):
    right.columnconfigure(i, weight=1)
for i in range(rows):
    right.rowconfigure(i, weight=1)

days = ["S", "M", "T", "W", "TH", "F", "S"]
colors = ["red", "gray", "gray", "gray", "gray", "gray", "red"]

# Headers
for i, d in enumerate(days):
    tk.Label(right, text=d, fg=colors[i], bg="white",
             font=("Arial", max(int(screen_width*0.02), 10), "bold")).grid(row=0, column=i, sticky="nsew", pady=(0, 2))

month_layout = calendar.monthcalendar(year, month)

# Calendar numbers
row_start = 1
for r, week in enumerate(month_layout):
    for c, num in enumerate(week):
        if num == 0:
            tk.Label(right, text="", bg="white").grid(row=row_start+r, column=c, sticky="nsew")
        elif num == day:
            frame = tk.Frame(right, bg="white", highlightbackground="#27ae60", highlightthickness=1)
            frame.grid(row=row_start+r, column=c, sticky="nsew", padx=1, pady=1)
            tk.Label(frame, text=str(num), bg="white", font=("Arial", max(int(screen_width*0.02), 10), "bold")).pack(expand=True)
        else:
            tk.Label(right, text=str(num), bg="white", font=("Arial", max(int(screen_width*0.02), 10), "bold")).grid(
                row=row_start+r, column=c, sticky="nsew", padx=1, pady=1
            )

# Build weather view
build_weather_view()
refresh_weather()  

# View switching functions
def show_calendar():
    global current_view
    current_view = "calendar"
    face_frame.grid_remove()
    weather_frame.grid_remove()
    calendar_frame.grid(row=0, column=0, sticky="nsew")
    root.title("Calendar UI")

def show_sekai_face():
    """Show Sekai's face and set initial mood"""
    global current_view
    current_view = "face"
    calendar_frame.grid_remove()
    weather_frame.grid_remove()
    face_frame.grid(row=0, column=0, sticky="nsew")
    
    # Reset idle timer when showing face view
    reset_idle_timer()
    
    # Set initial mood to happy
    set_mood("happy")
    root.title("Sekai is listening...")

def show_weather():
    global current_view
    current_view = "weather"
    calendar_frame.grid_remove()
    face_frame.grid_remove()
    weather_frame.grid(row=0, column=0, sticky="nsew")
    root.title("Weather")

def switch_view(event):
    key = event.char.lower()
    if key == 'a':
        show_calendar()
    elif key == 'b':
        show_sekai_face()
    elif key == 'c':
        show_weather()
    elif key == 'q':
        cleanup_and_quit()

def cleanup_and_quit():
    if 'wake_detector' in globals():
        wake_detector.stop()
    GPIO.cleanup()
    root.destroy()

# Bind keys
root.bind('<Key>', switch_view)

# Enhanced FSR monitoring function
def monitor_fsr():
    """Monitor FSR sensor for touch interactions"""
    global fsr_last_tap_time, fsr_tap_count, fsr_last_state, fsr_cooldown_until, fsr_is_active
    
    while True:
        try:
            current_time = time.time()
            fsr_value = fsr_channel.value
            
            # Check if we're in cooldown period
            if current_time < fsr_cooldown_until:
                fsr_last_state = False
                time.sleep(0.05)
                continue
            
            # Check if FSR is being pressed
            fsr_pressed = fsr_value > FSR_THRESHOLD
            
            # Detect press start (rising edge)
            if fsr_pressed and not fsr_last_state:
                print(f"FSR pressed: {fsr_value}")
                fsr_last_state = True
                
                # Check for double tap
                time_since_last_tap = current_time - fsr_last_tap_time
                
                if time_since_last_tap < FSR_DOUBLE_TAP_TIMEOUT:
                    fsr_tap_count += 1
                    print(f"Double tap detected! Count: {fsr_tap_count}")
                    
                    # Double tap activates Sekai
                    if fsr_tap_count >= 2 and not fsr_is_active:
                        # Schedule activation in main thread
                        root.after(0, lambda: activate_sekai(mode="touch"))
                        fsr_tap_count = 0
                        fsr_cooldown_until = current_time + FSR_COOLDOWN
                else:
                    # First tap
                    fsr_tap_count = 1
                    print("First tap detected")
                
                fsr_last_tap_time = current_time
            
            # Detect release (falling edge)
            elif not fsr_pressed and fsr_last_state:
                fsr_last_state = False
                print("FSR released")
            
            # Reset tap count if too much time has passed
            if current_time - fsr_last_tap_time > FSR_DOUBLE_TAP_TIMEOUT * 2:
                if fsr_tap_count > 0:
                    print(f"Tap timeout - resetting (had {fsr_tap_count} taps)")
                    fsr_tap_count = 0
            
            # Show FSR value for debugging (optional)
            # print(f"FSR: {fsr_value:5d} | State: {fsr_last_state} | Taps: {fsr_tap_count}")
            
            time.sleep(0.05)  # 50ms sampling rate
            
        except Exception as e:
            print(f"FSR monitoring error: {e}")
            time.sleep(0.1)

# Start FSR monitoring in separate thread
fsr_thread = threading.Thread(target=monitor_fsr, daemon=True)
fsr_thread.start()

# Handle window close
root.protocol("WM_DELETE_WINDOW", cleanup_and_quit)

try:
    # Check image files at startup
    check_available_images()

    # Start with face view
    show_sekai_face()
    root.mainloop()
except KeyboardInterrupt:
    cleanup_and_quit()
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    cleanup_and_quit()