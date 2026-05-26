
from dotenv import load_dotenv
import io
import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    pass

try:
    from azure.storage.blob import BlobServiceClient, PublicAccess
except ImportError:
    pass

app = Flask(__name__)
CORS(app)

# ── Configurações ──────────────────────────────────────────────


AZURE_CONNECTION_STRING = os.environ["AZURE_CONNECTION_STRING"]

AZURE_ACCOUNT  = "stodsm6p2"
CONTAINER_NAME = "aluno-michell"
#SA_JSON_PATH   = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
#SA_JSON_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ── Helpers ────────────────────────────────────────────────────
# def get_drive_service():
#     creds = service_account.Credentials.from_service_account_file(SA_JSON_PATH, scopes=SCOPES)
#     return build("drive", "v3", credentials=creds)

def get_drive_service():
    creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])

    # Corrige quebras de linha da chave privada
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")

    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=SCOPES
    )

    return build("drive", "v3", credentials=creds)

def get_blob_client():
    return BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

def get_container_client():
    return get_blob_client().get_container_client(CONTAINER_NAME)

def fmt_size(b):
    try:
        b = int(b or 0)
    except (ValueError, TypeError):
        return "—"
    if b == 0:   return "—"
    if b < 1024: return f"{b} B"
    if b < 2**20: return f"{b/1024:.1f} KB"
    return f"{b/2**20:.1f} MB"

def ensure_container():
    client = get_blob_client()
    cc = client.get_container_client(CONTAINER_NAME)
    try:
        cc.create_container(public_access=PublicAccess.CONTAINER)
    except Exception as e:
        if "ContainerAlreadyExists" not in str(e):
            raise
    return cc


# ══════════════════════════════════════════════════════════════
#  ROTAS
# ══════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "container": CONTAINER_NAME, "account": AZURE_ACCOUNT})


@app.route("/api/drive/files", methods=["GET"])
def list_drive_files():
    """Lista arquivos de uma pasta do Google Drive."""
    folder_id = request.args.get("folder_id", "root")
    try:
        service  = get_drive_service()
        arquivos = []
        page_token = None
        while True:
            q = f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
            params = dict(q=q, spaces="drive",
                          fields="nextPageToken,files(id,name,size,mimeType,modifiedTime)",
                          pageSize=100)
            if page_token:
                params["pageToken"] = page_token
            res = service.files().list(**params).execute()
            arquivos.extend(res.get("files", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break

        result = [{
            "id":           f["id"],
            "name":         f["name"],
            "size":         fmt_size(f.get("size", 0)),
            "size_raw":     int(f.get("size", 0) or 0),
            "mimeType":     f.get("mimeType", ""),
            "modifiedTime": f.get("modifiedTime", ""),
        } for f in arquivos]

        return jsonify({"success": True, "files": result, "total": len(result)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/blob/files", methods=["GET"])
def list_blob_files():
    """Lista blobs no contêiner Azure."""
    try:
        cc    = get_container_client()
        blobs = list(cc.list_blobs())
        result = [{
            "name":         b.name,
            "size":         fmt_size(b.size),
            "size_raw":     b.size,
            "lastModified": b.last_modified.isoformat() if b.last_modified else "",
            "contentType":  b.content_settings.content_type if b.content_settings else "",
            "url":          f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/{b.name}",
        } for b in blobs]
        return jsonify({"success": True, "files": result, "total": len(result),
                        "container": CONTAINER_NAME, "account": AZURE_ACCOUNT})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/migrate", methods=["POST"])
def migrate():
    """
    Migra um único arquivo do Drive para o Blob.
    Body JSON: { "file_id": "...", "file_name": "..." }
    """
    data     = request.get_json()
    file_id  = data.get("file_id")
    file_name = data.get("file_name")

    if not file_id or not file_name:
        return jsonify({"success": False, "error": "file_id e file_name são obrigatórios"}), 400

    try:
        service = get_drive_service()

        # Download do Drive
        meta = service.files().get(fileId=file_id, fields="mimeType").execute()
        mime = meta.get("mimeType", "")
        EXPORTS = {
            "application/vnd.google-apps.document":
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.google-apps.spreadsheet":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.presentation":
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        buf = io.BytesIO()
        if mime in EXPORTS:
            req = service.files().export_media(fileId=file_id, mimeType=EXPORTS[mime])
        else:
            req = service.files().get_media(fileId=file_id)
        dl = MediaIoBaseDownload(buf, req, chunksize=4*1024*1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        dados = buf.read()

        # Upload para o Azure
        cc = ensure_container()
        blob_client = cc.get_blob_client(file_name)
        blob_client.upload_blob(dados, overwrite=True)

        url = f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/{file_name}"
        return jsonify({"success": True, "url": url, "file_name": file_name})

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "file_name": file_name}), 500


@app.route("/api/migrate/all", methods=["POST"])
def migrate_all():
    """
    Migra todos os arquivos de uma pasta do Drive.
    Body JSON: { "folder_id": "..." }
    """
    data      = request.get_json()
    folder_id = data.get("folder_id", "root")

    try:
        service = get_drive_service()
        arquivos = []
        page_token = None
        while True:
            q = f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
            params = dict(q=q, spaces="drive",
                          fields="nextPageToken,files(id,name,size,mimeType)",
                          pageSize=100)
            if page_token:
                params["pageToken"] = page_token
            res = service.files().list(**params).execute()
            arquivos.extend(res.get("files", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break

        cc = ensure_container()
        results = []
        for f in arquivos:
            try:
                meta = service.files().get(fileId=f["id"], fields="mimeType").execute()
                mime = meta.get("mimeType", "")
                EXPORTS = {
                    "application/vnd.google-apps.document":
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.google-apps.spreadsheet":
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.google-apps.presentation":
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }
                buf = io.BytesIO()
                if mime in EXPORTS:
                    req = service.files().export_media(fileId=f["id"], mimeType=EXPORTS[mime])
                else:
                    req = service.files().get_media(fileId=f["id"])
                dl = MediaIoBaseDownload(buf, req, chunksize=4*1024*1024)
                done = False
                while not done:
                    _, done = dl.next_chunk()
                buf.seek(0)
                dados = buf.read()
                blob_client = cc.get_blob_client(f["name"])
                blob_client.upload_blob(dados, overwrite=True)
                url = f"https://{AZURE_ACCOUNT}.blob.core.windows.net/{CONTAINER_NAME}/{f['name']}"
                results.append({"file_name": f["name"], "success": True, "url": url})
            except Exception as e:
                results.append({"file_name": f["name"], "success": False, "error": str(e)})

        ok  = sum(1 for r in results if r["success"])
        err = sum(1 for r in results if not r["success"])
        return jsonify({"success": True, "results": results, "ok": ok, "errors": err, "total": len(results)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/blob/delete/<path:blob_name>", methods=["DELETE"])
def delete_blob(blob_name):
    """Deleta um blob do contêiner."""
    try:
        cc = get_container_client()
        cc.get_blob_client(blob_name).delete_blob()
        return jsonify({"success": True, "deleted": blob_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
