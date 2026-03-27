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
import psutil
import ctypes
import tkinter.font as tkfont

VERSION = "fabric-loader-0.18.4-1.21.1"
APPDATA = os.getenv("APPDATA")
GAME_DIR = os.path.join(APPDATA, ".minecraft", ".pikaverso")
FONT_PATH = "font/PocketMonk.otf"
ACCOUNT_FILE = os.path.join(GAME_DIR, "account.json")
CONFIG_FILE = os.path.join(GAME_DIR, "config.json")

# -------------------------
# SPLASH SCREEN
# -------------------------

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


# -------------------------
# FADE IN
# -------------------------

def fade_in():

    root.attributes("-alpha",0)

    def anim(alpha=0):

        alpha += 0.05

        root.attributes("-alpha",alpha)

        if alpha < 1:
            root.after(20,lambda:anim(alpha))

    anim()


def carregar_config():

    global RAM, JAVA_ARGS

    if os.path.exists(CONFIG_FILE):

        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)

                RAM = data.get("ram", 4096)
                JAVA_ARGS = data.get("java_args", "")

        except:
            RAM = 4096
            JAVA_ARGS = ""
os.makedirs(GAME_DIR, exist_ok=True)
carregar_config()
processo = None
loading = None
log_box = None

backgrounds=[]
particles=[]
current_bg=None
bg_index=0
if os.path.exists(FONT_PATH):
    ctypes.windll.gdi32.AddFontResourceExW(FONT_PATH, 0x10, 0)

# -------------------------
# FECHAR JAVA
# -------------------------

def fechar_java():

    global processo

    try:

        if processo:
            processo.kill()

        for p in psutil.process_iter():

            nome=p.name().lower()

            if "java" in nome:
                p.kill()

    except:
        pass

# -------------------------
# CONTA
# -------------------------

def salvar_conta(user,uuidv):

    with open(ACCOUNT_FILE,"w") as f:
        json.dump({"username":user,"uuid":uuidv},f)

def carregar_conta():

    if os.path.exists(ACCOUNT_FILE):

        with open(ACCOUNT_FILE) as f:

            data=json.load(f)

            return data.get("username"),data.get("uuid")

    return None,None

# -------------------------
# SETTINGS
# -------------------------

def abrir_settings():

    click()

    win = tk.Toplevel(root)
    win.title("Configurações")
    win.geometry("340x300")
    win.resizable(False,False)

    # RAM
    tk.Label(win,text="Memória RAM").pack(pady=5)

    valores=[
        "2 GB","4 GB","6 GB","8 GB",
        "12 GB","16 GB","24 GB","32 GB"
    ]

    ram_var=tk.StringVar(value=f"{RAM//1024} GB")

    combo=ttk.Combobox(
        win,
        textvariable=ram_var,
        values=valores,
        state="readonly"
    )
    combo.pack(pady=5)

    # Java args
    tk.Label(win,text="Argumentos Java").pack(pady=5)

    args_entry = tk.Entry(win,width=40)
    args_entry.insert(0,JAVA_ARGS)
    args_entry.pack(pady=5)

    def salvar():

        global RAM, JAVA_ARGS

        gb=int(ram_var.get().replace(" GB",""))

        RAM = gb * 1024

        JAVA_ARGS = args_entry.get()

        with open(CONFIG_FILE,"w") as f:

            json.dump({
                "ram": RAM,
                "java_args": JAVA_ARGS
            }, f, indent=4)

        win.destroy()

    tk.Button(win,text="Salvar",width=22,command=salvar).pack(pady=10)

    tk.Button(
        win,
        text="Abrir pasta do launcher",
        width=22,
        command=lambda: os.startfile(GAME_DIR)
    ).pack(pady=5)
# -------------------------
# PARTICULAS
# -------------------------

def criar_particulas():

    for _ in range(40):

        x=random.randint(0,900)
        y=random.randint(0,540)

        p=canvas.create_oval(x,y,x+2,y+2,fill="white",outline="")

        particles.append(p)

def animar_particulas():

    for p in particles:

        canvas.move(p,0,0.4)

        pos=canvas.coords(p)

        if pos[1]>540:

            x=random.randint(0,900)

            canvas.coords(p,x,0,x+2,2)

    root.after(30,animar_particulas)

# -------------------------
# BACKGROUND
# -------------------------

def carregar_backgrounds():

    pasta="backgrounds"

    if not os.path.exists(pasta):
        os.makedirs(pasta)

    for f in os.listdir(pasta):

        if f.endswith(".jpg") or f.endswith(".png"):
            backgrounds.append(os.path.join(pasta,f))

def fade_background(path):

    global current_bg

    img1=current_bg
    img2=Image.open(path).resize((900,540))

    for a in range(10):

        blend=Image.blend(img1,img2,a/10)

        photo=ImageTk.PhotoImage(blend)

        canvas.itemconfig(bg_img,image=photo)
        canvas.image=photo

        root.update()
        time.sleep(0.05)

    current_bg=img2

def trocar_background():

    global bg_index

    if len(backgrounds)==0:
        return

    bg_index=(bg_index+1)%len(backgrounds)

    fade_background(backgrounds[bg_index])

    root.after(30000,trocar_background)

# -------------------------
# LOG
# -------------------------

def log(msg):

    if log_box:

        root.after(0,lambda:(
            log_box.insert(tk.END,msg+"\n"),
            log_box.see(tk.END)
        ))

# -------------------------
# LOADING
# -------------------------

def fechar_loading():

    fechar_java()
    os._exit(0)

def janela_loading():

    global loading,log_box

    root.iconify()

    loading=tk.Toplevel()

    loading.title("Carregando Minecraft")
    loading.geometry("520x320")
    loading.protocol("WM_DELETE_WINDOW",fechar_loading)

    frame=tk.Frame(loading)
    frame.pack(pady=10)

    gif_label=tk.Label(frame)
    gif_label.grid(row=0,column=0,padx=20)

    gif=Image.open("assets/loading.gif")

    frames=[ImageTk.PhotoImage(frame.resize((120,120)))
            for frame in ImageSequence.Iterator(gif)]

    def anim(i):

        gif_label.config(image=frames[i])

        loading.after(70,anim,(i+1)%len(frames))

    anim(0)

    log_box=tk.Text(
        loading,
        height=12,
        width=65,
        bg="#0e0e0e",
        fg="#00ff9c",
        font=("Consolas",9)
    )

    log_box.pack()

# -------------------------
# MINECRAFT
# -------------------------

def rodar_minecraft(user,uuidv):

    global processo

    options={
        "username":user,
        "uuid":uuidv,
        "token":"",
        "jvmArguments": [f"-Xmx{RAM}M"] + JAVA_ARGS.split()
    }

    command=minecraft_launcher_lib.command.get_minecraft_command(
        VERSION,
        GAME_DIR,
        options
    )

    processo=subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="ignore",
        bufsize=1
    )

    for linha in processo.stdout:

        log(linha.strip())

        if "LWJGL" in linha:

            root.after(0,loading.destroy)
            os._exit(0)

# -------------------------
# INICIAR
# -------------------------

def iniciar_minecraft():

    click()

    user=nick_entry.get().strip()

    if user=="":
        messagebox.showerror("Erro","Digite um nickname.")
        return

    saved_user,saved_uuid=carregar_conta()

    if saved_uuid:
        uuidv=saved_uuid
    else:
        uuidv=str(uuid.uuid3(uuid.NAMESPACE_DNS,user))
        salvar_conta(user,uuidv)

    janela_loading()

    threading.Thread(
        target=rodar_minecraft,
        args=(user,uuidv)
    ).start()


# -------------------------
# UI
# -------------------------

root=tk.Tk()
root.withdraw()
root.title("PikaVerse")
root.geometry("900x540")
root.resizable(False,False)
root.iconbitmap("icon.ico")

# inicia invisível para fade
root.attributes("-alpha",0)

root.protocol("WM_DELETE_WINDOW",fechar_loading)

canvas=tk.Canvas(root,width=900,height=540,highlightthickness=0)
canvas.pack()

bg_img=canvas.create_image(0,0,anchor="nw")

carregar_backgrounds()

if backgrounds:

    current_bg=Image.open(backgrounds[0]).resize((900,540)

)

    photo=ImageTk.PhotoImage(current_bg)

    canvas.itemconfig(bg_img,image=photo)
    canvas.image=photo

    root.after(30000,trocar_background)

titulo="PikaVerse"

for dx in [-3,-2,-1,1,2,3]:
    for dy in [-3,-2,-1,1,2,3]:

        canvas.create_text(
            450+dx,40+dy,
            text=titulo,
            fill="black",
            font=("Pocket Monk",38, "bold")
        )

canvas.create_text(
    450,40,
    text=titulo,
    fill="white",
    font=("Pocket Monk",38,"bold")
)

canvas.create_rectangle(0,470,900,540,fill="#1a1a1a",outline="")

nick_label=tk.Label(root,text="Usuário:",fg="white",bg="#1a1a1a")
canvas.create_window(100,505,window=nick_label)

nick_entry=tk.Entry(root,font=("Arial",12))
canvas.create_window(220,505,window=nick_entry,width=160)

saved_user,_=carregar_conta()

if saved_user:
    nick_entry.insert(0,saved_user)

play_button=tk.Button(
    root,
    text="INICIAR",
    font=("Arial",16,"bold"),
    width=14,
    command=iniciar_minecraft
)

canvas.create_window(450,505,window=play_button)

config_btn=tk.Button(
    root,
    text="⚙",
    font=("Arial",14),
    command=abrir_settings
)

canvas.create_window(870,505,window=config_btn)

# splash inicial
splash_screen()

# fade da janela
root.after(200, fade_in)

# iniciar elementos com atraso
root.after(400, criar_particulas)
root.after(500, animar_particulas)
root.after(700, tocar_musica)

splash_screen()

root.mainloop()
