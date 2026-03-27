import os
import re
import sys
import subprocess
import requests

URL_VERSAO_GITHUB = "https://raw.githubusercontent.com/Tavinzera/Launcher_version/refs/heads/main/launcher_version.txt"
URL_LOGICA_GITHUB = "https://raw.githubusercontent.com/Tavinzera/Launcher_version/refs/heads/main/main_logic.py"
ARQUIVO_LOCAL = "main_logic.py"

def obter_versao_do_arquivo_local():
    if not os.path.exists(ARQUIVO_LOCAL):
        return "0.0.0"
    
    try:
        with open(ARQUIVO_LOCAL, "r", encoding="utf-8") as f:
            conteudo = f.read()
            # Procura por algo como VERSION = "1.2.3" ou VERSION = '1.2.3'
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', conteudo)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "0.0.0"

def verificar_e_atualizar():
    versao_local = obter_versao_do_arquivo_local()
    print(f"Versão local detectada: {versao_local}")

    try:
        # Pegamos a versão do servidor (que ainda é um arquivo .txt pequeno para economizar internet)
        res = requests.get(URL_VERSAO_GITHUB, timeout=5)
        versao_remota = res.text.strip()

        if versao_remota != versao_local:
            print(f"Atualizando para a versão {versao_remota}...")
            res_codigo = requests.get(URL_LOGICA_GITHUB)
            with open(ARQUIVO_LOCAL, "w", encoding="utf-8") as f:
                f.write(res_codigo.text)
            print("Atualizado com sucesso!")
        else:
            print("Você já está na última versão.")
            
    except Exception as e:
        print(f"Erro na conexão: {e}")

def rodar():
    if os.path.exists(ARQUIVO_LOCAL):
        subprocess.run([sys.executable, ARQUIVO_LOCAL])

if __name__ == "__main__":
    verificar_e_atualizar()
    rodar()