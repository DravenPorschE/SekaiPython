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
current_view = "face"
current_mood = "happy"
current_photo = None

# Image cache
image_cache = {}

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

def show_face(mood="happy"):
    """Show Sekai's face - press 'b'"""
    global current_view, face_frame, current_mood
    
    print(f"[UI] Showing Sekai face with mood: {mood}")
    
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
    """Set Sekai's mood"""
    global current_mood, current_photo, face_label
    
    current_mood = mood
    
    if face_label and face_label.winfo_exists():
        # Load the appropriate image
        photo = load_face_image(mood)
        
        if photo:
            # Update the label with the image
            face_label.config(image=photo, bg="black")
            face_label.image = photo  # Keep a reference!
            current_photo = photo
    
    return current_mood

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
            show_face("happy")
        elif key == 'c':
            show_weather()
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
    root.title("Sekai Interface - Press a/b/c")
    
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
    
    # Start with happy face
    show_face("happy")
    
    # Setup keyboard controls
    setup_keyboard_controls()
    
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
    print("SEKAI INTERFACE - SIMPLE KEYBOARD CONTROLS")
    print("="*60)
    print("\nKEYBOARD SHORTCUTS:")
    print("  a = Show Calendar")
    print("  b = Show Happy Face")
    print("  c = Show Weather")
    print("  q = Quit")
    print("="*60)
    
    # Check if image directory exists
    if not os.path.exists("sekai_faces"):
        print("NOTE: 'sekai_faces' directory not found!")
        print("Using colored fallbacks for faces.")
    
    # Setup Tkinter UI
    root = setup_tkinter_ui()
    
    # Setup cleanup on window close
    root.protocol("WM_DELETE_WINDOW", cleanup_and_exit)
    
    # Start main loop
    print("\n[Main] Starting Tkinter main loop...")
    print("[Main] Press a/b/c to switch views\n")
    
    try:
        root.mainloop()
            
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