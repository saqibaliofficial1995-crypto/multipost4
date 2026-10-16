import os
import json
import yaml
import datetime
import argparse
import requests

from src.auth_env import get_access_token, get_gemini_api_key, get_drive_folder_id
from src.drive_source import list_pending_videos, download_video, move_to_uploaded_and_trash
from src.normalize import normalize_video, get_video_duration
from src.llm_meta import generate_video_metadata
from src.upload_youtube_ci import upload_to_youtube

def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_state(state_file):
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"items": {}, "history": []}

def save_state(state, state_file):
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def get_uploaded_ids(state):
    uploaded = set()
    # Check items
    items = state.get("items", {})
    if isinstance(items, dict):
        for fid, entry in items.items():
            if isinstance(entry, dict):
                if entry.get("youtube_video_id") or entry.get("uploaded_at_utc"):
                    uploaded.add(fid)
            elif isinstance(entry, str) and entry.strip():
                uploaded.add(fid)

    # Check history
    for entry in state.get("history", []):
        if isinstance(entry, dict):
            fid = entry.get("drive_file_id") or entry.get("id")
            if fid and (entry.get("youtube_video_id") or entry.get("uploaded_at_utc")):
                uploaded.add(fid)

    return uploaded

def execute_pipeline(config_path="config.ci.yaml"):
    print("[start] Channel 4 Multipost Run starting...", flush=True)
    config = load_config(config_path)
    
    is_dry_run = os.environ.get("DRY_RUN", "false").lower() in ["true", "1", "yes"]
    env_max = os.environ.get("MAX_UPLOADS")
    
    state_file = os.path.join(config.get("paths", {}).get("state", "state"), "uploaded.json")
    state = load_state(state_file)
    uploaded_ids = get_uploaded_ids(state)

    access_token = get_access_token()
    gemini_key = get_gemini_api_key()

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    inbox_id = config.get("drive", {}).get("inbox_folder_id")
    uploaded_folder_id = config.get("drive", {}).get("uploaded_folder_id")

    # List pending videos
    pending_videos = list_pending_videos(session, inbox_id, uploaded_ids)
    if not pending_videos:
        print("[finish] Nothing to upload. Inbox is clear.", flush=True)
        return

    work_dir = config.get("paths", {}).get("work", "work")
    os.makedirs(work_dir, exist_ok=True)

    max_videos = int(env_max) if env_max and env_max.isdigit() else config.get("schedule", {}).get("max_videos_per_run", 1)
    processed_count = 0

    for video_info in pending_videos[:max_videos]:
        file_id = video_info["id"]
        file_name = video_info["name"]
        print(f"-------- Processing: {file_name} (ID: {file_id}) --------", flush=True)

        raw_path = os.path.join(work_dir, f"raw_{file_id}.mp4")
        norm_path = os.path.join(work_dir, f"norm_{file_id}.mp4")

        try:
            # 1. Download
            download_video(session, file_id, raw_path)

            # 2. Normalize via FFmpeg
            normalize_video(raw_path, norm_path, config.get("encode", {}))
            duration = get_video_duration(norm_path)

            # 3. Gemini Multimodal Analysis
            metadata = generate_video_metadata(norm_path, gemini_key, duration_seconds=duration)

            if is_dry_run:
                print(f"[dry-run] Dry run active. Validated metadata path: '{metadata.get('path')}'. Skipping YouTube upload and Drive move for {file_name}.", flush=True)
                processed_count += 1
                continue

            # 4. Upload to YouTube (with safety gate check)
            yt_id, yt_url = upload_to_youtube(norm_path, metadata, access_token, config)

            # 5. Move and trash in Drive
            move_to_uploaded_and_trash(session, file_id, uploaded_folder_id, file_name)

            # 6. Update state
            record = {
                "drive_file_id": file_id,
                "filename": file_name,
                "title": metadata["title"],
                "youtube_video_id": yt_id,
                "youtube_url": yt_url,
                "uploaded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            state.setdefault("items", {})[file_id] = record
            state.setdefault("history", []).append(record)
            save_state(state, state_file)
            print("[state] Recorded upload state.", flush=True)

            processed_count += 1
        finally:
            # Clean local work files
            for p in [raw_path, norm_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    print(f"[finish] Processed {processed_count} video(s).", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.ci.yaml", help="Path to config file")
    args = parser.parse_args()
    execute_pipeline(args.config)
