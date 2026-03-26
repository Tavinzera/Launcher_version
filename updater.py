import os
import json
import uuid
import time
import random
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk, ImageSequence
import minecraft_launcher_lib
from playsound import playsound
import psutil
import ctypes
import tkinter.font as tkfont

# SPLASH SCREEN

def splash_screen():

    splash = tk.Toplevel()

    splash.overrideredirect(True)

    largura = 420
    altura = 220

    x = (root.winfo_screenwidth()//2) - (largura//2)
    y = (root.winfo_screenheight()//2) - (altura//2)

    splash.geometry(f"{largura}x{altura}+{x}+{y}")

    frame = tk.Frame(splash,bg="#111")
    frame.pack(fill="both",expand=True)

    tk.Label(
        frame,
        text="PikaVerse",
        fg="white",
        bg="#111",
        font=("Pocket Monk",30,"bold")
    ).pack(expand=True)

    tk.Label(
        frame,
        text="Carregando launcher...",
        fg="gray",
        bg="#111",
        font=("Arial",12)
    ).pack(pady=10)

    def fechar():

        splash.destroy()

        # mostrar launcher
        root.deiconify()

        fade_in()

    root.after(1800, fechar)