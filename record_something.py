import tkinter as tk
import calendar
from datetime import date
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
import threading
import os
import queue
import subprocess
from PIL import Image, ImageTk
from datetime import datetime
import random

# ============================================================================
# GLOBAL VARIABLES AND SHARED STATE
# ============================================================================

# Screen dimensions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Today's date
today = date.today()
year = today.year
month = today.month
day = today.day

# ----------------------------
# LED Setup
# ----------------------------
LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

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

# Thread-safe communication queues
fsr_event_queue = queue.Queue()
ui_command_queue = queue.Queue()

# Thread control flag
fsr_thread_running = True

# Tkinter references
root = None
container = None

# View frames
calendar_frame = None
face_frame = None
weather_frame = None
face_label = None

# Current state
current_view = "face"  # CHANGED: Start with face view
current_mood = "happy"
current_photo = None

# Image cache
image_cache = {}

# Audio device
AUDIO_DEVICE = "plughw:2,0"

# Mood probability (7 happy : 3 angry)
MOOD_PROBABILITIES = {"happy": 0.7, "angry": 0.3}

# ============================================================================
# MODULAR VIEW FUNCTIONS
# ============================================================================

def show_calendar():
    """Show calendar view - press 'a'"""
    global current_view, calendar_frame
    
    print("[UI] Showing calendar view")
    
    if current_view == "calendar":
        return calendar_frame
    
    # Hide other views
    hide_all_views()
    
    # Create calendar if it doesn't exist
    if not calendar_frame or not calendar_frame.winfo_exists():
        calendar_frame = create_calendar_view()
        calendar_frame.grid(row=0, column=0, sticky="nsew")
    else:
        calendar_frame.grid(row=0, column=0, sticky="nsew")
    
    current_view = "calendar"
    update_title("Calendar")
    
    return calendar_frame

def show_face():
    """Show Sekai's face with random mood (70% happy, 30% angry) - press 'b'"""
    global current_view, face_frame, current_mood
    
    # Choose random mood based on probabilities
    mood = random.choices(
        list(MOOD_PROBABILITIES.keys()), 
        weights=list(MOOD_PROBABILITIES.values())
    )[0]
    
    print(f"[UI] Showing Sekai face with random mood: {mood} (70% happy, 30% angry)")
    
    if current_view == "face" and current_mood == mood:
        return face_frame
    
    # Hide other views
    hide_all_views()
    
    # Create face frame if it doesn't exist
    if not face_frame or not face_frame.winfo_exists():
        face_frame = create_face_view()
        face_frame.grid(row=0, column=0, sticky="nsew")
    else:
        face_frame.grid(row=0, column=0, sticky="nsew")
    
    current_view = "face"
    current_mood = mood
    
    # Set the mood
    set_face_mood(mood)
    
    update_title(f"Sekai is {mood}")
    
    return face_frame

def show_default_face():
    """Show default happy face - used at startup"""
    global current_view, face_frame, current_mood
    
    print("[UI] Showing default happy face")
    
    # Hide other views
    hide_all_views()
    
    # Create face frame if it doesn't exist
    if not face_frame or not face_frame.winfo_exists():
        face_frame = create_face_view()
        face_frame.grid(row=0, column=0, sticky="nsew")
    else:
        face_frame.grid(row=0, column=0, sticky="nsew")
    
    current_view = "face"
    current_mood = "happy"
    
    # Set to happy mood
    set_face_mood("happy")
    
    update_title("Sekai is happy")
    
    return face_frame

def show_weather():
    """Show weather view - press 'c'"""
    global current_view, weather_frame
    
    print("[UI] Showing weather view")
    
    if current_view == "weather":
        return weather_frame
    
    # Hide other views
    hide_all_views()
    
    # Create weather frame if it doesn't exist
    if not weather_frame or not weather_frame.winfo_exists():
        weather_frame = create_weather_view()
        weather_frame.grid(row=0, column=0, sticky="nsew")
    else:
        weather_frame.grid(row=0, column=0, sticky="nsew")
    
    current_view = "weather"
    update_title("Weather")
    
    return weather_frame

def hide_all_views():
    """Hide all view frames"""
    if calendar_frame and calendar_frame.winfo_exists():
        calendar_frame.grid_remove()
    if face_frame and face_frame.winfo_exists():
        face_frame.grid_remove()
    if weather_frame and weather_frame.winfo_exists():
        weather_frame.grid_remove()

def update_title(title):
    """Update window title"""
    if root and root.winfo_exists():
        root.title(title)

# ============================================================================
# VIEW CREATION FUNCTIONS
# ============================================================================

def create_calendar_view():
    """Create calendar view frame"""
    frame = tk.Frame(container, bg="white")
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1)
    
    # LEFT PANEL
    left_width = int(SCREEN_WIDTH * 0.35)
    left = tk.Frame(frame, bg="white", highlightbackground="black", 
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
    
    # RIGHT PANEL
    right = tk.Frame(frame, bg="white")
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
                font=("Arial", max(int(SCREEN_WIDTH*0.02), 10), "bold")).grid(
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
                frame_num = tk.Frame(right, bg="white", highlightbackground="#27ae60", 
                                   highlightthickness=1)
                frame_num.grid(row=row_start+r, column=c, sticky="nsew", padx=1, pady=1)
                tk.Label(frame_num, text=str(num), bg="white", 
                        font=("Arial", max(int(SCREEN_WIDTH*0.02), 10), "bold")).pack(expand=True)
            else:
                tk.Label(right, text=str(num), bg="white", 
                        font=("Arial", max(int(SCREEN_WIDTH*0.02), 10), "bold")).grid(
                            row=row_start+r, column=c, sticky="nsew", padx=1, pady=1)
    
    return frame

def create_face_view():
    """Create face view frame"""
    global face_label
    
    frame = tk.Frame(container, bg="black")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    
    # Face label (will display images)
    face_label = tk.Label(frame, bg="black")
    face_label.grid(row=0, column=0, sticky="nsew")
    
    return frame

def create_weather_view():
    """Create weather view frame"""
    frame = tk.Frame(container, bg="white")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    
    # Left panel - Current weather
    left_weather = tk.Frame(frame, bg="#f0f0f0", highlightbackground="gray", 
                           highlightthickness=1)
    left_weather.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    
    # Day and time
    current_day = datetime.now().strftime("%A")
    current_time = datetime.now().strftime("%I:%M %p")
    tk.Label(left_weather, text=f"{current_day} {current_time}", 
             bg="#f0f0f0", font=("Arial", 14), anchor="w").pack(pady=(10, 5), padx=10, fill="x")
    
    # Temperature
    tk.Label(left_weather, text="34°C", bg="#f0f0f0", 
             font=("Arial", 32, "bold")).pack(pady=20)
    
    # Location
    tk.Label(left_weather, text="Lipa City", bg="#f0f0f0", 
             font=("Arial", 16)).pack(pady=5)
    
    tk.Label(left_weather, text="Partly Cloudy", bg="#f0f0f0", 
             font=("Arial", 14)).pack()
    
    # Right panel - Forecast
    right_weather = tk.Frame(frame, bg="white")
    right_weather.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
    
    # Sample forecast data
    forecast_data = [
        {"day": "Tuesday", "temp": "37°C", "condition": "Sunny"},
        {"day": "Wednesday", "temp": "36°C", "condition": "Partly Cloudy"},
        {"day": "Thursday", "temp": "35°C", "condition": "Rainy"},
        {"day": "Friday", "temp": "34°C", "condition": "Cloudy"}
    ]
    
    for forecast in forecast_data:
        forecast_card = tk.Frame(right_weather, bg="#f0f0f0", highlightbackground="gray", 
                                highlightthickness=1)
        forecast_card.pack(fill="x", pady=5, padx=5)
        
        inner = tk.Frame(forecast_card, bg="#f0f0f0")
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_frame = tk.Frame(inner, bg="#f0f0f0")
        text_frame.pack(side="left", fill="both", expand=True)
        
        tk.Label(text_frame, text=forecast['day'], bg="#f0f0f0", 
                font=("Arial", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(text_frame, text=f"{forecast['temp']} - {forecast['condition']}", 
                bg="#f0f0f0", font=("Arial", 10), anchor="w").pack(fill="x")
    
    return frame

# ============================================================================
# FACE IMAGE FUNCTIONS
# ============================================================================

def load_face_image(mood):
    """Load face image from sekai_faces folder"""
    global image_cache
    
    # Check cache first
    if mood in image_cache:
        return image_cache[mood]
    
    # Try to find the image file
    sekai_faces_dir = "sekai_faces"
    
    # Possible filenames for each mood
    mood_files = {
        'happy': ['happy.jpg', 'happy.JPG', 'hapy.jpg', 'smile.jpg'],
        'angry': ['angry.jpg', 'angry.JPG', 'mad.jpg'],
    }
    
    image_path = None
    
    if mood in mood_files:
        for filename in mood_files[mood]:
            test_path = os.path.join(sekai_faces_dir, filename)
            if os.path.exists(test_path):
                image_path = test_path
                break
    
    if not image_path:
        # If no image found, create a colored fallback
        return create_fallback_image(mood)
    
    try:
        # Load and resize image
        img = Image.open(image_path)
        
        # Calculate scaling to fit screen while maintaining aspect ratio
        img_width, img_height = img.size
        screen_ratio = SCREEN_WIDTH / SCREEN_HEIGHT
        img_ratio = img_width / img_height
        
        if img_ratio > screen_ratio:
            # Image is wider than screen
            new_width = SCREEN_WIDTH
            new_height = int(SCREEN_WIDTH / img_ratio)
        else:
            # Image is taller than screen
            new_height = SCREEN_HEIGHT
            new_width = int(SCREEN_HEIGHT * img_ratio)
        
        # Resize with high-quality filtering
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(img)
        
        # Cache the image
        image_cache[mood] = photo
        
        return photo
        
    except Exception as e:
        print(f"[Image] Error loading {mood} image: {e}")
        return create_fallback_image(mood)

def create_fallback_image(mood):
    """Create a fallback image if real image not found"""
    colors = {
        'happy': '#4CAF50',  # Green
        'angry': '#F44336',  # Red
    }
    
    color = colors.get(mood, '#9E9E9E')  # Gray as default
    
    # Create a simple colored image with text
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color)
    
    try:
        from PIL import ImageDraw, ImageFont
        
        draw = ImageDraw.Draw(img)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        text = f"Sekai is {mood}"
        
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = (SCREEN_WIDTH - text_width) // 2
        y = (SCREEN_HEIGHT - text_height) // 2
        
        draw.text((x, y), text, fill="white", font=font)
        
    except Exception as e:
        print(f"[Image] Error creating fallback: {e}")
    
    photo = ImageTk.PhotoImage(img)
    return photo

def set_face_mood(mood):
    """Set Sekai's mood - NO TEXT OVERLAY"""
    global current_mood, current_photo, face_label
    
    current_mood = mood
    
    if face_label and face_label.winfo_exists():
        # Load the appropriate image
        photo = load_face_image(mood)
        
        if photo:
            # Update the label with the image - NO TEXT
            face_label.config(image=photo, bg="black")
            face_label.image = photo  # Keep a reference!
            current_photo = photo
            # Clear any text overlay - just show the image
            face_label.config(text="", compound="center")
    
    return current_mood

# ============================================================================
# AUDIO RECORDING FUNCTIONS
# ============================================================================

def record_audio():
    """Record audio for 5 seconds with flashing LED - NON-BLOCKING"""
    print("\n" + "="*50)
    print("STARTING 5-SECOND AUDIO RECORDING")
    print("="*50)
    
    # Change title to show recording
    update_title("Recording...")
    
    # Start LED flashing in a separate thread
    flash_thread = threading.Thread(target=flash_led_while_recording, daemon=True)
    flash_thread.start()
    
    # Record for 5 seconds
    recording_file = "test_recording.wav"
    print(f"[Recording] Saving to: {recording_file}")
    
    # Record command with your audio device - USE subprocess.Popen for non-blocking
    record_command = f"arecord -d 5 -f S16_LE -r 16000 -c 1 -D {AUDIO_DEVICE} {recording_file}"
    print(f"[Recording] Command: {record_command}")
    
    print(f"[Recording] Starting recording at: {time.strftime('%H:%M:%S')}")
    
    try:
        # Use Popen instead of run - non-blocking
        process = subprocess.Popen(record_command, shell=True, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        
        # Wait for process to complete in background
        def wait_for_recording():
            stdout, stderr = process.communicate()
            return_code = process.returncode
            
            print(f"[Recording] Recording finished at: {time.strftime('%H:%M:%S')}")
            
            if return_code == 0:
                print("[Recording] ✅ Recording successful!")
                
                if os.path.exists(recording_file):
                    file_size = os.path.getsize(recording_file)
                    print(f"[Recording] 📁 File size: {file_size} bytes")
                    
                    # Play back the recording in separate thread
                    playback_thread = threading.Thread(target=playback_audio, 
                                                     args=(recording_file,), 
                                                     daemon=True)
                    playback_thread.start()
                else:
                    print(f"[Recording] ❌ File not created")
            else:
                print(f"[Recording] ❌ Recording failed!")
                print(f"[Recording] Error: {stderr.decode()[:200]}")
            
            # Stop LED and return to happy face
            GPIO.output(LED_PIN, GPIO.LOW)
            if root and root.winfo_exists():
                # Set back to default happy face
                set_face_mood("happy")
                update_title("Sekai is happy")  # Update title to match
        
        # Start waiting in separate thread
        wait_thread = threading.Thread(target=wait_for_recording, daemon=True)
        wait_thread.start()
            
    except Exception as e:
        print(f"[Recording] ❌ Exception: {e}")
        GPIO.output(LED_PIN, GPIO.LOW)
        if root and root.winfo_exists():
            set_face_mood("happy")
            update_title("Sekai is happy")

def playback_audio(recording_file):
    """Play back recorded audio"""
    print("[Recording] Playing back recording...")
    play_command = f"aplay {recording_file}"
    try:
        play_result = subprocess.run(play_command, shell=True, 
                                   capture_output=True, text=True)
        if play_result.returncode == 0:
            print("[Recording] ✅ Playback successful!")
        else:
            print(f"[Recording] ❌ Playback failed: {play_result.stderr[:100]}")
    except Exception as e:
        print(f"[Recording] Playback error: {e}")

def flash_led_while_recording():
    """Flash LED while recording is in progress"""
    print("[LED] Starting LED flash pattern")
    
    try:
        flash_duration = 5.0  # Match recording duration
        start_time = time.time()
        
        while time.time() - start_time < flash_duration:
            # Flash pattern: on for 0.2s, off for 0.2s
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.2)
            
    except Exception as e:
        print(f"[LED] Error in flash thread: {e}")
    finally:
        # Ensure LED is off
        GPIO.output(LED_PIN, GPIO.LOW)

# ============================================================================
# FSR MONITORING THREAD
# ============================================================================

def fsr_monitoring_thread():
    """Monitor FSR sensor in separate thread"""
    global fsr_last_tap_time, fsr_tap_count, fsr_last_state, fsr_cooldown_until
    global fsr_thread_running
    
    print("[FSR Thread] Starting FSR monitoring...")
    
    while fsr_thread_running:
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
                    print(f"[FSR Thread] Double tap count: {fsr_tap_count}")
                    
                    # Double tap detected - start recording sequence
                    if fsr_tap_count >= 2:
                        print("[FSR Thread] ✅ Double tap detected! Starting recording...")
                        
                        # Send event to UI thread
                        fsr_event_queue.put(('fsr_detected',))
                        
                        # Reset for next time
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
    
    print("[FSR Thread] Thread stopped")

# ============================================================================
# UI COMMAND PROCESSING (Main Thread)
# ============================================================================

def process_ui_commands():
    """Process commands from other threads (runs in main thread)"""
    global root
    
    # Process FSR events
    try:
        while not fsr_event_queue.empty():
            event = fsr_event_queue.get_nowait()
            
            if event[0] == 'fsr_detected':
                print("[UI Thread] FSR double-tap detected! Starting recording sequence...")
                
                # CHOOSE RANDOM MOOD FIRST (70% happy, 30% angry)
                mood = random.choices(
                    list(MOOD_PROBABILITIES.keys()), 
                    weights=list(MOOD_PROBABILITIES.values())
                )[0]
                
                print(f"[UI Thread] Selected random mood: {mood}")
                
                # Show the randomly chosen mood face
                set_face_mood(mood)
                
                # Start recording after 3 seconds
                if root and root.winfo_exists():
                    root.after(3000, start_recording)
                
    except queue.Empty:
        pass
    
    # Schedule next check
    if root and root.winfo_exists():
        root.after(100, process_ui_commands)

def start_recording():
    """Start the recording sequence"""
    print("[UI Thread] Starting recording sequence...")
    
    # Start recording in a separate thread
    recording_thread = threading.Thread(target=record_audio, daemon=True)
    recording_thread.start()

# ============================================================================
# KEYBOARD CONTROLS
# ============================================================================

def setup_keyboard_controls():
    """Setup keyboard shortcuts"""
    def on_key_press(event):
        key = event.char.lower()
        if key == 'a':
            show_calendar()
        elif key == 'b':
            show_face()  # Random mood (70% happy, 30% angry)
        elif key == 'c':
            show_weather()
        elif key == 'r':
            # Manual recording test - follow same flow as FSR
            print("[Manual] Starting recording test...")
            
            # Choose random mood first (70% happy, 30% angry)
            mood = random.choices(
                list(MOOD_PROBABILITIES.keys()), 
                weights=list(MOOD_PROBABILITIES.values())
            )[0]
            
            print(f"[Manual] Selected random mood: {mood}")
            
            # Show the randomly chosen mood face
            set_face_mood(mood)
            
            # Start recording after 1 second (faster for manual test)
            if root and root.winfo_exists():
                root.after(1000, start_recording)
        elif key == 'q':
            cleanup_and_exit()
    
    if root:
        root.bind('<Key>', on_key_press)

# ============================================================================
# TKINTER UI SETUP
# ============================================================================

def setup_tkinter_ui():
    """Setup Tkinter UI on main thread"""
    global root, container
    
    calendar.setfirstweekday(calendar.SUNDAY)
    
    root = tk.Tk()
    root.title("Sekai is happy")
    
    # Set fixed screen size
    root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    root.resizable(False, False)
    root.configure(bg="black")
    
    # GRID SETUP
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    
    # Container for all views
    container = tk.Frame(root, bg="black")
    container.grid(row=0, column=0, sticky="nsew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    
    # Create all frames but don't show them yet
    global calendar_frame, face_frame, weather_frame, face_label
    
    # Create frames (hidden initially)
    calendar_frame = create_calendar_view()
    calendar_frame.grid(row=0, column=0, sticky="nsew")
    calendar_frame.grid_remove()
    
    face_frame = create_face_view()
    face_frame.grid(row=0, column=0, sticky="nsew")
    face_frame.grid_remove()
    
    weather_frame = create_weather_view()
    weather_frame.grid(row=0, column=0, sticky="nsew")
    weather_frame.grid_remove()
    
    # Start UI command processor
    root.after(100, process_ui_commands)
    
    # Setup keyboard controls
    setup_keyboard_controls()
    
    # SHOW DEFAULT HAPPY FACE AT STARTUP
    show_default_face()
    
    return root

# ============================================================================
# CLEANUP AND EXIT
# ============================================================================

def cleanup_and_exit():
    """Cleanup and exit the application"""
    global fsr_thread_running
    
    print("\n[Cleanup] Cleaning up resources...")
    
    # Stop FSR thread
    fsr_thread_running = False
    
    # Cleanup GPIO
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    
    # Destroy Tkinter window
    if root and root.winfo_exists():
        root.destroy()
    
    print("[Cleanup] Exiting application")
    
    # Exit the program
    import sys
    sys.exit(0)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main function"""
    print("="*60)
    print("SEKAI INTERFACE - FIXED VERSION")
    print("="*60)
    print("\nKEYBOARD SHORTCUTS:")
    print("  a = Show Calendar")
    print("  b = Show Random Face (70% happy, 30% angry)")
    print("  c = Show Weather")
    print("  r = Manual Recording Test")
    print("  q = Quit")
    print("\nFSR CONTROL:")
    print("  Double-tap FSR = random mood → 3 sec → record → happy face")
    print("\nCHANGES MADE:")
    print("  1. Starts with HAPPY FACE (not black screen)")
    print("  2. FSR shows random mood (70% happy, 30% angry)")
    print("  3. Non-blocking recording")
    print("  4. Returns to happy face after recording")
    print("="*60)
    
    # Check if image directory exists
    if not os.path.exists("sekai_faces"):
        print("NOTE: 'sekai_faces' directory not found!")
        print("Using colored fallbacks for faces.")
    
    # Setup Tkinter UI
    root = setup_tkinter_ui()
    
    # Setup cleanup on window close
    root.protocol("WM_DELETE_WINDOW", cleanup_and_exit)
    
    # Start FSR monitoring thread
    print("\n[Main] Starting FSR monitoring thread...")
    fsr_thread = threading.Thread(target=fsr_monitoring_thread, daemon=False)
    fsr_thread.start()
    
    # Start main loop
    print("\n[Main] Starting Tkinter main loop...")
    print("[Main] Starts with HAPPY FACE - Press a/b/c/r\n")
    
    try:
        root.mainloop()
        
        # Wait for FSR thread to finish
        if fsr_thread.is_alive():
            print("[Main] Waiting for FSR thread to finish...")
            fsr_thread.join(timeout=2.0)
            
    except KeyboardInterrupt:
        print("\n[Main] Keyboard interrupt received")
        cleanup_and_exit()
    except Exception as e:
        print(f"\n[Main] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup_and_exit()

if __name__ == "__main__":
    main()