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
import json
import queue
import pyaudio
import numpy as np

# ============================================================================
# GLOBAL VARIABLES AND SHARED STATE
# ============================================================================
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
fsr_channel = AnalogIn(ads, 0)

# ----------------------------
# FSR Thresholds
# ----------------------------
FSR_THRESHOLD = 100
FSR_DOUBLE_TAP_TIMEOUT = 0.5
FSR_COOLDOWN = 2.0

# FSR state tracking
fsr_last_tap_time = 0
fsr_tap_count = 0
fsr_last_state = False
fsr_cooldown_until = 0
fsr_is_active = False

# Thread-safe communication queues
wake_word_queue = queue.Queue()
ui_command_queue = queue.Queue()
audio_processing_queue = queue.Queue()

# Global state variables
current_view = "calendar"
current_mood = "happy"
current_photo = None
sleep_timer_id = None
last_interaction_time = time.time()
idle_timer_start = None
is_idle = False

# Wake word detector (will be initialized in its own thread)
wake_detector = None

# ============================================================================
# TKINTER UI SETUP (Main Thread)
# ============================================================================
def setup_tkinter_ui():
    """Setup Tkinter UI on main thread"""
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
    global current_view
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
    calendar_frame = create_calendar_view(container, screen_width, screen_height)
    
    # SEKAI FACE VIEW FRAME
    face_frame = tk.Frame(container, bg="white")
    face_frame.rowconfigure(0, weight=1)
    face_frame.columnconfigure(0, weight=1)
    
    # Label to display Sekai's face
    face_label = tk.Label(face_frame, bg="white")
    face_label.grid(row=0, column=0, sticky="nsew")
    
    # WEATHER VIEW FRAME
    weather_frame = create_weather_view(container, screen_width, screen_height)
    
    # Store frames for later access
    frames = {
        'calendar': calendar_frame,
        'face': face_frame,
        'weather': weather_frame,
        'face_label': face_label,
        'container': container,
        'root': root
    }
    
    # Start with face view
    switch_view_ui(frames, 'face')
    
    # Start UI command processor
    root.after(100, lambda: process_ui_commands(frames))
    
    # Start wake word queue processor
    root.after(1000, lambda: process_wake_word_queue(frames))
    
    return frames

def create_calendar_view(container, screen_width, screen_height):
    """Create calendar view frame"""
    calendar_frame = tk.Frame(container, bg="white")
    calendar_frame.columnconfigure(0, weight=0)
    calendar_frame.columnconfigure(1, weight=1)
    calendar_frame.rowconfigure(0, weight=1)
    
    # LEFT PANEL (Calendar view)
    left_width = int(screen_width * 0.35)
    left = tk.Frame(calendar_frame, bg="white", highlightbackground="black", 
                   highlightthickness=2, width=left_width)
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
                font=("Arial", max(int(screen_width*0.02), 10), "bold")).grid(
                    row=0, column=i, sticky="nsew", pady=(0, 2))
    
    month_layout = calendar.monthcalendar(year, month)
    
    # Calendar numbers
    row_start = 1
    for r, week in enumerate(month_layout):
        for c, num in enumerate(week):
            if num == 0:
                tk.Label(right, text="", bg="white").grid(
                    row=row_start+r, column=c, sticky="nsew")
            elif num == day:
                frame = tk.Frame(right, bg="white", highlightbackground="#27ae60", 
                                highlightthickness=1)
                frame.grid(row=row_start+r, column=c, sticky="nsew", padx=1, pady=1)
                tk.Label(frame, text=str(num), bg="white", 
                        font=("Arial", max(int(screen_width*0.02), 10), "bold")).pack(expand=True)
            else:
                tk.Label(right, text=str(num), bg="white", 
                        font=("Arial", max(int(screen_width*0.02), 10), "bold")).grid(
                            row=row_start+r, column=c, sticky="nsew", padx=1, pady=1)
    
    return calendar_frame

def create_weather_view(container, screen_width, screen_height):
    """Create weather view frame"""
    weather_frame = tk.Frame(container, bg="white")
    weather_frame.rowconfigure(0, weight=1)
    weather_frame.columnconfigure(0, weight=1)
    weather_frame.columnconfigure(1, weight=1)
    
    # This would be populated with actual weather data
    # For now, just return empty frame
    return weather_frame

# ============================================================================
# THREAD 1: WAKE WORD DETECTION (Separate Thread)
# ============================================================================
def wake_word_detection_thread():
    """Run wake word detection in separate thread"""
    print("[WakeWord Thread] Starting wake word detection...")
    
    try:
        # Create detector
        global wake_detector
        wake_detector = SekaiDetector()
        
        # Patch methods for thread-safe operation
        def patched_on_hey_girl_detected(self):
            """Patched version that sends to queue instead of direct callback"""
            print("[WakeWord Thread] 'hey girl' detected!")
            print("[WakeWord Thread] Sending wake word detection to UI thread...")
            
            # Send to queue instead of calling directly
            wake_word_queue.put(True)
            
            # Original sleep (in thread, doesn't block UI)
            time.sleep(2)
        
        SekaiDetector.on_hey_girl_detected = patched_on_hey_girl_detected
        
        # Add start method that runs in this thread
        def start_detector_thread(self, device_index=None):
            """Start listening in this thread"""
            print(f"[WakeWord Thread] Starting detector on device {device_index}...")
            try:
                # Start listening (blocks this thread, not UI thread)
                self.start_listening(device_index)
            except Exception as e:
                print(f"[WakeWord Thread] Error: {e}")
                import traceback
                traceback.print_exc()
        
        SekaiDetector.start = start_detector_thread
        
        # Start detection (this will block this thread, which is OK)
        wake_detector.start()
        
    except Exception as e:
        print(f"[WakeWord Thread] Failed to start: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# THREAD 2: FSR MONITORING (Separate Thread)
# ============================================================================
def fsr_monitoring_thread():
    """Monitor FSR sensor in separate thread"""
    print("[FSR Thread] Starting FSR monitoring...")
    
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
                print(f"[FSR Thread] FSR pressed: {fsr_value}")
                fsr_last_state = True
                
                # Check for double tap
                time_since_last_tap = current_time - fsr_last_tap_time
                
                if time_since_last_tap < FSR_DOUBLE_TAP_TIMEOUT:
                    fsr_tap_count += 1
                    print(f"[FSR Thread] Double tap detected! Count: {fsr_tap_count}")
                    
                    # Double tap activates Sekai
                    if fsr_tap_count >= 2 and not fsr_is_active:
                        print("[FSR Thread] Activating Sekai via double tap")
                        # Send activation command to UI thread
                        ui_command_queue.put(('activate', 'touch', None))
                        fsr_tap_count = 0
                        fsr_cooldown_until = current_time + FSR_COOLDOWN
                else:
                    # First tap
                    fsr_tap_count = 1
                    print("[FSR Thread] First tap detected")
                
                fsr_last_tap_time = current_time
            
            # Detect release (falling edge)
            elif not fsr_pressed and fsr_last_state:
                fsr_last_state = False
                print("[FSR Thread] FSR released")
            
            # Reset tap count if too much time has passed
            if current_time - fsr_last_tap_time > FSR_DOUBLE_TAP_TIMEOUT * 2:
                if fsr_tap_count > 0:
                    print(f"[FSR Thread] Tap timeout - resetting")
                    fsr_tap_count = 0
            
            time.sleep(0.05)  # 50ms sampling rate
            
        except Exception as e:
            print(f"[FSR Thread] Error: {e}")
            time.sleep(0.1)

# ============================================================================
# THREAD 3: AUDIO PROCESSING (Separate Thread)
# ============================================================================
def audio_processing_thread():
    """Handle audio recording and processing in separate thread"""
    print("[Audio Thread] Starting audio processing...")
    
    while True:
        try:
            # Check for audio processing requests
            if not audio_processing_queue.empty():
                command = audio_processing_queue.get_nowait()
                if command == 'record':
                    print("[Audio Thread] Starting recording...")
                    record_audio()
                elif command == 'process':
                    print("[Audio Thread] Processing audio...")
                    process_audio()
                    
        except queue.Empty:
            pass
        
        time.sleep(0.1)

def record_audio():
    """Record audio (runs in audio thread)"""
    print("[Audio Thread] Recording audio...")
    
    # LED stays ON during recording
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    recording_file = "recorded_command.wav"
    print(f"[Audio Thread] Recording to: {recording_file}")
    
    # Record for 5 seconds
    arecord_command = f"arecord -d 5 -f S16_LE -t wav -r 16000 -c 1 {recording_file}"
    return_code = os.system(arecord_command)
    
    if return_code == 0:
        print(f"[Audio Thread] Recording finished")
        # Queue for processing
        audio_processing_queue.put('process')
    else:
        print(f"[Audio Thread] Recording failed")

def process_audio():
    """Process recorded audio (runs in audio thread)"""
    print("[Audio Thread] Processing audio file...")
    
    try:
        result = transcribe_wav_file("recorded_command.wav")
        
        if result:
            print("[Audio Thread] Transcription complete")
            print(f"Transcription: {result}")
            
            API_KEY = "__pltMzLwjRtejoHYcjCEi984cBgKa6qMU6EiSkEs2Xne "
            
            ai_intent = getSekaiIntent(result)
            print(f"[Audio Thread] Intent: {ai_intent}")
            
            data = json.loads(ai_intent)
            command_value = data["command"]
            
            ai_response = getSekaiResponse(result, current_mood)
            
            # Generate speech
            audio_file = text_to_speech_api(ai_response, API_KEY)
            
            if audio_file and os.path.exists(audio_file):
                print(f"[Audio Thread] Playing response audio")
                import subprocess
                try:
                    subprocess.run(['aplay', audio_file], check=True)
                except:
                    print("[Audio Thread] Could not play audio")
            
            # Send deactivation command to UI
            ui_command_queue.put(('deactivate',))
            
    except Exception as e:
        print(f"[Audio Thread] Processing error: {e}")
        import traceback
        traceback.print_exc()
        ui_command_queue.put(('deactivate',))

# ============================================================================
# UI COMMAND PROCESSING (Main Thread)
# ============================================================================
def process_ui_commands(frames):
    """Process commands from other threads (runs in main thread)"""
    try:
        while not ui_command_queue.empty():
            command = ui_command_queue.get_nowait()
            
            if command[0] == 'activate':
                mode = command[1] if len(command) > 1 else 'manual'
                emotion = command[2] if len(command) > 2 else None
                activate_sekai_ui(frames, mode, emotion)
            elif command[0] == 'deactivate':
                deactivate_sekai_ui(frames)
            elif command[0] == 'set_mood':
                mood = command[1]
                set_mood_ui(frames, mood)
            elif command[0] == 'switch_view':
                view = command[1]
                switch_view_ui(frames, view)
            elif command[0] == 'change_bg_color':  # NEW: Handle background color change
                color = command[1]
                change_background_color(frames, color)
                
    except queue.Empty:
        pass
    
    # Schedule next check
    frames['root'].after(100, lambda: process_ui_commands(frames))

def process_wake_word_queue(frames):
    """Process wake word detections from queue"""
    try:
        while not wake_word_queue.empty():
            wake_word_queue.get_nowait()
            print("[UI Thread] Processing wake word detection...")
            
            # Change background to red to show detection
            ui_command_queue.put(('change_bg_color', 'red'))
            
            # Flash red for 1 second, then change back to white
            frames['root'].after(1000, lambda: ui_command_queue.put(('change_bg_color', 'white')))
            
            # Also activate Sekai as before
            ui_command_queue.put(('activate', 'voice', 'happy'))
            
    except queue.Empty:
        pass
    
    # Schedule next check
    frames['root'].after(100, lambda: process_wake_word_queue(frames))

# ============================================================================
# UI FUNCTIONS (Main Thread Only)
# ============================================================================
def change_background_color(frames, color):
    """Change the background color of the Tkinter window"""
    print(f"[UI Thread] Changing background color to {color}")
    
    # Change root window background
    frames['root'].configure(bg=color)
    
    # Change container background
    frames['container'].configure(bg=color)
    
    # Change current frame background based on view
    if current_view == 'calendar':
        frames['calendar'].configure(bg=color)
    elif current_view == 'face':
        frames['face'].configure(bg=color)
    elif current_view == 'weather':
        frames['weather'].configure(bg=color)

def load_image(image_name, screen_width=480, screen_height=320):
    """Load JPG image from sekai_faces folder"""
    try:
        from PIL import Image, ImageTk
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sekai_faces_dir = os.path.join(script_dir, "sekai_faces")
        
        possible_extensions = ['.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG']
        image_path = None
        
        for ext in possible_extensions:
            test_path = os.path.join(sekai_faces_dir, image_name + ext)
            if os.path.exists(test_path):
                image_path = test_path
                break
        
        if not image_path:
            test_path = os.path.join(sekai_faces_dir, image_name)
            if os.path.exists(test_path):
                image_path = test_path
        
        if not image_path:
            print(f"Image not found: {image_name}")
            return None
        
        img = Image.open(image_path)
        
        # Calculate scaling
        img_width, img_height = img.size
        screen_ratio = screen_width / screen_height
        img_ratio = img_width / img_height
        
        if img_ratio > screen_ratio:
            new_width = screen_width
            new_height = int(screen_width / img_ratio)
        else:
            new_height = screen_height
            new_width = int(screen_height * img_ratio)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        
        return photo
        
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def activate_sekai_ui(frames, mode="touch", emotion=None):
    """Activate Sekai - called from UI thread"""
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
        switch_view_ui(frames, "face")
    else:
        reset_idle_timer_ui(frames)
    
    # Set the mood
    set_mood_ui(frames, emotion)
    
    # Turn on LED
    GPIO.output(LED_PIN, GPIO.HIGH)
    
    # Play appropriate audio in separate thread
    audio_folder = "voices_happy" if emotion == "happy" else "voices_angry"
    
    try:
        files = os.listdir(audio_folder)
        if files:
            audio_file = os.path.join(audio_folder, random.choice(files))
            print(f"Playing: {audio_file}")
            
            # Play greeting in background
            import subprocess
            subprocess.Popen(['aplay', audio_file])
            
            # Start recording after delay
            frames['root'].after(2000, lambda: audio_processing_queue.put('record'))
            
        else:
            print(f"No audio files found in {audio_folder}")
            frames['root'].after(100, lambda: audio_processing_queue.put('record'))
            
    except Exception as e:
        print(f"Audio error: {e}")
        frames['root'].after(100, lambda: audio_processing_queue.put('record'))
    
    # Set active state
    fsr_is_active = True

def deactivate_sekai_ui(frames):
    """Deactivate Sekai - called from UI thread"""
    global fsr_is_active
    
    fsr_is_active = False
    GPIO.output(LED_PIN, GPIO.LOW)
    print("Sekai deactivated")
    
    # Reset to happy face after cooldown
    frames['root'].after(1000, lambda: set_mood_ui(frames, "happy"))

def set_mood_ui(frames, mood):
    """Set Sekai's mood - called from UI thread"""
    global current_mood, current_photo, last_interaction_time, idle_timer_start, is_idle, sleep_timer_id
    
    # Cancel any existing sleep timer
    if sleep_timer_id:
        frames['root'].after_cancel(sleep_timer_id)
    
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
    
    # Try different possible filenames
    photo = None
    possible_names = mood_mapping.get(mood, [mood])
    
    for name in possible_names:
        photo = load_image(name)
        if photo:
            print(f"Successfully loaded image for {mood}")
            break
    
    if not photo:
        print(f"Failed to load image for mood: {mood}")
        # Create fallback
        try:
            from PIL import Image, ImageDraw, ImageFont
            colors = {'happy': '#4CAF50', 'angry': '#F44336', 'sleeping': '#2196F3'}
            color = colors.get(mood, '#9E9E9E')
            
            img = Image.new('RGB', (480, 320), color)
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()
            
            text = f"Sekai is {mood}"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (480 - text_width) // 2
            y = (320 - text_height) // 2
            
            draw.text((x, y), text, fill="white", font=font)
            photo = ImageTk.PhotoImage(img)
        except:
            pass
    
    # Display the image
    if photo:
        frames['face_label'].config(image=photo)
        frames['face_label'].image = photo
        current_photo = photo
    
    # If setting to sleeping mood, don't start a new sleep timer
    if mood != "sleeping":
        reset_idle_timer_ui(frames)
    
    print(f"Mood set to: {mood}")

def reset_idle_timer_ui(frames):
    """Reset idle timer"""
    global sleep_timer_id, idle_timer_start, is_idle
    
    if is_idle:
        return
    
    if sleep_timer_id:
        frames['root'].after_cancel(sleep_timer_id)
    
    sleep_timer_id = frames['root'].after(20000, lambda: go_to_sleep_ui(frames))
    idle_timer_start = time.time()
    print(f"Idle timer reset")

def go_to_sleep_ui(frames):
    """Go to sleep"""
    global current_mood, is_idle, current_view
    
    if current_view == "face" and current_mood != "sleeping":
        print("20 seconds idle detected. Going to sleep...")
        is_idle = True
        set_mood_ui(frames, "sleeping")

def switch_view_ui(frames, view):
    """Switch views"""
    global current_view
    
    current_view = view
    
    # Hide all frames
    frames['calendar'].grid_remove()
    frames['face'].grid_remove()
    frames['weather'].grid_remove()
    
    # Show selected frame
    if view == 'calendar':
        frames['calendar'].grid(row=0, column=0, sticky="nsew")
        frames['root'].title("Calendar UI")
    elif view == 'face':
        frames['face'].grid(row=0, column=0, sticky="nsew")
        frames['root'].title("Sekai is listening...")
        reset_idle_timer_ui(frames)
        set_mood_ui(frames, "happy")
    elif view == 'weather':
        frames['weather'].grid(row=0, column=0, sticky="nsew")
        frames['root'].title("Weather")

def switch_view_key(event, frames):
    """Handle keyboard input"""
    key = event.char.lower()
    if key == 'a':
        switch_view_ui(frames, 'calendar')
    elif key == 'b':
        switch_view_ui(frames, 'face')
    elif key == 'c':
        switch_view_ui(frames, 'weather')
    elif key == 'q':
        cleanup_and_quit(frames)

def cleanup_and_quit(frames):
    """Cleanup and quit"""
    print("Cleaning up...")
    
    if wake_detector:
        try:
            wake_detector.stop()
        except:
            pass
    
    GPIO.cleanup()
    frames['root'].destroy()

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    """Main function to start all threads"""
    print("="*50)
    print("Starting Sekai Robot Interface")
    print("Wake word test: Say 'hey girl' to see red background")
    print("="*50)
    
    # Setup Tkinter UI
    frames = setup_tkinter_ui()
    
    # Bind keyboard
    frames['root'].bind('<Key>', lambda event: switch_view_key(event, frames))
    
    # Setup cleanup
    frames['root'].protocol("WM_DELETE_WINDOW", lambda: cleanup_and_quit(frames))
    
    # Start FSR monitoring thread
    print("Starting FSR monitoring thread...")
    fsr_thread = threading.Thread(target=fsr_monitoring_thread, daemon=True)
    fsr_thread.start()
    
    # Start wake word detection thread
    print("Starting wake word detection thread...")
    wake_thread = threading.Thread(target=wake_word_detection_thread, daemon=True)
    wake_thread.start()
    
    # Start audio processing thread
    print("Starting audio processing thread...")
    audio_thread = threading.Thread(target=audio_processing_thread, daemon=True)
    audio_thread.start()
    
    # Start with face view
    switch_view_ui(frames, 'face')
    
    # Start main loop
    print("\n" + "="*50)
    print("Main loop starting...")
    print("Say 'hey girl' - the background should turn RED")
    print("Press 'q' to quit")
    print("="*50 + "\n")
    
    try:
        frames['root'].mainloop()
    except KeyboardInterrupt:
        cleanup_and_quit(frames)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup_and_quit(frames)

if __name__ == "__main__":
    main()