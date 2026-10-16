import os
import json
import time
import requests

def upload_to_youtube(video_path, metadata, access_token, config):
    # Safety Gate Check
    meta_path = metadata.get("path")
    if meta_path != "video_ai_gemini":
        print(f"[block] Safety block: Publishing blocked because metadata path is '{meta_path}'. Only 'video_ai_gemini' is allowed to publish live.", flush=True)
        raise RuntimeError(f"Safety block triggered: metadata path '{meta_path}' not authorized.")

    title = metadata["title"]
    desc = metadata["description"]
    if config.get("metadata", {}).get("append_hashtags_to_description", True):
        desc = f"{desc}\n\n" + " ".join(metadata.get("hashtags", []))

    snippet = {
        "title": title,
        "description": desc,
        "tags": metadata.get("tags", []),
        "categoryId": str(metadata.get("category_id", config.get("youtube", {}).get("category_id", "22"))),
        "defaultLanguage": metadata.get("language", "en")
    }

    status = {
        "privacyStatus": config.get("youtube", {}).get("privacy_status", "public"),
        "selfDeclaredMadeForKids": False
    }

    body = {"snippet": snippet, "status": status}
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(os.path.getsize(video_path))
    }

    res = requests.post(init_url, headers=headers, json=body, timeout=30)
    res.raise_for_status()
    upload_url = res.headers.get("Location")
    if not upload_url:
        raise RuntimeError("No upload Location header returned by YouTube API.")

    # Upload video content
    with open(video_path, "rb") as f:
        up_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4"
        }
        up_res = requests.put(upload_url, headers=up_headers, data=f, timeout=300)
        up_res.raise_for_status()
        yt_data = up_res.json()

    video_id = yt_data.get("id")
    if not video_id:
        raise RuntimeError("No video ID in YouTube response.")

    # Verify upload and privacy status
    verify_url = f"https://www.googleapis.com/youtube/v3/videos?part=status,snippet&id={video_id}"
    v_res = requests.get(verify_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
    actual_privacy = "unknown"
    actual_upload_status = "unknown"
    if v_res.status_code == 200:
        items = v_res.json().get("items", [])
        if items:
            v_status = items[0].get("status", {})
            actual_privacy = v_status.get("privacyStatus", "unknown")
            actual_upload_status = v_status.get("uploadStatus", "unknown")

    print(f"[yt] Actual privacyStatus: {actual_privacy}, uploadStatus: {actual_upload_status}", flush=True)
    video_url = f"https://youtu.be/{video_id}"
    print(f"[yt] Published successfully: {video_url}", flush=True)

    return video_id, video_url
