import json
import os
import random
import smtplib
import time
import uuid
from email.mime.text import MIMEText

from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# =========================
# ENV
# =========================
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "").strip()
GOOGLE_OAUTH_JSON = os.getenv("GOOGLE_OAUTH_JSON", "").strip()

# Gmail SMTP com senha de app
EMAIL_USER = os.getenv("EMAIL_USER", "").strip()
EMAIL_PASS = os.getenv("EMAIL_PASS", "").strip()
CODE_EXPIRES_SECONDS = int(os.getenv("CODE_EXPIRES_SECONDS", "300"))

if not FIREBASE_SECRET:
    raise RuntimeError("FIREBASE_SECRET não configurado no ambiente")

if not GOOGLE_OAUTH_JSON:
    raise RuntimeError("GOOGLE_OAUTH_JSON não configurado no ambiente")

try:
    firebase_dict = json.loads(FIREBASE_SECRET)
except Exception as e:
    raise RuntimeError(f"FIREBASE_SECRET inválido: {e}")

try:
    oauth_dict = json.loads(GOOGLE_OAUTH_JSON)
except Exception as e:
    raise RuntimeError(f"GOOGLE_OAUTH_JSON inválido: {e}")

installed = oauth_dict.get("installed", {})
GOOGLE_CLIENT_ID = str(installed.get("client_id", "")).strip()
if not GOOGLE_CLIENT_ID:
    raise RuntimeError("client_id não encontrado dentro de GOOGLE_OAUTH_JSON")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()


# =========================
# HELPERS
# =========================
def now_ts() -> int:
    return int(time.time())


def get_google_oauth_public_config():
    installed_cfg = oauth_dict.get("installed", {})
    return {
        "installed": {
            "client_id": installed_cfg.get("client_id", ""),
            "project_id": installed_cfg.get("project_id", ""),
            "auth_uri": installed_cfg.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": installed_cfg.get("token_uri", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": installed_cfg.get(
                "auth_provider_x509_cert_url",
                "https://www.googleapis.com/oauth2/v1/certs"
            ),
            "client_secret": installed_cfg.get("client_secret", ""),
            "redirect_uris": installed_cfg.get("redirect_uris", ["http://localhost"])
        }
    }


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def send_code_email(email: str, code: str, subject: str, body_prefix: str) -> None:
    if not EMAIL_USER or not EMAIL_PASS:
        raise RuntimeError("EMAIL_USER ou EMAIL_PASS não configurados")

    body = (
        f"{body_prefix}\n\n"
        f"Código: {code}\n\n"
        f"Esse código expira em {CODE_EXPIRES_SECONDS // 60} minutos.\n"
        "Se você não solicitou isso, ignore este email."
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [email], msg.as_string())


def find_user_by_email(email: str):
    docs = db.collection("users").where("email", "==", email).limit(1).stream()
    for doc in docs:
        return doc
    return None


def username_exists(username: str, exclude_doc_id: str | None = None) -> bool:
    docs = db.collection("users").where("username", "==", username).limit(5).stream()
    for doc in docs:
        if exclude_doc_id is None or doc.id != exclude_doc_id:
            return True
    return False


def validate_username(username: str) -> str | None:
    if not username:
        return "nickname vazio"
    if len(username) < 3:
        return "nickname deve ter pelo menos 3 caracteres"
    if len(username) > 16:
        return "nickname deve ter no máximo 16 caracteres"
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    if any(ch not in allowed for ch in username):
        return "nickname deve conter apenas letras, números e _"
    return None


def validate_password(password: str) -> str | None:
    if not password:
        return "senha vazia"
    if len(password) < 6:
        return "senha deve ter pelo menos 6 caracteres"
    if len(password) > 128:
        return "senha muito longa"
    return None


def save_pending_code(email: str, code_type: str, payload: dict) -> None:
    db.collection("codes").document(f"{code_type}:{email}").set({
        "email": email,
        "type": code_type,
        "code": payload["code"],
        "expires_at": now_ts() + CODE_EXPIRES_SECONDS,
        **{k: v for k, v in payload.items() if k != "code"}
    })


def read_pending_code(email: str, code_type: str):
    return db.collection("codes").document(f"{code_type}:{email}").get()


def delete_pending_code(email: str, code_type: str) -> None:
    db.collection("codes").document(f"{code_type}:{email}").delete()


# =========================
# ROUTES
# =========================
@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/auth/google/config")
def auth_google_config():
    return jsonify({
        "ok": True,
        "oauth": get_google_oauth_public_config()
    })


@app.post("/auth/google")
def auth_google():
    try:
        token = str((request.json or {}).get("id_token", "")).strip()
        if not token:
            return jsonify({"ok": False, "error": "id_token ausente"}), 400

        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=300
        )

        google_id = str(idinfo["sub"])
        email = normalize_email(idinfo.get("email", ""))
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        doc_ref = db.collection("users").document(google_id)
        snap = doc_ref.get()

        current_username = ""
        current_uuid = ""

        if snap.exists:
            old = snap.to_dict() or {}
            current_username = old.get("username", "") or ""
            current_uuid = old.get("uuid", "") or ""

        doc_ref.set({
            "google_id": google_id,
            "email": email,
            "name": name,
            "picture": picture,
            "provider": "google",
        }, merge=True)

        return jsonify({
            "ok": True,
            "user": {
                "google_id": google_id,
                "email": email,
                "name": name,
                "picture": picture,
                "username": current_username,
                "uuid": current_uuid,
            },
            "needs_username": not bool(current_username)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/set-username")
def set_username():
    try:
        data = request.json or {}
        google_id = str(data.get("google_id", "")).strip()
        username = str(data.get("username", "")).strip()

        if not google_id:
            return jsonify({"ok": False, "error": "google_id ausente"}), 400

        username_error = validate_username(username)
        if username_error:
            return jsonify({"ok": False, "error": username_error}), 400

        if username_exists(username, exclude_doc_id=google_id):
            return jsonify({"ok": False, "error": "nickname já está em uso"}), 409

        user_ref = db.collection("users").document(google_id)
        snap = user_ref.get()
        if not snap.exists:
            return jsonify({"ok": False, "error": "usuário Google não encontrado"}), 404

        existing = snap.to_dict() or {}
        novo_uuid = existing.get("uuid") or str(uuid.uuid4())

        user_ref.set({
            "username": username,
            "uuid": novo_uuid
        }, merge=True)

        return jsonify({
            "ok": True,
            "google_id": google_id,
            "username": username,
            "uuid": novo_uuid
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/register/start")
def register_start():
    try:
        data = request.json or {}
        username = str(data.get("username", "")).strip()
        email = normalize_email(data.get("email", ""))
        password = str(data.get("password", "")).strip()

        username_error = validate_username(username)
        if username_error:
            return jsonify({"ok": False, "error": username_error}), 400

        password_error = validate_password(password)
        if password_error:
            return jsonify({"ok": False, "error": password_error}), 400

        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "gmail inválido"}), 400

        if find_user_by_email(email):
            return jsonify({"ok": False, "error": "gmail já cadastrado"}), 409

        if username_exists(username):
            return jsonify({"ok": False, "error": "nickname já está em uso"}), 409

        code = generate_code()
        save_pending_code(email, "register", {
            "code": code,
            "username": username,
            "password_hash": generate_password_hash(password),
        })

        send_code_email(
            email=email,
            code=code,
            subject="PikaVerse - Confirmar cadastro",
            body_prefix="Use este código para confirmar o seu cadastro no PikaVerse."
        )

        return jsonify({"ok": True, "message": "Código enviado para o Gmail"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/register/confirm")
def register_confirm():
    try:
        data = request.json or {}
        email = normalize_email(data.get("email", ""))
        code = str(data.get("code", "")).strip()

        snap = read_pending_code(email, "register")
        if not snap.exists:
            return jsonify({"ok": False, "error": "código inválido"}), 400

        pending = snap.to_dict() or {}
        if pending.get("code") != code:
            return jsonify({"ok": False, "error": "código inválido"}), 400
        if now_ts() > int(pending.get("expires_at", 0)):
            delete_pending_code(email, "register")
            return jsonify({"ok": False, "error": "código expirado"}), 400

        if find_user_by_email(email):
            delete_pending_code(email, "register")
            return jsonify({"ok": False, "error": "gmail já cadastrado"}), 409

        username = pending.get("username", "")
        if username_exists(username):
            return jsonify({"ok": False, "error": "nickname já está em uso"}), 409

        user_doc_id = str(uuid.uuid4())
        player_uuid = str(uuid.uuid4())

        db.collection("users").document(user_doc_id).set({
            "provider": "email",
            "email": email,
            "username": username,
            "password_hash": pending.get("password_hash", ""),
            "uuid": player_uuid,
            "created_at": now_ts(),
        })

        delete_pending_code(email, "register")

        return jsonify({
            "ok": True,
            "user": {
                "username": username,
                "uuid": player_uuid,
                "email": email,
                "provider": "email",
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/login/start")
def login_start():
    try:
        data = request.json or {}
        email = normalize_email(data.get("email", ""))
        password = str(data.get("password", "")).strip()

        user_doc = find_user_by_email(email)
        if not user_doc:
            return jsonify({"ok": False, "error": "gmail ou senha incorretos"}), 401

        user = user_doc.to_dict() or {}
        if user.get("provider") == "google" and not user.get("password_hash"):
            return jsonify({"ok": False, "error": "essa conta usa login Google"}), 400

        if not check_password_hash(user.get("password_hash", ""), password):
            return jsonify({"ok": False, "error": "gmail ou senha incorretos"}), 401

        code = generate_code()
        save_pending_code(email, "login", {"code": code})

        send_code_email(
            email=email,
            code=code,
            subject="PikaVerse - Confirmar login",
            body_prefix="Use este código para confirmar o login no PikaVerse."
        )

        return jsonify({"ok": True, "message": "Código enviado para o Gmail"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/login/confirm")
def login_confirm():
    try:
        data = request.json or {}
        email = normalize_email(data.get("email", ""))
        code = str(data.get("code", "")).strip()

        snap = read_pending_code(email, "login")
        if not snap.exists:
            return jsonify({"ok": False, "error": "código inválido"}), 400

        pending = snap.to_dict() or {}
        if pending.get("code") != code:
            return jsonify({"ok": False, "error": "código inválido"}), 400
        if now_ts() > int(pending.get("expires_at", 0)):
            delete_pending_code(email, "login")
            return jsonify({"ok": False, "error": "código expirado"}), 400

        user_doc = find_user_by_email(email)
        if not user_doc:
            delete_pending_code(email, "login")
            return jsonify({"ok": False, "error": "usuário não encontrado"}), 404

        user = user_doc.to_dict() or {}
        delete_pending_code(email, "login")

        return jsonify({
            "ok": True,
            "user": {
                "username": user.get("username", ""),
                "uuid": user.get("uuid", ""),
                "email": user.get("email", ""),
                "provider": user.get("provider", "email"),
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
