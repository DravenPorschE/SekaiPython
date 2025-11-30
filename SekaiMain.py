import tkinter as tk
import calendar
from datetime import date

# Get today
today = date.today()
year, month, day = today.year, today.month, today.day

calendar.setfirstweekday(calendar.SUNDAY)

# Create main window
root = tk.Tk()
root.title("Calendar UI")

# Get actual screen size
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.geometry(f"{screen_width}x{screen_height}")
root.configure(bg="white")

# Quit function
def quit_app(event=None):
    root.destroy()

# Bind "q" key to quit
root.bind("q", quit_app)

# GRID SETUP
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

main = tk.Frame(root, bg="white")
main.grid(row=0, column=0, sticky="nsew")
main.columnconfigure(0, weight=0)  # Fixed width for left panel
main.columnconfigure(1, weight=1)  # Expandable right panel
main.rowconfigure(0, weight=1)

# LEFT PANEL
left_width = int(screen_width * 0.35)
left = tk.Frame(main, bg="white", highlightbackground="black", highlightthickness=2, width=left_width)
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
right = tk.Frame(main, bg="white")
right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

# Spread evenly
cols = 7
rows = 7  # 1 header row + 6 possible weeks
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

root.mainloop()
