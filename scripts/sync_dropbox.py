import json, os, pathlib, shutil, urllib.request, urllib.error

TOKEN = os.environ["DROPBOX_ACCESS_TOKEN"].strip()
if TOKEN.lower().startswith("bearer "):
    TOKEN = TOKEN[7:].strip()
if not TOKEN:
    raise RuntimeError("DROPBOX_ACCESS_TOKEN is empty")

ROOT = "/Remembering Rob/Friends Uploads"
DEST = pathlib.Path("uploads")
MANIFEST = pathlib.Path("uploads.json")

FOLDERS = {
    "slaters": "Slaters Bridge",
    "colorado": "Colorado River",
    "emerald": "Emerald Cave",
    "giants": "Giants Causeway",
    "idwal": "Cwm Idwal",
    "glenariffe": "Glenariffe Coast",
}

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".m4v", ".webm"}

def open_dropbox(req):
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = "<unable to read Dropbox error body>"
        raise RuntimeError(f"Dropbox API error {e.code}: {body}") from e

def api(endpoint, payload):
    req = urllib.request.Request(
        "https://api.dropboxapi.com/2/" + endpoint,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with open_dropbox(req) as r:
        return json.load(r)

def list_files(path):
    data = api("files/list_folder", {"path": path, "recursive": False})
    entries = data.get("entries", [])
    while data.get("has_more"):
        data = api("files/list_folder/continue", {"cursor": data["cursor"]})
        entries += data.get("entries", [])
    return [e for e in entries if e.get(".tag") == "file"]

def download(path, target):
    req = urllib.request.Request(
        "https://content.dropboxapi.com/2/files/download",
        headers={"Authorization": f"Bearer {TOKEN}", "Dropbox-API-Arg": json.dumps({"path": path})},
    )
    with open_dropbox(req) as r, open(target, "wb") as f:
        shutil.copyfileobj(r, f)

manifest = {k: [] for k in FOLDERS}
DEST.mkdir(exist_ok=True)

for key, folder in FOLDERS.items():
    out = DEST / key
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in list_files(f"{ROOT}/{folder}"):
        ext = pathlib.Path(item["name"]).suffix.lower()
        if ext not in ALLOWED:
            continue
        safe = pathlib.Path(item["name"]).name.replace("#", "_")
        target = out / safe
        download(item["path_lower"], target)
        manifest[key].append(target.as_posix())

MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: len(v) for k, v in manifest.items()}))
