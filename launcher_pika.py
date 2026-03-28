import os
import json
import uuid
import random
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import minecraft_launcher_lib

# -------------------------
# PATHS
# -------------------------
APPDATA = os.getenv("APPDATA")
GAME_DIR = os.path.join(APPDATA, "AtomicLauncher")
CONFIG_DIR = os.path.join(GAME_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ACCOUNT_FILE = os.path.join(GAME_DIR, "account.json")

os.makedirs(GAME_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(os.path.join(GAME_DIR, "mods"), exist_ok=True)

VERSION_MC = "1.21.1"
RAM = 4
JAVA_ARGS = ""

# -------------------------
# CONFIG
# -------------------------
def salvar_config(login_type=None):
    data = carregar_config() or {}
    if login_type:
        data["login_type"] = login_type
    data["ram"] = RAM
    data["java_args"] = JAVA_ARGS

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return None

# -------------------------
# ACCOUNT
# -------------------------
def salvar_conta(user, uuidv):
    with open(ACCOUNT_FILE, "w") as f:
        json.dump({"username": user, "uuid": uuidv}, f)

def carregar_conta():
    if os.path.exists(ACCOUNT_FILE):
        with open(ACCOUNT_FILE) as f:
            d = json.load(f)
            return d.get("username"), d.get("uuid")
    return None, None

# -------------------------
# FABRIC UPDATE
# -------------------------
def atualizar_fabric():
    loaders = minecraft_launcher_lib.fabric.get_all_loader_versions()
    latest_loader = loaders[0]["version"]

    version_id = f"fabric-loader-{latest_loader}-{VERSION_MC}"

    installed_versions = minecraft_launcher_lib.utils.get_installed_versions(GAME_DIR)
    installed_ids = [v["id"] for v in installed_versions]

    if version_id not in installed_ids:
        minecraft_launcher_lib.install.install_minecraft_version(VERSION_MC, GAME_DIR)
        minecraft_launcher_lib.fabric.install_fabric(
            minecraft_version=VERSION_MC,
            loader_version=latest_loader,
            minecraft_directory=GAME_DIR
        )
    return version_id

# -------------------------
# ROOT
# -------------------------
root = tk.Tk()
root.title("PikaVerse Launcher")
root.geometry("900x540")
root.resizable(False, False)

canvas = tk.Canvas(root, width=900, height=540, highlightthickness=0)
canvas.pack()

# -------------------------
# BACKGROUND
# -------------------------
backgrounds = []
bg_photo = None

def carregar_backgrounds():
    pasta = os.path.join(os.path.dirname(__file__), "backgrounds")
    if not os.path.exists(pasta):
        os.makedirs(pasta)

    for f in os.listdir(pasta):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            backgrounds.append(os.path.join(pasta, f))

def mostrar_background():
    global bg_photo
    if not backgrounds:
        return
    img = Image.open(backgrounds[0]).resize((900, 540))
    bg_photo = ImageTk.PhotoImage(img)
    canvas.create_image(0, 0, anchor="nw", image=bg_photo)

carregar_backgrounds()

# -------------------------
# PARTICLES
# -------------------------
particles = []

def criar_particulas():
    for _ in range(40):
        x = random.randint(0, 900)
        y = random.randint(0, 540)
        p = canvas.create_oval(x, y, x+2, y+2, fill="white", outline="")
        particles.append(p)

def animar_particulas():
    for p in particles:
        canvas.move(p, 0, 0.5)
        if canvas.coords(p)[1] > 540:
            x = random.randint(0, 900)
            canvas.coords(p, x, 0, x+2, 2)
    root.after(30, animar_particulas)

# -------------------------
# RUN MINECRAFT
# -------------------------
def rodar_minecraft(user, uuidv):
    version_id = atualizar_fabric()

    options = {
        "username": user,
        "uuid": uuidv,
        "token": "",
        "jvmArguments": [f"-Xmx{RAM}G"] + JAVA_ARGS.split()
    }

    cmd = minecraft_launcher_lib.command.get_minecraft_command(
        version_id,
        GAME_DIR,
        options
    )

    subprocess.Popen(cmd, cwd=GAME_DIR)

# -------------------------
# START
# -------------------------
def iniciar():
    user = nick_entry.get().strip()
    if not user:
        messagebox.showerror("Erro", "Digite um nickname")
        return

    saved_user, saved_uuid = carregar_conta()

    if saved_uuid:
        uuidv = saved_uuid
    else:
        uuidv = str(uuid.uuid3(uuid.NAMESPACE_DNS, user))
        salvar_conta(user, uuidv)

    threading.Thread(
        target=rodar_minecraft,
        args=(user, uuidv),
        daemon=True
    ).start()

# -------------------------
# MENU CONFIG
# -------------------------
menu_frame = None

def abrir_menu():
    global menu_frame
    if menu_frame:
        menu_frame.destroy()
        menu_frame = None
        return

    menu_frame = tk.Frame(root, bg="#2a2a2a")

    config = carregar_config()
    login_type = config.get("login_type") if config else "offline"

    if login_type != "offline":
        tk.Button(menu_frame, text="Conta", bg="#2a2a2a", fg="white", bd=0).pack(fill="x")

    tk.Button(menu_frame, text="Java", bg="#2a2a2a", fg="white", bd=0, command=abrir_java).pack(fill="x")
    tk.Button(menu_frame, text="Minecraft", bg="#2a2a2a", fg="white", bd=0, command=abrir_minecraft_config).pack(fill="x")
    tk.Button(menu_frame, text="Sobre", bg="#2a2a2a", fg="white", bd=0, command=sobre).pack(fill="x")

    canvas.create_window(820, 120, window=menu_frame)

# -------------------------
# CONFIG JAVA
# -------------------------
def abrir_java():
    win = tk.Toplevel(root)
    win.title("Java")
    win.geometry("300x200")

    tk.Label(win, text="RAM (GB)").pack()
    ram_entry = tk.Entry(win)
    ram_entry.insert(0, str(RAM))
    ram_entry.pack()

    tk.Label(win, text="Argumentos JVM").pack()
    args_entry = tk.Entry(win)
    args_entry.insert(0, JAVA_ARGS)
    args_entry.pack()

    def salvar():
        global RAM, JAVA_ARGS
        RAM = int(ram_entry.get())
        JAVA_ARGS = args_entry.get()
        salvar_config()
        win.destroy()

    tk.Button(win, text="Salvar", command=salvar).pack(pady=10)

# -------------------------
# CONFIG MINECRAFT
# -------------------------
def abrir_minecraft_config():
    win = tk.Toplevel(root)
    win.title("Minecraft")
    win.geometry("250x150")

    def abrir_dir():
        os.startfile(GAME_DIR)

    tk.Button(win, text="Abrir Diretório", command=abrir_dir).pack(pady=30)

# -------------------------
# SOBRE
# -------------------------
def sobre():
    messagebox.showinfo("Sobre", "PikaVerse Launcher\nVersão 1.0")

# -------------------------
# LOGIN SCREEN
# -------------------------
def tela_login():
    canvas.delete("all")
    canvas.create_rectangle(0,0,900,540, fill="#1a1a1a")
    canvas.create_text(450, 150, text="Login", fill="white", font=("Arial", 28, "bold"))

    def login_offline():
        salvar_config("offline")
        tela_inicio()

    btn = tk.Button(root, text="Jogar Offline", width=20, height=2, command=login_offline)
    canvas.create_window(450, 260, window=btn)

# -------------------------
# HOME SCREEN
# -------------------------
def tela_inicio():
    canvas.delete("all")
    mostrar_background()

    # Barra superior
    canvas.create_rectangle(0, 0, 900, 50, fill="#202020", outline="")
    canvas.create_text(20, 25, text="PikaVerse Launcher", fill="white", font=("Arial", 14, "bold"), anchor="w")

    # Botão menu (3 barras)
    menu_btn = tk.Button(root, text="≡", font=("Arial", 16), bg="#202020", fg="white", bd=0, command=abrir_menu)
    canvas.create_window(870, 25, window=menu_btn)

    # Barra lateral
    canvas.create_rectangle(0, 50, 80, 540, fill="#2a2a2a", outline="")

    # Faixa inferior
    canvas.create_rectangle(0, 470, 900, 540, fill="#1a1a1a", outline="")

    # Nick
    global nick_entry
    nick_entry = tk.Entry(root, font=("Arial", 12))
    canvas.create_window(180, 505, window=nick_entry, width=160)

    saved_user, _ = carregar_conta()
    if saved_user:
        nick_entry.insert(0, saved_user)

    # Botão iniciar
    play_button = tk.Button(root, text="INICIAR", font=("Arial", 14, "bold"), width=12, command=iniciar)
    canvas.create_window(450, 505, window=play_button)

    criar_particulas()
    animar_particulas()

# -------------------------
# START FLOW
# -------------------------
config = carregar_config()

if config is None:
    tela_login()
else:
    if config.get("login_type") == "offline":
        tela_inicio()
    else:
        tela_login()

root.mainloop()