import tkinter as tk

VERSION = "1.1"
text = "Bye World"

window = tk.Tk()
window.title(f"Atomic Launcher v{VERSION}")
window.geometry("300x100")

label = tk.Label(window, text=text, font=("Arial", 14))
label.pack(pady=20)

window.mainloop()
