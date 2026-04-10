import json
import os
import time
import uuid
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "").strip()
GOOGLE_OAUTH_JSON = os.getenv("GOOGLE_OAUTH_JSON", "").strip()

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

if "private_key" in firebase_dict and isinstance(firebase_dict["private_key"], str):
    firebase_dict["private_key"] = firebase_dict["private_key"].replace("\\n", "\n").strip()
    if not firebase_dict["private_key"].endswith("\n"):
        firebase_dict["private_key"] += "\n"

installed = oauth_dict.get("installed", {})
GOOGLE_CLIENT_ID = str(installed.get("client_id", "")).strip()
if not GOOGLE_CLIENT_ID:
    raise RuntimeError("client_id não encontrado dentro de GOOGLE_OAUTH_JSON")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SKINS_DIR = STATIC_DIR / "skins"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
SKINS_DIR.mkdir(parents=True, exist_ok=True)

MAX_SKIN_BYTES = 2 * 1024 * 1024


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
            "redirect_uris": installed_cfg.get("redirect_uris", ["http://localhost"]),
        }
    }


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def find_user_by_email_doc(email: str):
    email = normalize_email(email)
    docs = db.collection("users").where("email", "==", email).limit(1).stream()
    for doc in docs:
        return doc
    return None


def find_user_by_uuid_doc(uuidv: str):
    uuidv = str(uuidv or "").strip()
    if not uuidv:
        return None
    docs = db.collection("users").where("uuid", "==", uuidv).limit(1).stream()
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


def validate_skin_model(model: str) -> str:
    model = str(model or "classic").strip().lower()
    if model not in ("classic", "slim"):
        return "classic"
    return model


def build_skin_payload(user: dict) -> dict:
    return {
        "skin_type": user.get("skin_type", "default") or "default",
        "skin_url": user.get("skin_url", "") or "",
        "skin_model": validate_skin_model(user.get("skin_model", "classic")),
        "skin_updated_at": int(user.get("skin_updated_at", 0) or 0),
    }


def build_absolute_skin_url(filename: str) -> str:
    return request.host_url.rstrip("/") + f"/static/skins/{filename}"


def delete_existing_skin_files(uuidv: str) -> None:
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = SKINS_DIR / f"{uuidv}.{ext}"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def can_change_skin(uuidv: str):
    user_doc = find_user_by_uuid_doc(uuidv)
    if not user_doc:
        return None, "usuário não encontrado no banco"

    user = user_doc.to_dict() or {}
    provider = str(user.get("provider", "") or "").strip().lower()
    email = str(user.get("email", "") or "").strip()
    username = str(user.get("username", "") or "").strip()
    user_uuid = str(user.get("uuid", "") or "").strip()

    if provider not in ("email", "google"):
        return None, f"provider inválido: {provider or 'vazio'}"

    if not email:
        return None, "conta sem email salvo no banco"

    if not username:
        return None, "conta sem username salvo no banco"

    if not user_uuid:
        return None, "conta sem uuid salvo no banco"

    return user_doc, None


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/auth/google/config")
def auth_google_config():
    return jsonify({"ok": True, "oauth": get_google_oauth_public_config()})


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
            clock_skew_in_seconds=300,
        )

        google_id = str(idinfo["sub"])
        email = normalize_email(idinfo.get("email", ""))
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        existing_email_doc = find_user_by_email_doc(email)

        if existing_email_doc:
            doc_ref = db.collection("users").document(existing_email_doc.id)
            old = existing_email_doc.to_dict() or {}
            current_username = old.get("username", "") or ""
            current_uuid = old.get("uuid", "") or ""

            doc_ref.set({
                "google_id": google_id,
                "email": email,
                "name": name,
                "picture": picture,
                "provider": "google",
                "linked_google": True,
                "updated_at": now_ts(),
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
                "needs_username": not bool(current_username),
            })

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
            "linked_google": True,
            "created_at": now_ts(),
            "updated_at": now_ts(),
            "skin_type": "default",
            "skin_url": "",
            "skin_model": "classic",
            "skin_updated_at": 0,
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
            "needs_username": not bool(current_username),
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

        docs = db.collection("users").where("google_id", "==", google_id).limit(1).stream()
        user_doc = None
        for doc in docs:
            user_doc = doc
            break

        if user_doc is None:
            snap = db.collection("users").document(google_id).get()
            if snap.exists:
                user_doc = snap

        if user_doc is None or not user_doc.exists:
            return jsonify({"ok": False, "error": "usuário Google não encontrado"}), 404

        if username_exists(username, exclude_doc_id=user_doc.id):
            return jsonify({"ok": False, "error": "nickname já está em uso"}), 409

        existing = user_doc.to_dict() or {}
        novo_uuid = existing.get("uuid") or str(uuid.uuid4())

        db.collection("users").document(user_doc.id).set({
            "username": username,
            "uuid": novo_uuid,
            "updated_at": now_ts(),
        }, merge=True)

        return jsonify({
            "ok": True,
            "google_id": google_id,
            "username": username,
            "uuid": novo_uuid,
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

        existing_user = find_user_by_email_doc(email)
        if existing_user:
            return jsonify({"ok": False, "error": "gmail já cadastrado"}), 409

        if username_exists(username):
            return jsonify({"ok": False, "error": "nickname já está em uso"}), 409

        password_hash = generate_password_hash(password)
        user_doc_id = str(uuid.uuid4())
        player_uuid = str(uuid.uuid4())

        db.collection("users").document(user_doc_id).set({
            "provider": "email",
            "email": email,
            "username": username,
            "password_hash": password_hash,
            "uuid": player_uuid,
            "created_at": now_ts(),
            "updated_at": now_ts(),
            "linked_google": False,
            "skin_type": "default",
            "skin_url": "",
            "skin_model": "classic",
            "skin_updated_at": 0,
        })

        return jsonify({
            "ok": True,
            "message": "Conta criada com sucesso",
            "user": {
                "username": username,
                "uuid": player_uuid,
                "email": email,
                "provider": "email",
                "skin_type": "default",
                "skin_url": "",
                "skin_model": "classic",
            },
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/auth/login/start")
def login_start():
    try:
        data = request.json or {}
        email = normalize_email(data.get("email", ""))
        password = str(data.get("password", "")).strip()

        user_doc = find_user_by_email_doc(email)
        if not user_doc:
            return jsonify({"ok": False, "error": "gmail, senha incorretos ou conta inexistente"}), 401

        user = user_doc.to_dict() or {}
        if user.get("provider") == "google" and not user.get("password_hash"):
            return jsonify({"ok": False, "error": "essa conta usa login Google"}), 400

        if not check_password_hash(user.get("password_hash", ""), password):
            return jsonify({"ok": False, "error": "gmail ou senha incorretos"}), 401

        return jsonify({
            "ok": True,
            "message": "Login realizado com sucesso",
            "user": {
                "username": user.get("username", ""),
                "uuid": user.get("uuid", ""),
                "email": user.get("email", ""),
                "provider": user.get("provider", "email"),
                "skin_type": user.get("skin_type", "default"),
                "skin_url": user.get("skin_url", ""),
                "skin_model": user.get("skin_model", "classic"),
                "skin_updated_at": int(user.get("skin_updated_at", 0) or 0),
            },
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/skin/get")
def skin_get():
    try:
        uuidv = str(request.args.get("uuid", "")).strip()
        if not uuidv:
            return jsonify({"ok": False, "error": "uuid ausente"}), 400

        user_doc = find_user_by_uuid_doc(uuidv)
        if not user_doc:
            return jsonify({"ok": False, "error": "usuário não encontrado"}), 404

        user = user_doc.to_dict() or {}
        return jsonify({"ok": True, "skin": build_skin_payload(user)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/skin/upload")
def skin_upload():
    try:
        uuidv = str(request.form.get("uuid", "")).strip()
        skin_model = validate_skin_model(request.form.get("skin_model", "classic"))
        skin_file = request.files.get("skin_file")

        if not uuidv:
            return jsonify({"ok": False, "error": "uuid ausente"}), 400

        user_doc, err = can_change_skin(uuidv)
        if user_doc is None:
            return jsonify({"ok": False, "error": err}), 403

        if skin_file is None or not getattr(skin_file, "filename", ""):
            return jsonify({"ok": False, "error": "arquivo da skin ausente"}), 400

        filename = secure_filename(skin_file.filename or "skin.png")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return jsonify({"ok": False, "error": "formato inválido; envie PNG, JPG, JPEG ou WEBP"}), 400

        raw = skin_file.read()
        if not raw:
            return jsonify({"ok": False, "error": "arquivo vazio"}), 400
        if len(raw) > MAX_SKIN_BYTES:
            return jsonify({"ok": False, "error": "arquivo muito grande; limite de 2 MB"}), 400

        delete_existing_skin_files(uuidv)

        final_name = f"{uuidv}.{ext}"
        final_path = SKINS_DIR / final_name
        with open(final_path, "wb") as f:
            f.write(raw)

        updated_ts = now_ts()
        skin_url = build_absolute_skin_url(final_name) + f"?v={updated_ts}"

        db.collection("users").document(user_doc.id).set({
            "skin_type": "custom",
            "skin_url": skin_url,
            "skin_model": skin_model,
            "skin_updated_at": updated_ts,
            "updated_at": updated_ts,
        }, merge=True)

        return jsonify({
            "ok": True,
            "message": "Skin enviada com sucesso",
            "skin": {
                "skin_type": "custom",
                "skin_url": skin_url,
                "skin_model": skin_model,
                "skin_updated_at": updated_ts,
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/skin/reset")
def skin_reset():
    try:
        data = request.json or {}
        uuidv = str(data.get("uuid", "")).strip()

        if not uuidv:
            return jsonify({"ok": False, "error": "uuid ausente"}), 400

        user_doc, err = can_change_skin(uuidv)
        if user_doc is None:
            return jsonify({"ok": False, "error": err}), 403

        delete_existing_skin_files(uuidv)
        updated_ts = now_ts()

        db.collection("users").document(user_doc.id).set({
            "skin_type": "default",
            "skin_url": "",
            "skin_model": "classic",
            "skin_updated_at": updated_ts,
            "updated_at": updated_ts,
        }, merge=True)

        return jsonify({
            "ok": True,
            "message": "Skin resetada com sucesso",
            "skin": {
                "skin_type": "default",
                "skin_url": "",
                "skin_model": "classic",
                "skin_updated_at": updated_ts,
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
