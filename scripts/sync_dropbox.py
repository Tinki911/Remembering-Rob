import json, os, pathlib, shutil, subprocess, urllib.request, urllib.error

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

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
ALLOWED = IMAGE_EXTS | VIDEO_EXTS
MAX_WEB_VIDEO = 45 * 1024 * 1024
THUMB_SIZE = 200

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

def transcode_video(src, dest):
    attempts = [(28, 720), (31, 720), (33, 540), (35, 480)]
    for crf, height in attempts:
        if dest.exists():
            dest.unlink()
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", f"scale=-2:'min({height},ih)'",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
            str(dest),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if dest.stat().st_size <= MAX_WEB_VIDEO:
            return
    raise RuntimeError(f"Could not compress video below {MAX_WEB_VIDEO // (1024*1024)} MB: {src.name}")

def thumb_filter():
    return f"scale={THUMB_SIZE}:{THUMB_SIZE}:force_original_aspect_ratio=increase,crop={THUMB_SIZE}:{THUMB_SIZE}"

def make_image_thumbnail(image, thumb):
    cmd = ["ffmpeg", "-y", "-i", str(image), "-frames:v", "1", "-vf", thumb_filter(), "-q:v", "6", "-update", "1", str(thumb)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return thumb.exists()
    except subprocess.CalledProcessError:
        print(f"WARNING: thumbnail failed for {image.name}; gallery uses original image")
        return False

def make_poster(video, poster):
    cmd = ["ffmpeg", "-y", "-ss", "0.7", "-i", str(video), "-frames:v", "1", "-vf", thumb_filter(), "-q:v", "6", "-update", "1", str(poster)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
        if ext in VIDEO_EXTS:
            tmp = pathlib.Path("/tmp") / safe
            stem = pathlib.Path(safe).stem
            target = out / (stem + "-web.mp4")
            poster = out / (stem + "-poster.jpg")
            try:
                download(item["path_lower"], tmp)
                transcode_video(tmp, target)
                make_poster(target, poster)
                manifest[key].append(f"vp:{target.as_posix()}|{poster.as_posix()}")
            except Exception as e:
                print(f"WARNING: skipping video {folder}/{safe}: {e}")
                target.unlink(missing_ok=True)
                poster.unlink(missing_ok=True)
            finally:
                tmp.unlink(missing_ok=True)
        else:
            try:
                target = out / safe
                download(item["path_lower"], target)
                thumb = out / (pathlib.Path(safe).stem + "-thumb.jpg")
                make_image_thumbnail(target, thumb)
                manifest[key].append(target.as_posix())
            except Exception as e:
                print(f"WARNING: skipping image {folder}/{safe}: {e}")

MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: len(v) for k, v in manifest.items()}))