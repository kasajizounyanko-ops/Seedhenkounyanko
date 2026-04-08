from **future** import annotations
import os
import sys
import uuid
import base64
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(**file**))
BCSFE_SRC = os.path.join(BASE_DIR, “BCSFE-Python-main”, “src”)
if os.path.isdir(BCSFE_SRC):
sys.path.insert(0, BCSFE_SRC)

try:
from bcsfe import core
# CoreDataを必ず初期化する
core.core_data.init_data()
except ImportError as e:
print(f”[ERROR] BCSFE のインポートに失敗: {e}”)
sys.exit(1)

app = Flask(**name**, template_folder=“templates”)
CORS(app)

PORT = int(os.environ.get(“PORT”, 5000))
SESSION_STORE: dict[str, dict] = {}
COUNTRY_CODES = {“jp”, “en”, “kr”, “tw”}

def save_file_to_session(session_id: str, save_file, password, cc: str):
data = save_file.to_data().to_bytes()
SESSION_STORE[session_id] = {
“save_data_b64”: base64.b64encode(data).decode(),
“inquiry_code”: save_file.inquiry_code,
“password_refresh_token”: save_file.password_refresh_token,
“password”: password,
“cc”: cc,
“energy_penalty_timestamp”: float(save_file.energy_penalty_timestamp),
}

def restore_save_file(session_id: str):
sess = SESSION_STORE.get(session_id)
if sess is None:
return None
raw = base64.b64decode(sess[“save_data_b64”])
cc = core.CountryCode(sess[“cc”])
save_file = core.SaveFile(core.Data(raw), cc=cc)
save_file.inquiry_code = sess[“inquiry_code”]
save_file.password_refresh_token = sess[“password_refresh_token”]
save_file.energy_penalty_timestamp = sess[“energy_penalty_timestamp”]
password = sess.get(“password”)
if password:
sh = core.ServerHandler(save_file, print=False)
sh.save_password(password)
return save_file, password

@app.route(”/”)
def index():
return send_from_directory(“templates”, “index.html”)

@app.route(”/api/health”)
def health():
return jsonify({“status”: “ok”})

@app.route(”/api/download”, methods=[“POST”])
def download_save():
body = request.json or {}
transfer_code = body.get(“transfer_code”, “”).strip()
confirmation_code = body.get(“confirmation_code”, “”).strip()
cc_str = body.get(“country_code”, “jp”).strip().lower()

```
if not transfer_code or not confirmation_code:
    return jsonify({"error": "引き継ぎコードと確認コードを入力してください"}), 400
if cc_str not in COUNTRY_CODES:
    return jsonify({"error": "無効な国コードです"}), 400

try:
    cc = core.CountryCode(cc_str)
    gv = core.GameVersion(120200)
    server_handler, result = core.ServerHandler.from_codes(
        transfer_code, confirmation_code, cc, gv,
        print=False, save_backup=False,
    )
except Exception as e:
    traceback.print_exc()
    return jsonify({"error": f"サーバー接続エラー: {str(e)}"}), 500

if server_handler is None:
    detail = ""
    if result and result.response is not None:
        try:
            detail = result.response.json().get("message", result.response.text[:200])
        except Exception:
            detail = result.response.text[:200]
    return jsonify({"error": f"コードが無効またはサーバーエラー。{detail}"}), 400

save_file = server_handler.save_file
gatya = save_file.gatya
session_id = str(uuid.uuid4())
save_file_to_session(session_id, save_file, server_handler.get_stored_password(), cc_str)

return jsonify({
    "session_id": session_id,
    "rare_seed": gatya.rare_seed,
    "normal_seed": gatya.normal_seed,
    "event_seed": gatya.event_seed,
    "inquiry_code": save_file.inquiry_code,
})
```

@app.route(”/api/upload”, methods=[“POST”])
def upload_save():
body = request.json or {}
session_id = body.get(“session_id”, “”)
rare_seed = body.get(“rare_seed”)
normal_seed = body.get(“normal_seed”)
event_seed = body.get(“event_seed”)

```
if not session_id or session_id not in SESSION_STORE:
    return jsonify({"error": "セッションが無効です。最初からやり直してください"}), 400

for name, val in [("rare_seed", rare_seed), ("normal_seed", normal_seed), ("event_seed", event_seed)]:
    if val is None:
        return jsonify({"error": f"{name} が指定されていません"}), 400
    try:
        if not (0 <= int(val) <= 4294967295):
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": f"{name} は 0〜4294967295 の整数で入力してください"}), 400

restored = restore_save_file(session_id)
if restored is None:
    return jsonify({"error": "セッションデータの復元に失敗しました"}), 500

save_file, _ = restored
save_file.gatya.rare_seed = int(rare_seed)
save_file.gatya.normal_seed = int(normal_seed)
save_file.gatya.event_seed = int(event_seed)

try:
    server_handler = core.ServerHandler(save_file, print=False)
    result = server_handler.get_codes(upload_managed_items=False)
except Exception as e:
    traceback.print_exc()
    return jsonify({"error": f"アップロードエラー: {str(e)}"}), 500

if result is None:
    return jsonify({"error": "アップロードに失敗しました"}), 500

transfer_code, confirmation_code = result
SESSION_STORE.pop(session_id, None)

return jsonify({
    "transfer_code": transfer_code,
    "confirmation_code": confirmation_code,
})
```

if **name** == “**main**”:
app.run(host=“0.0.0.0”, port=PORT, debug=False)
