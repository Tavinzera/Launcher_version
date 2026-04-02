import os
from flask import Flask, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Local: usa JSON
# Cloud Run: pode usar credenciais padrão do ambiente
if not firebase_admin._apps:
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()

db = firestore.client()

@app.get("/health")
def health():
    return jsonify({"ok": True})