
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
import ctypes
import sys

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

# -------------------------
# CONFIG GERAL
# -------------------------
VERSION_ID = "fabric-loader-0.18.4-1.21.1"
VERSION_MC = "1.21.1"

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
icon_frames = []
icon_anim_index = 0
minecraft_process = None
closing_launcher = False
is_minimized = False
is_minimizing = False

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
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump({"username": user, "uuid": uuidv}, f, indent=4, ensure_ascii=False)


def carregar_conta():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d.get("username"), d.get("uuid")
        except Exception:
            return None, None
    return None, None


def sair_da_conta():
    global config
    salvar_config_campos(login_type="offline")
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
            root.overrideredirect(False)
            root.update_idletasks()
        except Exception:
            pass

        try:
            root.iconify()
            is_minimized = True
        except Exception:
            try:
                hwnd = root.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, 6)
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
            root.overrideredirect(True)
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
configurar_janela_barra_tarefas()
root.update_idletasks()
root.deiconify()
root.lift()
try:
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
def log(msg):
    if log_box is not None:
        log_box.insert(tk.END, str(msg) + "\n")
        log_box.see(tk.END)


def atualizar_output(msg):
    if output_label is not None:
        texto = str(msg).strip()
        if len(texto) > 54:
            texto = texto[:51] + "..."
        output_label.config(text=texto)

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
        atualizar_output("Gerando comando do Minecraft...")

        options = {
            "username": user,
            "uuid": uuidv,
            "token": "",
            "jvmArguments": [f"-Xmx{RAM}G"] + JAVA_ARGS.split()
        }

        cmd = minecraft_launcher_lib.command.get_minecraft_command(
            VERSION_ID,
            GAME_DIR,
            options
        )

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
                linha = linha.rstrip()
                if linha:
                    root.after(0, atualizar_output, linha)
                    root.after(0, log, linha)

        if minecraft_process is not None:
            return_code = minecraft_process.wait()
            if not closing_launcher:
                root.after(0, atualizar_output, f"Minecraft finalizado: {return_code}")
    except Exception as e:
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
    global bg_canvas_item, bg_photo, particles, log_box, nick_entry, btn_iniciar, output_label, menu_btn, header_icon_label
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


def desenhar_topo():
    global header_icon_label
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
        dados = [
            ("Tipo de login", LOGIN_TYPE),
            ("Usuário salvo", user or (config.get("offline_user", "") if isinstance(config, dict) else "") or "-"),
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
def login_google():
    try:
        candidatos = [
            os.path.join(os.path.dirname(__file__), "login_google.py"),
            os.path.join(os.path.dirname(__file__), "google_login.py"),
            os.path.join(os.path.dirname(__file__), "main_logic.py"),
        ]

        caminho_script = None
        for candidato in candidatos:
            if os.path.exists(candidato):
                caminho_script = candidato
                break

        if caminho_script is None:
            raise FileNotFoundError(
                "Nenhum script de login foi encontrado. Crie um arquivo login_google.py na mesma pasta do launcher."
            )

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        subprocess.Popen(
            [sys.executable, caminho_script],
            cwd=os.path.dirname(caminho_script),
            creationflags=creationflags
        )

        fechar_launcher()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao abrir login: {e}")


def login_offline():
    salvar_config_campos(login_type="offline")
    tela_inicio()


def tela_login():
    destruir_janelas_secundarias()
    limpar_canvas()
    canvas.configure(bg=BG)
    canvas.create_rectangle(0, 0, 900, 540, fill="#000000", outline="")
    desenhar_topo()
    canvas.create_text(450, 120, text="PikaVerse", fill=ACCENT, font=("Arial", 30, "bold"))

    card = tk.Frame(root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    canvas.create_window(450, 290, window=card, width=340, height=200)

    tk.Label(card, text="LOGIN", bg=CARD, fg=TEXT, font=("Arial", 16, "bold")).pack(pady=(24, 14))
    make_button(card, "Entrar com Google", login_google, width=24, bg=CARD, fg=TEXT).pack(pady=6)
    make_button(card, "Jogar Offline", login_offline, width=24, bg=ACCENT, fg="black").pack(pady=6)

# -------------------------
# HOME
# -------------------------
def tela_inicio():
    global nick_entry, menu_btn, btn_iniciar, output_label

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

    # usuário à esquerda na barra inferior
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

    nick_entry.bind("<KeyRelease>", salvar_usuario_digitado)
    nick_entry.bind("<FocusOut>", salvar_usuario_digitado)

    saved_user, _ = carregar_conta()
    cfg_user = ""
    if isinstance(config, dict):
        cfg_user = config.get("offline_user", "") or ""
    valor = cfg_user or saved_user or ""
    if valor:
        nick_entry.insert(0, valor)

    # iniciar centralizado
    btn_iniciar = make_button(root, "INICIAR", iniciar, bg=ACCENT, fg="black")
    canvas.create_window(450, 482, window=btn_iniciar, anchor="n", width=170, height=34)

    # output menor e centralizado
    output_label = tk.Label(
        root,
        text="",
        bg=BOTTOM_BAR,
        fg=TEXT,
        font=("Arial", 9, "bold"),
        anchor="center",
        justify="center"
    )
    canvas.create_window(450, 522, window=output_label, anchor="center", width=220, height=16)

    criar_particulas()

# -------------------------
# START FLOW
# -------------------------
if config is None:
    tela_login()
else:
    if config.get("login_type") == "offline":
        tela_inicio()
    else:
        tela_login()

animar_particulas()
animar_icone_topo()
animacao_abrir_launcher()
root.mainloop()
