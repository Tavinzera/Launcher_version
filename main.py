import tkinter as tk

def main():
    window = tk.Tk()
    window.title("Hello World")
    window.geometry("800x600")
    
    # Set background color
    window.config(bg="#87CEEB")
    
    # Create a label with text
    label = tk.Label(
        window,
        text="Hello World",
        font=("Arial", 48, "bold"),
        bg="#87CEEB",
        fg="white"
    )
    label.pack(expand=True)
    
    window.mainloop()

if __name__ == "__main__":
    main()
