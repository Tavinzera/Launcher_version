import os
import sys
import requests
import customtkinter as ctk
import json
import threading
import time
import importlib.util

# --- CONFIGURAÇÕES ---
URL_CONFIG_JSON = "https://github.com/Tavinzera/Launcher_version/raw/refs/heads/main/config.json"
FILE_PYC = "main_logic.pyc"

class AtomicLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Atomic")
        self.geometry("400x180")
        self.configure(fg_color="#000000")
        self.resizable(False, False)

        self.lbl_title = ctk.CTkLabel(self, text="ATOMIC", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF")
        self.lbl_title.pack(pady=(30, 5))

        self.lbl_status = ctk.CTkLabel(self, text="Sincronizando...", font=("Segoe UI", 11), text_color="#888888")
        self.lbl_status.pack()

        self.progress = ctk.CTkProgressBar(self, width=300, height=4, fg_color="#1a1a1a", progress_color="#3b82f6")
        self.progress.set(0)
        self.progress.pack(pady=20)

        threading.Thread(target=self.update_sequence, daemon=True).start()

    def get_version_from_pyc(self):
        """Carrega o .pyc temporariamente para ler a variável VERSION"""
        if not os.path.exists(FILE_PYC):
            return "0.0.0"
        try:
            spec = importlib.util.spec_from_file_location("temp_mod", FILE_PYC)
            temp_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(temp_mod)
            return getattr(temp_mod, "VERSION", "0.0.0")
        except:
            return "0.0.0"

    def update_sequence(self):
        try:
            self.lbl_status.configure(text="Checando versão da DLL...")
            v_local = self.get_version_from_pyc()
            
            # Busca JSON do Servidor
            response = requests.get(URL_CONFIG_JSON, timeout=10)
            config = response.json()
            v_remota = config['version']
            url_main = config['main_url']

            if v_remota != v_local:
                self.lbl_status.configure(text=f"Atualizando DLL: {v_local} -> {v_remota}")
                self.progress.set(0.5)
                
                r_file = requests.get(url_main)
                with open(FILE_PYC, "wb") as f:
                    f.write(r_file.content)
                
                self.lbl_status.configure(text="DLL Sincronizada!")
            else:
                self.lbl_status.configure(text="DLL em dia.")
            
            self.progress.set(1.0)
            time.sleep(1)
            self.boot_pyc()

        except Exception as e:
            print(f"Erro: {e}")
            self.lbl_status.configure(text="Erro de conexão. Tentando abrir...")
            time.sleep(2)
            self.boot_pyc()

    def boot_pyc(self):
        if not os.path.exists(FILE_PYC):
            self.lbl_status.configure(text="Erro: DLL inexistente.")
            return

        try:
            # Carregamento final
            spec = importlib.util.spec_from_file_location("main_logic", FILE_PYC)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            self.withdraw()
            if hasattr(module, 'start_app'):
                module.start_app() # O seu main_logic precisa ter essa função
            self.destroy()
            sys.exit()
        except Exception as e:
            print(f"Falha no boot: {e}")
            self.destroy()

if __name__ == "__main__":
    app = AtomicLauncher()
    app.mainloop()
