from tkinter import *
from PIL import Image, ImageTk, ImageSequence
import os

root = Tk()
# Set fixed screen size
screen_width = 480
screen_height = 320
root.geometry(f"{screen_width}x{screen_height}")
root.resizable(False, False)
root.configure(bg="white")

# Create main frame
main_frame = Frame(root, bg="white")
main_frame.pack(fill=BOTH, expand=True)

# Try to load and display the GIF
try:
    # Construct path to GIF
    gif_path = os.path.join("sekai_faces", "happy.gif")
    
    # Open GIF and get dimensions
    temp_img = Image.open(gif_path)
    gif_width, gif_height = temp_img.size
    temp_img.close()
    
    print(f"GIF dimensions: {gif_width}x{gif_height}")
    
    # Create label for GIF (empty for now)
    gif_label = Label(main_frame, bg="white")
    gif_label.grid(row=0, column=0, padx=20, pady=20)
    
    # Load frames
    gif = Image.open(gif_path)
    frames = []
    
    for frame in ImageSequence.Iterator(gif):
        # Resize if needed to fit your screen
        # frame = frame.resize((200, 200))  # Uncomment to resize
        
        photo = ImageTk.PhotoImage(frame.convert("RGBA"))
        frames.append(photo)
    
    # Animation function
    def animate_gif(idx=0):
        if frames:
            gif_label.config(image=frames[idx])
            root.after(50, animate_gif, (idx + 1) % len(frames))
    
    # Start animation
    animate_gif()
    
    # Keep reference
    gif_label.frames = frames
    
except FileNotFoundError:
    error_msg = f"File not found: sekai_faces/happy.gif\nCurrent dir: {os.getcwd()}"
    print(error_msg)
    Label(main_frame, text=error_msg, fg="red", bg="white", 
          font=("Arial", 12)).grid(row=0, column=0)
    
except Exception as e:
    error_msg = f"Error loading GIF: {e}"
    print(error_msg)
    Label(main_frame, text=error_msg, fg="red", bg="white", 
          font=("Arial", 12)).grid(row=0, column=0)

# You can add other widgets in the grid
# Label(main_frame, text="Character Expression", bg="white", 
#       font=("Arial", 14)).grid(row=1, column=0)

root.mainloop()