import json
import os
import uuid
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPDATA = os.getenv("APPDATA", "")
ATOMIC_DIR = os.path.join(APPDATA, "AtomicLauncher") if APPDATA else BASE_DIR

CREDENTIALS_JSON = os.path.join(ATOMIC_DIR, "credentials.json")
SERVICE_ACCOUNT_JSON = os.path.join(ATOMIC_DIR, "firebase_service_account.json")


def carregar_client_id():
    with open(CREDENTIALS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    installed = data.get("installed", {})
    client_id = installed.get("client_id", "").strip()
    if not client_id:
        raise RuntimeError("client_id não encontrado no credentials.json")
    return client_id


GOOGLE_CLIENT_ID = carregar_client_id()

cred = credentials.Certificate(SERVICE_ACCOUNT_JSON)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/auth/google")
def auth_google():
    try:
        token = (request.json or {}).get("id_token", "").strip()
        if not token:
            return jsonify({"ok": False, "error": "id_token ausente"}), 400

        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=300
        )

        google_id = str(idinfo["sub"])
        email = idinfo.get("email", "")
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

        if not username:
            return jsonify({"ok": False, "error": "username vazio"}), 400

        if len(username) < 3:
            return jsonify({"ok": False, "error": "username deve ter pelo menos 3 caracteres"}), 400

        if len(username) > 16:
            return jsonify({"ok": False, "error": "username deve ter no máximo 16 caracteres"}), 400

        docs = db.collection("users").where("username", "==", username).limit(1).stream()
        for doc in docs:
            if doc.id != google_id:
                return jsonify({"ok": False, "error": "username já está em uso"}), 409

        novo_uuid = str(uuid.uuid4())

        db.collection("users").document(google_id).set({
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False)
