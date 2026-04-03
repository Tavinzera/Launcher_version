import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import json
import tkinter as tk
from tkinter import messagebox

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

APPDATA = os.getenv("APPDATA") or ""
ATOMIC_DIR = os.path.join(APPDATA, "AtomicLauncher")
CONFIG_DIR = os.path.join(ATOMIC_DIR, "config")
ACCOUNT_FILE = os.path.join(ATOMIC_DIR, "account.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

BACKEND_URL = os.getenv("PIKAVERSE_BACKEND_URL", "https://launcher-version.onrender.com").strip().rstrip("/")

os.makedirs(ATOMIC_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

BG = "#0B0B0B"
CARD = "#101010"
ACCENT = "#F4D03F"
TEXT = "#F5F5F5"
BORDER = "#2A2A2A"
ENTRY_BG = "#161616"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

_root = tk.Tk()
_root.withdraw()


def erro(msg: str):
    messagebox.showerror("Erro", msg, parent=_root)


def info(msg: str):
    messagebox.showinfo("Google", msg, parent=_root)


def salvar_conta_local(username: str, uuidv: str, email: str = "", name: str = "", picture: str = "", provider: str = "google"):
    data = {
        "username": username,
        "uuid": uuidv,
        "email": email,
        "name": name,
        "picture": picture,
        "provider": provider
    }
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def salvar_login_type_google():
    data = {
        "login_type": "google",
        "offline_user": "",
        "ram": 4,
        "java_args": ""
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                antigo = json.load(f)
            if isinstance(antigo, dict):
                data.update(antigo)
        except Exception:
            pass

    data["login_type"] = "google"

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def backend_online() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=60)
        return bool(r.ok)
    except Exception:
        return False


def acordar_backend():
    try:
        requests.get(f"{BACKEND_URL}/health", timeout=60)
    except Exception:
        pass


def obter_oauth_config():
    r = requests.get(f"{BACKEND_URL}/auth/google/config", timeout=60)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Falha ao obter configuração OAuth"))
    oauth = data.get("oauth")
    if not oauth or "installed" not in oauth:
        raise RuntimeError("Configuração OAuth inválida recebida do backend")
    return oauth


def finalizar():
    try:
        _root.destroy()
    except Exception:
        pass


def tela_nickname(user_data: dict):
    win = tk.Toplevel(_root)
    win.title("Escolher nickname")
    win.geometry("430x230")
    win.configure(bg=BG)
    win.resizable(False, False)

    frame = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    frame.place(relx=0.5, rely=0.5, anchor="center", width=360, height=170)

    tk.Label(frame, text="Escolha seu nickname", bg=CARD, fg=ACCENT, font=("Arial", 16, "bold")).pack(pady=(18, 6))
    tk.Label(frame, text=user_data.get("email", ""), bg=CARD, fg=TEXT, font=("Arial", 10)).pack(pady=(0, 10))

    entry = tk.Entry(
        frame,
        bg=ENTRY_BG,
        fg=TEXT,
        insertbackground=ACCENT,
        relief="flat",
        bd=1,
        font=("Arial", 11),
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT
    )
    entry.pack(fill="x", padx=30, ipady=5)
    entry.focus_set()

    status = tk.Label(frame, text="", bg=CARD, fg="#FF6B6B", font=("Arial", 9, "bold"))
    status.pack(pady=(10, 0))

    def confirmar():
        username = entry.get().strip()
        if not username:
            status.config(text="Digite um nickname.")
            return

        try:
            r = requests.post(
                f"{BACKEND_URL}/auth/set-username",
                json={"google_id": user_data["google_id"], "username": username},
                timeout=60
            )
            data = r.json()
        except Exception as e:
            status.config(text=f"Falha ao salvar nickname: {e}")
            return

        if not data.get("ok"):
            status.config(text=data.get("error", "Erro ao salvar nickname"))
            return

        salvar_conta_local(
            username=data["username"],
            uuidv=data["uuid"],
            email=user_data.get("email", ""),
            name=user_data.get("name", ""),
            picture=user_data.get("picture", ""),
            provider="google"
        )
        salvar_login_type_google()
        info("Login Google concluído.")
        win.destroy()
        finalizar()

    tk.Button(
        frame,
        text="Confirmar",
        command=confirmar,
        bg=ACCENT,
        fg="black",
        relief="flat",
        bd=0,
        font=("Arial", 10, "bold"),
        cursor="hand2"
    ).pack(pady=(14, 0), ipadx=16, ipady=4)

    win.bind("<Return>", lambda e: confirmar())
    win.protocol("WM_DELETE_WINDOW", finalizar)
    win.deiconify()
    win.lift()
    win.focus_force()


def login():
    if "SEU-BACKEND.onrender.com" in BACKEND_URL:
        erro("Defina a URL real do backend em PIKAVERSE_BACKEND_URL ou no código.")
        finalizar()
        return

    try:
        acordar_backend()

        if not backend_online():
            erro(f"O backend não está online em {BACKEND_URL}")
            finalizar()
            return

        oauth_config = obter_oauth_config()

        flow = InstalledAppFlow.from_client_config(
            oauth_config,
            scopes=SCOPES
        )

        creds = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True
        )

        token_value = getattr(creds, "id_token", None)
        if not token_value:
            erro("O Google não retornou id_token.")
            finalizar()
            return

        r = requests.post(
            f"{BACKEND_URL}/auth/google",
            json={"id_token": token_value},
            timeout=60
        )

        data = r.json()

        if not data.get("ok"):
            erro(data.get("error", "Falha no backend"))
            finalizar()
            return

        user = data["user"]

        if data.get("needs_username"):
            tela_nickname(user)
        else:
            salvar_conta_local(
                username=user.get("username", ""),
                uuidv=user.get("uuid", ""),
                email=user.get("email", ""),
                name=user.get("name", ""),
                picture=user.get("picture", ""),
                provider="google"
            )
            salvar_login_type_google()
            info("Login Google concluído.")
            finalizar()

    except Exception as e:
        erro(f"Erro ao abrir login Google:\n{e}")
        finalizar()


if __name__ == "__main__":
    _root.after(0, login)
    _root.mainloop()
