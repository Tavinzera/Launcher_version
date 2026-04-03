import datetime
import os
import json
import uuid
import random
import time
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import minecraft_launcher_lib
import minecraft_launcher_lib.fabric
import ctypes
import sys
import requests

# -------------------------
# PATHS
# -------------------------
VERSION = "1.0"
APPDATA = os.getenv("APPDATA")
GAME_DIR = os.path.join(APPDATA, "AtomicLauncher")
CONFIG_DIR = os.path.join(GAME_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ACCOUNT_FILE = os.path.join(GAME_DIR, "account.json")
MODS_DIR = os.path.join(GAME_DIR, "mods")

os.makedirs(GAME_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MODS_DIR, exist_ok=True)
LOGS_DIR = os.path.join(GAME_DIR, "logs")
LAUNCHER_LOG_FILE = os.path.join(LOGS_DIR, "launcher_full.log")

os.makedirs(LOGS_DIR, exist_ok=True)

# -------------------------
# CONFIG GERAL
# -------------------------
VERSION_ID = "fabric-loader-0.18.5-1.21.1"
VERSION_MC = "1.21.1"
BACKEND_URL = os.getenv("PIKAVERSE_BACKEND_URL", "https://launcher-version.onrender.com").rstrip("/")

# -------------------------
# TEMA UMBREON
# -------------------------
BG = "#0B0B0B"
TOPBAR = "#F4D03F"
TOPBAR_TEXT = "#111111"
TOPBAR_SHADOW = "#161616"
TOPBAR_HEIGHT = 32
SHADOW_HEIGHT = 42
SIDEBAR = "#1B1B1B"
CARD = "#101010"
ACCENT = "#F4D03F"
ACCENT_2 = "#C9A227"
TEXT = "#F5F5F5"
TEXT_DIM = "#BFBFBF"
ENTRY_BG = "#161616"
ENTRY_FG = "#F5F5F5"
BORDER = "#2A2A2A"
BOTTOM_BAR = "#161616"

# -------------------------
# ESTADO
# -------------------------
RAM = 4
JAVA_ARGS = ""
LOGIN_TYPE = "offline"
backgrounds = []
bg_original = None
bg_frames = []
bg_anim_step = 0
bg_current_index = 0
bg_current_image = None
bg_cycle_job = None
bg_fade_job = None
bg_photo = None
bg_canvas_item = None
particles = []
log_box = None
nick_entry = None
menu_btn = None
config_window = None
content_frame = None
btn_iniciar = None
output_label = None
root_container = None
window_drag_data = {"x": 0, "y": 0}
config = None
header_icon_label = None
user_status_label = None
icon_frames = []
icon_anim_index = 0
minecraft_process = None
log_lines = []
closing_launcher = False
is_minimized = False
is_minimizing = False
pending_login_email = ""
pending_register_email = ""
pending_register_username = ""
login_email_entry = None
login_password_entry = None
google_login_polling = False
google_login_started_at = 0
last_account_signature = ""


# -------------------------
# MEMÓRIA
# -------------------------
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def obter_ram_total_gb():
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total_gb = int(stat.ullTotalPhys / (1024 ** 3))
        return max(2, total_gb)
    except Exception:
        return 8


def ram_padrao_metade():
    total = obter_ram_total_gb()
    metade = max(2, total // 2)
    return min(64, metade)

# -------------------------
# CONFIG
# -------------------------
def default_config():
    return {
        "login_type": "offline",
        "offline_user": "",
        "ram": ram_padrao_metade(),
        "java_args": ""
    }


def carregar_config():
    global RAM, JAVA_ARGS, LOGIN_TYPE

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = default_config()
    else:
        return None

    LOGIN_TYPE = data.get("login_type", "offline")
    RAM = int(data.get("ram", ram_padrao_metade()) or ram_padrao_metade())
    JAVA_ARGS = str(data.get("java_args", "") or "")
    return data


def salvar_config_campos(**updates):
    data = carregar_config()
    if data is None:
        data = default_config()

    data.update(updates)

    global RAM, JAVA_ARGS, LOGIN_TYPE, config
    RAM = int(data.get("ram", ram_padrao_metade()) or ram_padrao_metade())
    JAVA_ARGS = str(data.get("java_args", "") or "")
    LOGIN_TYPE = data.get("login_type", "offline")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    config = data
    return data


config = carregar_config()

# -------------------------
# CONTA
# -------------------------
def salvar_conta(user, uuidv):
    conta_atual = carregar_conta_info()
    conta_atual["username"] = user
    conta_atual["uuid"] = uuidv
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(conta_atual, f, indent=4, ensure_ascii=False)


def salvar_conta_completa(username, uuidv, email="", provider="offline", **extras):
    data = {"username": username, "uuid": uuidv, "email": email, "provider": provider}
    data.update(extras)
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def carregar_conta_info():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}


def carregar_conta():
    d = carregar_conta_info()
    return d.get("username"), d.get("uuid")


def sair_da_conta():
    global config

    try:
        if os.path.exists(ACCOUNT_FILE):
            os.remove(ACCOUNT_FILE)
    except Exception:
        pass

    salvar_config_campos(login_type="", offline_user="")
    config = carregar_config() or default_config()
    destruir_janelas_secundarias()
    tela_login()

# -------------------------
# ROOT
# -------------------------
root = tk.Tk()
root.title("PikaVerse Launcher")

ICON_PATH = None
for _icon_candidate in [
    os.path.join(os.path.dirname(__file__), "icon.ico"),
    os.path.join(os.path.dirname(__file__), "assets", "icon.ico"),
]:
    if os.path.exists(_icon_candidate):
        ICON_PATH = _icon_candidate
        break

try:
    if ICON_PATH:
        root.iconbitmap(ICON_PATH)
except Exception:
    pass

root.geometry("900x540")
root.resizable(False, False)
root.configure(bg=BG)
root.overrideredirect(True)

root_container = tk.Frame(root, bg=BG, highlightthickness=0, bd=0)
root_container.pack(fill="both", expand=True)

canvas = tk.Canvas(root_container, width=900, height=540, highlightthickness=0, bg=BG)
canvas.pack(fill="both", expand=True)

def aplicar_icone_janela():
    try:
        if ICON_PATH and os.path.exists(ICON_PATH):
            img = Image.open(ICON_PATH)
            icon = ImageTk.PhotoImage(img)
            root.iconphoto(True, icon)
            root._icon_ref = icon
    except Exception:
        pass


def configurar_janela_barra_tarefas():
    if os.name != "nt":
        return

    try:
        app_id = "AtomicLauncher.App"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    try:
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        root.update_idletasks()
        hwnd = root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass


aplicar_icone_janela()

# -------------------------
# JANELA CUSTOMIZADA
# -------------------------
def iniciar_arraste(event):
    window_drag_data["x"] = event.x_root
    window_drag_data["y"] = event.y_root


def arrastar_janela(event):
    dx = event.x_root - window_drag_data["x"]
    dy = event.y_root - window_drag_data["y"]
    x = root.winfo_x() + dx
    y = root.winfo_y() + dy
    root.geometry(f"900x540+{x}+{y}")
    window_drag_data["x"] = event.x_root
    window_drag_data["y"] = event.y_root


def _animar_alpha(inicio, fim, passos=12, delay=15, ao_final=None):
    try:
        delta = (fim - inicio) / max(1, passos)
        def step(i=0):
            try:
                valor = inicio + delta * i
                root.attributes("-alpha", max(0.0, min(1.0, valor)))
            except Exception:
                return
            if i < passos:
                root.after(delay, lambda: step(i + 1))
            elif ao_final:
                ao_final()
        step()
    except Exception:
        if ao_final:
            ao_final()


def minimizar_janela():
    global is_minimized, is_minimizing

    if is_minimized or is_minimizing:
        return

    is_minimizing = True

    def concluir_minimizacao():
        global is_minimized, is_minimizing
        try:
            hwnd = root.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, 6)
            is_minimized = True
        except Exception:
            try:
                root.iconify()
                is_minimized = True
            except Exception:
                pass

        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass
        is_minimizing = False

    _animar_alpha(1.0, 0.0, passos=10, delay=18, ao_final=concluir_minimizacao)


def restaurar_override(_event=None):
    global is_minimized, is_minimizing

    def restaurar():
        global is_minimized, is_minimizing
        try:
            estado = root.state()
        except Exception:
            estado = "normal"

        if estado == "iconic":
            return

        try:
            configurar_janela_barra_tarefas()
        except Exception:
            pass

        if is_minimized:
            try:
                root.attributes("-alpha", 0.0)
            except Exception:
                pass
            _animar_alpha(0.0, 1.0, passos=10, delay=18)
            is_minimized = False
            is_minimizing = False
        else:
            try:
                root.attributes("-alpha", 1.0)
            except Exception:
                pass

    root.after(80, restaurar)


def ao_desminimizar(_event=None):
    try:
        if root.state() == "normal":
            restaurar_override()
    except Exception:
        pass


root.bind("<Map>", restaurar_override)
root.bind("<Unmap>", lambda _event=None: None)

def cancelar_operacoes():
    global minecraft_process, closing_launcher
    closing_launcher = True
    try:
        if minecraft_process is not None and minecraft_process.poll() is None:
            minecraft_process.terminate()
            try:
                minecraft_process.wait(timeout=3)
            except Exception:
                minecraft_process.kill()
    except Exception:
        pass
    finally:
        minecraft_process = None


def fechar_launcher():
    cancelar_operacoes()
    try:
        destruir_janelas_secundarias()
    except Exception:
        pass
    try:
        root.quit()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
    os._exit(0)


root.protocol("WM_DELETE_WINDOW", fechar_launcher)
root.update_idletasks()
root.deiconify()
configurar_janela_barra_tarefas()
try:
    root.lift()
    root.focus_force()
except Exception:
    pass


def animacao_abrir_launcher():
    try:
        root.attributes("-alpha", 1.0)
    except Exception:
        pass


# -------------------------
# BACKGROUND
# -------------------------
def _resize_cover(img, target_w=900, target_h=540):
    img = img.convert("RGBA")
    w, h = img.size
    if w <= 0 or h <= 0:
        return Image.new("RGBA", (target_w, target_h), BG)

    scale = max(target_w / w, target_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def carregar_backgrounds():
    global backgrounds, bg_original, bg_frames, bg_current_index, bg_current_image
    backgrounds = []
    bg_original = None
    bg_frames = []
    bg_current_index = 0
    bg_current_image = None

    pasta = os.path.join(os.path.dirname(__file__), "backgrounds")
    os.makedirs(pasta, exist_ok=True)

    for f in sorted(os.listdir(pasta)):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            backgrounds.append(os.path.join(pasta, f))

    if backgrounds:
        primeiro = backgrounds[0]
        try:
            bg_original = Image.open(primeiro).convert("RGBA")
            bg_current_image = _resize_cover(bg_original)
        except Exception:
            bg_original = None
            bg_current_image = None


def _cancelar_animacao_background():
    global bg_cycle_job, bg_fade_job
    if bg_cycle_job is not None:
        try:
            root.after_cancel(bg_cycle_job)
        except Exception:
            pass
        bg_cycle_job = None
    if bg_fade_job is not None:
        try:
            root.after_cancel(bg_fade_job)
        except Exception:
            pass
        bg_fade_job = None


def _aplicar_background_image(img):
    global bg_photo, bg_canvas_item, bg_current_image
    bg_current_image = img
    bg_photo = ImageTk.PhotoImage(img)
    if bg_canvas_item is None:
        bg_canvas_item = canvas.create_image(0, 0, anchor="nw", image=bg_photo)
    else:
        canvas.itemconfig(bg_canvas_item, image=bg_photo)
    try:
        canvas.lower(bg_canvas_item)
    except Exception:
        pass


def renderizar_background():
    global bg_photo, bg_canvas_item

    try:
        if bg_current_image is not None:
            _aplicar_background_image(bg_current_image)
        else:
            if bg_canvas_item is None:
                bg_canvas_item = canvas.create_rectangle(0, 0, 900, 540, fill=BG, outline="")
            else:
                canvas.itemconfig(bg_canvas_item, fill=BG)
            try:
                canvas.lower(bg_canvas_item)
            except Exception:
                pass
    except Exception:
        if bg_canvas_item is None:
            bg_canvas_item = canvas.create_rectangle(0, 0, 900, 540, fill=BG, outline="")
        else:
            canvas.itemconfig(bg_canvas_item, fill=BG)


def animar_fade_in_inicial():
    global bg_fade_job

    _cancelar_animacao_background()
    bg_fade_job = None
    renderizar_background()
    agendar_proxima_troca_background()


def trocar_background_com_fade():
    global bg_current_index, bg_current_image, bg_original, bg_fade_job

    if len(backgrounds) <= 1:
        return

    try:
        proximo_index = (bg_current_index + 1) % len(backgrounds)
        proxima_original = Image.open(backgrounds[proximo_index]).convert("RGBA")
        proxima_img = _resize_cover(proxima_original)
        atual_img = bg_current_image if bg_current_image is not None else _resize_cover(bg_original)
    except Exception:
        agendar_proxima_troca_background()
        return

    total_passos = 18

    def passo(i=0):
        global bg_current_index, bg_current_image, bg_original, bg_fade_job
        frame = Image.blend(atual_img, proxima_img, i / total_passos)
        _aplicar_background_image(frame)
        if i < total_passos:
            bg_fade_job = root.after(28, lambda: passo(i + 1))
        else:
            bg_fade_job = None
            bg_current_index = proximo_index
            bg_original = proxima_original
            bg_current_image = proxima_img
            _aplicar_background_image(bg_current_image)
            agendar_proxima_troca_background()

    passo(0)


def agendar_proxima_troca_background():
    global bg_cycle_job
    if len(backgrounds) > 1:
        bg_cycle_job = root.after(5000, trocar_background_com_fade)


carregar_backgrounds()

# -------------------------
# ÍCONE DO TOPO
# -------------------------
def carregar_icone_topo():
    global icon_frames
    icon_frames = []
    pasta = os.path.dirname(__file__)
    possiveis = [
        os.path.join(pasta, "icon.ico"),
        os.path.join(pasta, "assets", "icon.ico"),
    ]
    for caminho in possiveis:
        if os.path.exists(caminho):
            try:
                img = Image.open(caminho).convert("RGBA").resize((22, 22))
                icon_frames.append(ImageTk.PhotoImage(img))
                return
            except Exception:
                icon_frames = []


def animar_icone_topo():
    if header_icon_label is not None and header_icon_label.winfo_exists() and icon_frames:
        if LOGIN_TYPE in ("google", "email"):
            return
        header_icon_label.config(image=icon_frames[0], text="")
        header_icon_label.image = icon_frames[0]


carregar_icone_topo()

# -------------------------
# PARTÍCULAS
# -------------------------
def limpar_particulas():
    global particles
    for p in particles:
        try:
            canvas.delete(p)
        except Exception:
            pass
    particles = []


def criar_particulas():
    limpar_particulas()
    for _ in range(36):
        x = random.randint(85, 890)
        y = random.randint(TOPBAR_HEIGHT + SHADOW_HEIGHT + 8, 450)
        p = canvas.create_oval(x, y, x + 2, y + 2, fill=ACCENT, outline="")
        particles.append(p)


def animar_particulas():
    for p in particles:
        canvas.move(p, 0, 0.35)
        coords = canvas.coords(p)
        if not coords:
            continue
        if coords[1] > 450:
            x = random.randint(85, 890)
            y0 = TOPBAR_HEIGHT + SHADOW_HEIGHT + 8
            canvas.coords(p, x, y0, x + 2, y0 + 2)
    root.after(30, animar_particulas)

# -------------------------
# LOG
# -------------------------
def atualizar_log_visual():
    global log_box, log_lines
    if log_box is not None and hasattr(log_box, "config"):
        texto = "".join(log_lines[-5:])
        log_box.config(text=texto)


def log(msg):
    global log_lines
    texto = str(msg).strip()
    if not texto:
        return

    log_lines.append(texto)
    if len(log_lines) > 100:
        log_lines = log_lines[-100:]

    atualizar_log_visual()

    try:
        with open(LAUNCHER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    except Exception:
        pass


def atualizar_output(msg):
    texto = str(msg).strip()
    if output_label is not None:
        output_label.config(text=texto)
    if texto:
        log(texto)

# -------------------------
# ESTILO
# -------------------------
def make_button(parent, text, command, width=None, bg=CARD, fg=TEXT, active=None):
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        width=width,
        bg=bg,
        fg=fg,
        activebackground=active or ACCENT_2,
        activeforeground="black",
        relief="flat",
        bd=0,
        font=("Arial", 11, "bold"),
        cursor="hand2",
        padx=10,
        pady=6,
    )
    return btn


def make_entry(parent):
    return tk.Entry(
        parent,
        bg=ENTRY_BG,
        fg=ENTRY_FG,
        insertbackground=ACCENT,
        relief="flat",
        bd=1,
        font=("Arial", 11),
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )

# -------------------------
# EXECUÇÃO MINECRAFT
# -------------------------
def obter_username_para_login():
    global config

    if LOGIN_TYPE == "offline":
        user = nick_entry.get().strip() if nick_entry else ""
        cfg_user = ""
        if isinstance(config, dict):
            cfg_user = config.get("offline_user", "")
        return user or cfg_user or "Player"

    saved_user, _ = carregar_conta()
    if saved_user:
        return saved_user

    if isinstance(config, dict):
        return config.get("offline_user", "") or "Player"
    return "Player"


def finalizar_botao_iniciar():
    global btn_iniciar
    if btn_iniciar is not None:
        btn_iniciar.config(state="normal", bg=ACCENT, fg="black")


def rodar_minecraft(user, uuidv):
    global minecraft_process, closing_launcher
    try:
        iniciar_arquivo_log()
        log("Iniciando Minecraft...")
        atualizar_output("Gerando comando do Minecraft...")

        options = {
            "username": user,
            "uuid": uuidv,
            "token": "",
            "jvmArguments": [f"-Xmx{RAM}G"] + JAVA_ARGS.split(),
        }

        log(f"Usuário: {user}")
        log(f"UUID: {uuidv}")
        log(f"Opções: {options}")

        cmd = minecraft_launcher_lib.command.get_minecraft_command(
            VERSION_ID,
            GAME_DIR,
            options
        )

        log("Comando gerado:")
        log(" ".join(cmd))

        minecraft_process = subprocess.Popen(
            cmd,
            cwd=GAME_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        if minecraft_process.stdout is not None:
            for linha in minecraft_process.stdout:
                if closing_launcher:
                    break

                linha = linha.rstrip("\n\r")
                if linha.strip():
                    root.after(0, atualizar_output, linha)
                    root.after(0, log, linha)

        if minecraft_process is not None:
            return_code = minecraft_process.wait()
            log(f"Processo finalizado com código: {return_code}")

            if not closing_launcher:
                root.after(0, atualizar_output, f"Minecraft finalizado: {return_code}")

    except Exception as e:
        log(f"EXCEÇÃO AO INICIAR: {repr(e)}")
        if not closing_launcher:
            root.after(0, atualizar_output, f"Erro ao iniciar: {e}")
            root.after(0, messagebox.showerror, "Erro ao iniciar", str(e))

    finally:
        minecraft_process = None
        if not closing_launcher:
            root.after(0, finalizar_botao_iniciar)


def iniciar():
    user = obter_username_para_login()

    if LOGIN_TYPE == "offline" and not user:
        messagebox.showerror("Erro", "Digite um usuário")
        return

    saved_user, saved_uuid = carregar_conta()

    if LOGIN_TYPE == "offline" and nick_entry is not None:
        novo_user = nick_entry.get().strip()
        if novo_user:
            user = novo_user
            salvar_config_campos(offline_user=user)

    if saved_uuid and saved_user == user:
        uuidv = saved_uuid
    else:
        uuidv = str(uuid.uuid3(uuid.NAMESPACE_DNS, user))
        salvar_conta(user, uuidv)

    if btn_iniciar is not None:
        btn_iniciar.config(state="disabled", bg="#666666", fg="#DDDDDD")

    atualizar_output("Preparando inicialização...")
    threading.Thread(target=rodar_minecraft, args=(user, uuidv), daemon=True).start()

# -------------------------
# TELAS AUXILIARES
# -------------------------
def destruir_janelas_secundarias():
    global config_window
    if config_window is not None and config_window.winfo_exists():
        config_window.destroy()
    config_window = None


def limpar_canvas():
    global bg_canvas_item, bg_photo, particles, log_box, nick_entry, btn_iniciar, output_label, menu_btn, header_icon_label, user_status_label, log_lines
    _cancelar_animacao_background()
    canvas.delete("all")
    bg_canvas_item = None
    bg_photo = None
    particles = []
    log_box = None
    nick_entry = None
    btn_iniciar = None
    output_label = None
    menu_btn = None
    header_icon_label = None
    user_status_label = None
    log_lines = []


def desenhar_topo():
    global header_icon_label, user_status_label
    topo = tk.Frame(root, bg=TOPBAR, highlightthickness=0, bd=0)
    canvas.create_window(0, 0, window=topo, anchor="nw", width=900, height=TOPBAR_HEIGHT)

    sombra = tk.Frame(root, bg=TOPBAR_SHADOW, highlightthickness=0, bd=0)
    canvas.create_window(0, TOPBAR_HEIGHT, window=sombra, anchor="nw", width=900, height=SHADOW_HEIGHT)

    drag = tk.Frame(topo, bg=TOPBAR, highlightthickness=0, bd=0)
    drag.place(x=0, y=0, width=820, height=TOPBAR_HEIGHT + SHADOW_HEIGHT)
    drag.bind("<ButtonPress-1>", iniciar_arraste)
    drag.bind("<B1-Motion>", arrastar_janela)

    header_icon_label = tk.Label(
        topo,
        text="☾" if not icon_frames else "",
        bg=TOPBAR,
        fg=TOPBAR_TEXT,
        font=("Arial", 14, "bold")
    )
    header_icon_label.place(x=10, y=5, width=22, height=22)
    header_icon_label.bind("<ButtonPress-1>", iniciar_arraste)
    header_icon_label.bind("<B1-Motion>", arrastar_janela)

    titulo = tk.Label(topo, text="PikaVerse Launcher", bg=TOPBAR, fg=TOPBAR_TEXT, font=("Arial", 12, "bold"))
    titulo.place(relx=0.5, rely=0.5, anchor="center")
    titulo.bind("<ButtonPress-1>", iniciar_arraste)
    titulo.bind("<B1-Motion>", arrastar_janela)

    usuario_txt = ""
    if LOGIN_TYPE in ("google", "email"):
        saved_user, _ = carregar_conta()
        usuario_txt = saved_user or ""
    elif LOGIN_TYPE == "offline" and isinstance(config, dict):
        usuario_txt = (config.get("offline_user", "") or "").strip()

    user_status_label = tk.Label(
        sombra,
        text=usuario_txt,
        bg=TOPBAR_SHADOW,
        fg=ACCENT,
        font=("Arial", 10, "bold"),
        anchor="w"
    )
    user_status_label.place(x=12, y=9, width=250, height=20)

    btn_min = tk.Button(topo, text="—", command=minimizar_janela, bg=TOPBAR, fg=TOPBAR_TEXT, relief="flat", bd=0, font=("Arial", 12, "bold"), activebackground=ACCENT_2, activeforeground="black", cursor="hand2")
    btn_min.place(x=834, y=2, width=28, height=28)

    btn_close = tk.Button(topo, text="✕", command=fechar_launcher, bg=TOPBAR, fg=TOPBAR_TEXT, relief="flat", bd=0, font=("Arial", 11, "bold"), activebackground="#d9534f", activeforeground="white", cursor="hand2")
    btn_close.place(x=866, y=2, width=28, height=28)

# -------------------------
# JANELA DE CONFIGURAÇÕES
# -------------------------
def render_conteudo_config(tipo):
    global content_frame
    if content_frame is None or not content_frame.winfo_exists():
        return

    for widget in content_frame.winfo_children():
        widget.destroy()

    topo = tk.Frame(content_frame, bg=BG)
    topo.pack(fill="x", pady=(0, 10))
    titulo = tk.Label(topo, text=tipo, bg=BG, fg=ACCENT, font=("Arial", 18, "bold"))
    titulo.pack(anchor="w")

    if tipo == "Conta":
        user, uuidv = carregar_conta()
        conta_info = carregar_conta_info()
        dados = [
            ("Usuário salvo", user or (config.get("offline_user", "") if isinstance(config, dict) else "") or "-"),
            ("Email", conta_info.get("email", "-") or "-"),
            ("UUID", uuidv or "-"),
        ]
        for chave, valor in dados:
            bloco = tk.Frame(content_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
            bloco.pack(fill="x", pady=6)
            tk.Label(bloco, text=chave, bg=CARD, fg=TEXT_DIM, font=("Arial", 10)).pack(anchor="w", padx=14, pady=(10, 0))
            tk.Label(bloco, text=valor, bg=CARD, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor="w", padx=14, pady=(2, 10))

        botoes = tk.Frame(content_frame, bg=BG)
        botoes.pack(anchor="w", pady=12)
        make_button(botoes, "Sair", sair_da_conta, bg=ACCENT, fg="black").pack(side="left")

    elif tipo == "Java":
        bloco = tk.Frame(content_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        bloco.pack(fill="x", pady=6)
        tk.Label(bloco, text="RAM (GB)", bg=CARD, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        ram_entry = make_entry(bloco)
        ram_entry.insert(0, str(RAM))
        ram_entry.pack(anchor="w", padx=14, pady=(0, 12), ipadx=40)

        def update_ram(_event=None):
            valor = ram_entry.get().strip()
            if valor.isdigit():
                gb = max(1, min(64, int(valor)))
                salvar_config_campos(ram=gb)

        ram_entry.bind("<KeyRelease>", update_ram)
        ram_entry.bind("<FocusOut>", update_ram)

        bloco2 = tk.Frame(content_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        bloco2.pack(fill="x", pady=6)
        tk.Label(bloco2, text="Argumentos JVM", bg=CARD, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        jvm_entry = make_entry(bloco2)
        jvm_entry.insert(0, JAVA_ARGS)
        jvm_entry.pack(fill="x", padx=14, pady=(0, 12), ipady=4)

        def update_jvm(_event=None):
            salvar_config_campos(java_args=jvm_entry.get())

        jvm_entry.bind("<KeyRelease>", update_jvm)
        jvm_entry.bind("<FocusOut>", update_jvm)

        tk.Label(
            content_frame,
            text=f"RAM inicial padrão: metade da memória do PC ({ram_padrao_metade()} GB).",
            bg=BG,
            fg=TEXT_DIM,
            font=("Arial", 10)
        ).pack(anchor="w", pady=(8, 0))

    elif tipo == "Minecraft":
        dados = [
            ("Diretório do launcher", GAME_DIR),
            ("Pasta mods", MODS_DIR),
            ("Versão configurada", VERSION_ID),
        ]
        for chave, valor in dados:
            bloco = tk.Frame(content_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
            bloco.pack(fill="x", pady=6)
            tk.Label(bloco, text=chave, bg=CARD, fg=TEXT_DIM, font=("Arial", 10)).pack(anchor="w", padx=14, pady=(10, 0))
            tk.Label(bloco, text=valor, bg=CARD, fg=TEXT, font=("Arial", 11, "bold"), wraplength=420, justify="left").pack(anchor="w", padx=14, pady=(2, 10))

        botoes = tk.Frame(content_frame, bg=BG)
        botoes.pack(anchor="w", pady=10)
        make_button(botoes, "Abrir diretório", lambda: os.startfile(GAME_DIR), bg=ACCENT, fg="black").pack(side="left", padx=(0, 10))
        make_button(botoes, "Abrir mods", lambda: os.startfile(MODS_DIR), bg=CARD, fg=TEXT).pack(side="left")

    elif tipo == "Sobre":
        bloco = tk.Frame(content_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        bloco.pack(fill="x", pady=6)
        tk.Label(bloco, text="PikaVerse Launcher", bg=CARD, fg=ACCENT, font=("Arial", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(
            bloco,
            text="Tema Umbreon\nBarra superior amarela\nFundo animado\nSem atualização automática do Fabric",
            bg=CARD,
            fg=TEXT,
            justify="left",
            font=("Arial", 11)
        ).pack(anchor="w", padx=14, pady=(0, 12))


def abrir_config():
    global config_window, content_frame

    if config_window is not None and config_window.winfo_exists():
        config_window.lift()
        return

    config_window = tk.Toplevel(root)
    config_window.title("Configurações")
    config_window.geometry("720x430")
    config_window.resizable(False, False)
    config_window.configure(bg=BG)

    left = tk.Frame(config_window, bg=SIDEBAR, width=190)
    left.pack(side="left", fill="y")

    right = tk.Frame(config_window, bg=BG)
    right.pack(side="right", fill="both", expand=True)

    header = tk.Frame(right, bg="#111111", height=48)
    header.pack(fill="x")
    tk.Label(header, text="Configurações", bg="#111111", fg=ACCENT, font=("Arial", 14, "bold")).pack(anchor="w", padx=16, pady=12)

    content_frame = tk.Frame(right, bg=BG)
    content_frame.pack(fill="both", expand=True, padx=16, pady=14)

    tk.Label(left, text="MENU", bg=SIDEBAR, fg=ACCENT, font=("Arial", 13, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

    for nome in ["Conta", "Java", "Minecraft", "Sobre"]:
        make_button(left, nome, lambda n=nome: render_conteudo_config(n), bg=SIDEBAR, fg=TEXT, active=ACCENT).pack(fill="x", padx=10, pady=4)

    make_button(left, "Fechar", config_window.destroy, bg=CARD, fg=ACCENT).pack(side="bottom", fill="x", padx=10, pady=12)
    render_conteudo_config("Conta")


# -------------------------
# LOGIN
# -------------------------
def iniciar_backend():
    try:
        backend_path = os.path.join(os.path.dirname(__file__), "backend_ready.py")
        if os.path.exists(backend_path):
            try:
                r = requests.get("http://127.0.0.1:8080/health", timeout=1.0)
                if not r.ok:
                    raise RuntimeError("backend local indisponível")
                return
            except Exception:
                creationflags = 0
                if os.name == "nt":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                subprocess.Popen(
                    [sys.executable, backend_path],
                    cwd=os.path.dirname(backend_path),
                    creationflags=creationflags
                )
                return

        try:
            requests.get(f"{BACKEND_URL}/health", timeout=2.0)
        except Exception:
            pass
    except Exception as e:
        print("Erro ao iniciar backend:", e)


def _assinatura_conta_local():
    try:
        info = carregar_conta_info()
        return json.dumps(info, sort_keys=True, ensure_ascii=False)
    except Exception:
        return ""


def conta_salva_valida(provider_esperado: str | None = None):
    info = carregar_conta_info()
    username = str(info.get("username", "")).strip()
    uuidv = str(info.get("uuid", "")).strip()
    provider = str(info.get("provider", "")).strip().lower()
    if not username or not uuidv:
        return False
    if provider_esperado:
        return provider == provider_esperado
    return True


def verificar_login_google_concluido():
    global google_login_polling, google_login_started_at, last_account_signature, config, LOGIN_TYPE

    if not google_login_polling:
        return

    try:
        config = carregar_config() or default_config()
        login_type = str(config.get("login_type", "") or "").strip().lower()
        assinatura = _assinatura_conta_local()

        if login_type == "google" and conta_salva_valida("google"):
            google_login_polling = False
            last_account_signature = assinatura
            LOGIN_TYPE = "google"
            tela_inicio()
            return

        if assinatura != last_account_signature and conta_salva_valida():
            google_login_polling = False
            last_account_signature = assinatura
            LOGIN_TYPE = str((carregar_config() or {}).get("login_type", "") or "").strip().lower()
            tela_inicio()
            return
    except Exception:
        pass

    root.after(1200, verificar_login_google_concluido)


def login_google():
    global google_login_polling, google_login_started_at, last_account_signature
    try:
        iniciar_backend()

        base_dir = os.path.dirname(__file__)
        caminho_script = os.path.join(base_dir, "auth_ui.py")

        if not os.path.exists(caminho_script):
            raise FileNotFoundError("auth_ui.py não encontrado na pasta do launcher.")

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        subprocess.Popen(
            [sys.executable, caminho_script],
            cwd=os.path.dirname(caminho_script),
            creationflags=creationflags
        )

        google_login_polling = True
        google_login_started_at = int(time.time()) if "time" in globals() else 0
        last_account_signature = _assinatura_conta_local()
        messagebox.showinfo(
            "Google",
            "A tela de login continuará aberta. Termine o login Google no navegador e no popup que abrir."
        )
        root.after(1200, verificar_login_google_concluido)

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao abrir login Google: {e}")


def login_offline():
    salvar_config_campos(login_type="offline")
    tela_inicio()


def abrir_janela_confirmacao(titulo_janela, email, endpoint_confirm, on_success):
    win = tk.Toplevel(root)
    win.title(titulo_janela)
    win.geometry("420x220")
    win.resizable(False, False)
    win.configure(bg=BG)

    frame = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    frame.place(relx=0.5, rely=0.5, anchor="center", width=340, height=160)

    tk.Label(frame, text="Digite o código", bg=CARD, fg=ACCENT, font=("Arial", 16, "bold")).pack(pady=(18, 6))
    tk.Label(frame, text=email, bg=CARD, fg=TEXT, font=("Arial", 10)).pack(pady=(0, 10))
    code_entry = make_entry(frame)
    code_entry.pack(fill="x", padx=28, ipady=5)
    code_entry.focus_set()

    def confirmar():
        codigo = code_entry.get().strip()
        if not codigo:
            messagebox.showerror("Erro", "Digite o código", parent=win)
            return
        try:
            r = requests.post(
                f"{BACKEND_URL}{endpoint_confirm}",
                json={"email": email, "code": codigo},
                timeout=60
            )
            data = r.json()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao confirmar código: {e}", parent=win)
            return

        if not data.get("ok"):
            messagebox.showerror("Erro", data.get("error", "Código inválido"), parent=win)
            return

        user = data.get("user", {})
        username = user.get("username", "")
        uuidv = user.get("uuid", "")
        email_resp = user.get("email", email)
        provider = user.get("provider", "email")

        if username and uuidv:
            salvar_conta_completa(username, uuidv, email=email_resp, provider=provider)
            salvar_config_campos(login_type=provider if provider in ("google", "email") else "email", offline_user="")
        win.destroy()
        on_success()

    make_button(frame, "Confirmar", confirmar, bg=ACCENT, fg="black").pack(pady=(14, 0), ipadx=12)
    win.bind("<Return>", lambda _e: confirmar())


def iniciar_login_email():
    global login_email_entry, login_password_entry
    email = login_email_entry.get().strip() if login_email_entry is not None else ""
    senha = login_password_entry.get().strip() if login_password_entry is not None else ""

    if not email or not senha:
        messagebox.showerror("Erro", "Preencha gmail e senha")
        return

    try:
        r = requests.post(
            f"{BACKEND_URL}/auth/login/start",
            json={"email": email, "password": senha},
            timeout=60
        )
        data = r.json()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao conectar no servidor: {e}")
        return

    if not data.get("ok"):
        messagebox.showerror("Erro", data.get("error", "Gmail ou senha incorretos"))
        return

    abrir_janela_confirmacao(
        "Confirmar login",
        email,
        "/auth/login/confirm",
        tela_inicio
    )


def criar_conta():
    win = tk.Toplevel(root)
    win.title("Criar conta")
    win.geometry("430x420")
    win.resizable(False, False)
    win.configure(bg=BG)

    frame = tk.Frame(
        win,
        bg=CARD,
        highlightthickness=1,
        highlightbackground=BORDER
    )
    frame.place(relx=0.5, rely=0.5, anchor="center", width=360, height=350)

    tk.Label(
        frame,
        text="Criar conta",
        bg=CARD,
        fg=ACCENT,
        font=("Arial", 16, "bold")
    ).pack(pady=(14, 6))

    tk.Label(frame, text="Nickname", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", padx=28, pady=(4, 2))
    username_entry = make_entry(frame)
    username_entry.pack(fill="x", padx=28, ipady=5)

    tk.Label(frame, text="Gmail", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", padx=28, pady=(8, 2))
    email_entry = make_entry(frame)
    email_entry.pack(fill="x", padx=28, ipady=5)

    tk.Label(frame, text="Senha", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", padx=28, pady=(8, 2))
    password_entry = make_entry(frame)
    password_entry.config(show="*")
    password_entry.pack(fill="x", padx=28, ipady=5)

    info_label = tk.Label(
        frame,
        text="Um código será enviado para o Gmail para confirmar o cadastro.",
        bg=CARD,
        fg=TEXT_DIM,
        font=("Arial", 9),
        wraplength=300,
        justify="center"
    )
    info_label.pack(pady=(12, 10))

    def enviar():
        username = username_entry.get().strip()
        email = email_entry.get().strip()
        senha = password_entry.get().strip()

        if not username or not email or not senha:
            messagebox.showerror("Erro", "Preencha nickname, gmail e senha", parent=win)
            return

        try:
            r = requests.post(
                f"{BACKEND_URL}/auth/register/start",
                json={
                    "username": username,
                    "email": email,
                    "password": senha
                },
                timeout=60
            )
            data = r.json()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao conectar: {e}", parent=win)
            return

        if not data.get("ok"):
            messagebox.showerror("Erro", data.get("error", "Falha ao iniciar cadastro"), parent=win)
            return

        for widget in frame.winfo_children():
            widget.destroy()

        tk.Label(
            frame,
            text="Confirmar cadastro",
            bg=CARD,
            fg=ACCENT,
            font=("Arial", 16, "bold")
        ).pack(pady=(18, 6))

        tk.Label(frame, text=email, bg=CARD, fg=TEXT, font=("Arial", 10)).pack(pady=(0, 10))
        tk.Label(frame, text="Digite o código enviado no Gmail", bg=CARD, fg=TEXT_DIM, font=("Arial", 9)).pack(pady=(0, 8))

        code_entry = make_entry(frame)
        code_entry.pack(fill="x", padx=28, ipady=5)
        code_entry.focus_set()

        status_label = tk.Label(frame, text="", bg=CARD, fg="#FF6B6B", font=("Arial", 9, "bold"))
        status_label.pack(pady=(10, 0))

        def confirmar_codigo():
            codigo = code_entry.get().strip()
            if not codigo:
                status_label.config(text="Digite o código para confirmar.")
                return

            try:
                r2 = requests.post(
                    f"{BACKEND_URL}/auth/register/confirm",
                    json={"email": email, "code": codigo},
                    timeout=60
                )
                data2 = r2.json()
            except Exception as e:
                status_label.config(text=f"Falha ao confirmar: {e}")
                return

            if not data2.get("ok"):
                status_label.config(text=data2.get("error", "Código incorreto. Tente novamente."))
                return

            user = data2.get("user", {})
            username_ok = user.get("username", "")
            uuidv = user.get("uuid", "")
            email_resp = user.get("email", email)
            provider = user.get("provider", "email")

            if username_ok and uuidv:
                salvar_conta_completa(username_ok, uuidv, email=email_resp, provider=provider)
                salvar_config_campos(login_type=provider, offline_user="")

            messagebox.showinfo("Sucesso", "Conta criada com sucesso!", parent=win)
            win.destroy()
            tela_inicio()

        make_button(frame, "Confirmar código", confirmar_codigo, bg=ACCENT, fg="black").pack(pady=(14, 0), ipadx=12)
        win.bind("<Return>", lambda _e: confirmar_codigo())

    btn_criar = make_button(frame, "Criar conta", enviar, bg=ACCENT, fg="black")
    btn_criar.pack(pady=(4, 0), ipadx=18)

    username_entry.focus_set()


def desenhar_icone_google(parent):
    btn = tk.Button(
        parent,
        text="G",
        command=login_google,
        bg="white",
        fg="black",
        relief="flat",
        bd=0,
        font=("Arial", 12, "bold"),
        cursor="hand2",
        width=3,
        height=1,
    )
    return btn

def criar_botao_login(parent, texto, comando, icone=""):
    label = f"{icone}  {texto}" if icone else texto
    btn = tk.Button(
        parent,
        text=label,
        command=comando,
        bg=ACCENT,
        fg="black",
        activebackground=ACCENT_2,
        activeforeground="black",
        relief="flat",
        bd=0,
        font=("Arial", 10, "bold"),
        cursor="hand2",
        padx=14,
        pady=8,
        highlightthickness=0,
        compound="left",
    )
    return btn

def desenhar_icone_google(parent):
    return criar_botao_login(parent, "Google", login_google, "G")

def tela_login():
    global login_email_entry, login_password_entry

    destruir_janelas_secundarias()
    limpar_canvas()
    canvas.configure(bg=BG)
    canvas.create_rectangle(0, 0, 900, 540, fill="#000000", outline="")
    desenhar_topo()

    card = tk.Frame(root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    canvas.create_window(450, 275, window=card, width=390, height=305)

    tk.Label(card, text="LOGIN", bg=CARD, fg=TEXT, font=("Arial", 16, "bold")).pack(pady=(18, 12))

    tk.Label(card, text="Gmail", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", padx=30)
    login_email_entry = make_entry(card)
    login_email_entry.pack(fill="x", padx=30, ipady=5, pady=(4, 10))

    tk.Label(card, text="Senha", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", padx=30)
    login_password_entry = tk.Entry(
        card,
        bg=ENTRY_BG,
        fg=ENTRY_FG,
        insertbackground=ACCENT,
        relief="flat",
        bd=1,
        font=("Arial", 11),
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        show="*",
    )
    login_password_entry.pack(fill="x", padx=30, ipady=5, pady=(4, 12))
    make_button(card, "Entrar", iniciar_login_email, bg=ACCENT, fg="black").pack(pady=(0, 10), ipadx=18)

    botoes_frame = tk.Frame(card, bg=CARD)
    botoes_frame.pack(pady=(10, 10))

    btn_offline = criar_botao_login(botoes_frame, "Offline", login_offline, "◉")
    btn_google = criar_botao_login(botoes_frame, "Google", login_google, "G")
    btn_criar = criar_botao_login(botoes_frame, "Criar conta", criar_conta, "+")

    btn_offline.grid(row=0, column=0, padx=4)
    btn_google.grid(row=0, column=1, padx=4)
    btn_criar.grid(row=0, column=2, padx=4)

    info = tk.Label(
        card,
        text="Entre com Gmail e senha, use Google ou jogue offline.",
        bg=CARD,
        fg=TEXT_DIM,
        font=("Arial", 9),
        justify="center"
    )
    info.pack(pady=(4, 10))

    try:
        login_email_entry.focus_set()
    except Exception:
        pass

# -------------------------
# HOME
# -------------------------
def tela_inicio():
    global nick_entry, menu_btn, btn_iniciar, output_label, log_box, config

    config = carregar_config() or default_config()

    destruir_janelas_secundarias()
    limpar_canvas()
    canvas.configure(bg=BG)

    renderizar_background()
    animar_fade_in_inicial()

    # faixas
    canvas.create_rectangle(0, TOPBAR_HEIGHT + SHADOW_HEIGHT, 80, 540, fill=SIDEBAR, outline="")
    canvas.create_rectangle(0, 455, 900, 540, fill=BOTTOM_BAR, outline="")

    desenhar_topo()

    canvas.create_text(40, 94, text="☾", fill=ACCENT, font=("Arial", 18, "bold"))
    canvas.create_text(40, 124, text="⚫", fill=ACCENT_2, font=("Arial", 10))

    menu_btn = make_button(root, "≡", abrir_config, bg=TOPBAR_SHADOW, fg=ACCENT, active=ACCENT_2)
    canvas.create_window(845, TOPBAR_HEIGHT + (SHADOW_HEIGHT // 2), window=menu_btn, width=44, height=28)

    nick_entry = None

    if LOGIN_TYPE == "offline":
        user_frame = tk.Frame(root, bg=BOTTOM_BAR, highlightthickness=0, bd=0)
        canvas.create_window(100, 472, window=user_frame, anchor="nw", width=230, height=58)

        tk.Label(user_frame, text="Usuário", bg=BOTTOM_BAR, fg=ACCENT, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 4))
        nick_entry = tk.Entry(
            user_frame,
            bg=BOTTOM_BAR,
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            bd=0,
            font=("Arial", 11, "bold"),
            highlightthickness=1,
            highlightbackground=ACCENT,
            highlightcolor=ACCENT,
        )
        nick_entry.pack(anchor="w", fill="x", ipady=4)

        def salvar_usuario_digitado(_event=None):
            texto = nick_entry.get().strip() if nick_entry is not None else ""
            salvar_config_campos(offline_user=texto)
            if user_status_label is not None:
                user_status_label.config(text=texto)

        nick_entry.bind("<KeyRelease>", salvar_usuario_digitado)
        nick_entry.bind("<FocusOut>", salvar_usuario_digitado)

        saved_user, _ = carregar_conta()
        cfg_user = ""
        if isinstance(config, dict):
            cfg_user = config.get("offline_user", "") or ""
        valor = cfg_user or saved_user or ""
        if valor:
            nick_entry.insert(0, valor)
            if user_status_label is not None:
                user_status_label.config(text=valor)

    btn_iniciar = make_button(root, "INICIAR", iniciar, bg=ACCENT, fg="black")
    canvas.create_window(450, 472, window=btn_iniciar, anchor="n", width=170, height=34)

    output_label = tk.Label(
        root,
        text="",
        bg=BOTTOM_BAR,
        fg=TEXT_DIM,
        font=("Arial", 9, "bold"),
        anchor="center",
        justify="center"
    )
    canvas.create_window(450, 510, window=output_label, anchor="center", width=340, height=16)

    log_box = tk.Label(
        root,
        text="",
        bg=BG,
        fg=TEXT,
        font=("Consolas", 9),
        justify="center",
        anchor="n"
    )
    canvas.create_window(450, 532, window=log_box, anchor="n", width=520, height=46)

    criar_particulas()
    log("Launcher pronto.")

#
#   LOG
#

def iniciar_arquivo_log():
    try:
        with open(LAUNCHER_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("PikaVerse Launcher - Log completo\n")
            f.write(f"Data: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"GAME_DIR: {GAME_DIR}\n")
            f.write(f"VERSION_ID: {VERSION_ID}\n")
            f.write(f"RAM: {RAM}G\n")
            f.write(f"JAVA_ARGS: {JAVA_ARGS}\n")
            f.write(f"LOGIN_TYPE: {LOGIN_TYPE}\n")
            f.write("=" * 80 + "\n")
    except Exception:
        pass

# -------------------------
# START FLOW
# -------------------------
config = carregar_config()
if config is None:
    config = default_config()

LOGIN_TYPE = str((config or {}).get("login_type", "") or "").strip().lower()

if LOGIN_TYPE == "google" and conta_salva_valida("google"):
    tela_inicio()
elif LOGIN_TYPE == "email" and conta_salva_valida("email"):
    tela_inicio()
elif LOGIN_TYPE == "offline":
    tela_inicio()
else:
    tela_login()

animar_particulas()
animar_icone_topo()
animacao_abrir_launcher()
try:
    root.after(250, configurar_janela_barra_tarefas)
    root.after(900, configurar_janela_barra_tarefas)
    root.after(1800, configurar_janela_barra_tarefas)
    root.after(500, iniciar_backend)
except Exception:
    pass
root.mainloop()
