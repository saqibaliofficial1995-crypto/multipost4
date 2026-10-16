import os
import re
import json
import time
import requests

MODEL_PRIORITY = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

def get_live_models(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    headers = {"x-goog-api-key": api_key}
    res = requests.get(url, headers=headers, timeout=20)
    if res.status_code == 200:
        models = [m.get("name", "").replace("models/", "") for m in res.json().get("models", [])]
        candidates = []
        for p in MODEL_PRIORITY:
            for m in models:
                if p in m and m not in candidates:
                    candidates.append(m)
        if candidates:
            return candidates
    return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

def upload_video_to_gemini(video_path, api_key):
    file_size = os.path.getsize(video_path)
    init_url = "https://generativelanguage.googleapis.com/upload/v1beta/files"
    headers = {
        "x-goog-api-key": api_key,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": "video/mp4",
        "Content-Type": "application/json"
    }
    body = {"file": {"display_name": os.path.basename(video_path)}}
    
    res = requests.post(init_url, headers=headers, json=body, timeout=30)
    res.raise_for_status()
    upload_url = res.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        upload_url = res.headers.get("x-goog-upload-url")

    # Upload bytes
    with open(video_path, "rb") as f:
        upload_headers = {
            "x-goog-api-key": api_key,
            "Content-Length": str(file_size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize"
        }
        up_res = requests.post(upload_url, headers=upload_headers, data=f, timeout=180)
        up_res.raise_for_status()
        file_info = up_res.json().get("file", {})

    file_name = file_info.get("name")
    file_uri = file_info.get("uri")

    # Poll until ACTIVE
    for _ in range(30):
        check_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
        c_res = requests.get(check_url, headers={"x-goog-api-key": api_key}, timeout=15)
        if c_res.status_code == 200:
            state = c_res.json().get("state")
            if state == "ACTIVE":
                break
            elif state == "FAILED":
                raise RuntimeError("Gemini video processing failed.")
        time.sleep(4)

    return file_name, file_uri

def delete_gemini_file(file_name, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
    requests.delete(url, headers={"x-goog-api-key": api_key}, timeout=15)
    print(f"[llm_meta] Deleted Gemini temporary file {file_name}.", flush=True)

def clean_text(raw_text):
    text = raw_text.strip()
    # Strip markdown code blocks
    text = re.sub(r"^```(?:json|text)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # If it is JSON, parse and unpack
    try:
        data = json.loads(text)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return data
    except Exception:
        pass

    # Strip prefixes like text:, description:, json:
    text = re.sub(r"^(?:text|description|json):\s*", "", text, flags=re.IGNORECASE)
    return text.strip()

def validate_metadata(meta):
    title = meta.get("title", "").strip()
    
    # 1. Title length < 60
    if len(title) >= 60:
        raise ValueError(f"Title length is {len(title)} >= 60 characters.")
    if not title:
        raise ValueError("Title is empty.")

    # 2. Currency hallucination check
    currency_pattern = re.compile(r"[$€£¥₹]|(USD|AED|EUR|GBP)", re.IGNORECASE)
    if currency_pattern.search(title):
        raise ValueError("Title contains currency symbols or currency codes.")

    # 3. Number+unit hallucination pattern (e.g. 10m, 500k, 2 billion, 500 sqft, 100 feet)
    unit_pattern = re.compile(r"\d+\s*(m|b|k|million|billion|sqft|feet)", re.IGNORECASE)
    if unit_pattern.search(title):
        raise ValueError("Title contains numerical magnitude/unit hallucination.")

    # 4. Tags contract: 10-15 tags, total comma length < 460
    tags = meta.get("tags", [])
    if not isinstance(tags, list) or len(tags) < 10:
        raise ValueError(f"Tags count is {len(tags)}, must be at least 10.")
    tags = tags[:15]
    meta["tags"] = tags
    tags_joined = ",".join(tags)
    if len(tags_joined) >= 460:
        raise ValueError(f"Tags string length {len(tags_joined)} exceeds 460 characters.")

    # 5. Exactly 3 hashtags
    hashtags = meta.get("hashtags", [])
    if not isinstance(hashtags, list) or len(hashtags) != 3:
        raise ValueError(f"Hashtags count is {len(hashtags)}, must be exactly 3.")
    cleaned_hashtags = []
    for h in hashtags:
        h_clean = h.strip()
        if not h_clean.startswith("#"):
            h_clean = f"#{h_clean}"
        cleaned_hashtags.append(h_clean)
    meta["hashtags"] = cleaned_hashtags

    return True

def generate_video_metadata(video_path, api_key, duration_seconds=60):
    models = get_live_models(api_key)
    file_name, file_uri = upload_video_to_gemini(video_path, api_key)

    prompt = """Watch the video frames and listen to the audio carefully. Do NOT use the video filename to guess content.
Perform this exact analysis:
1. Inferred channel topic/niche from the actual video visuals.
2. The language of the video (e.g. 'en', 'es', 'ur', etc.).
3. Relevant YouTube category ID (e.g. '22' for People & Blogs, '24' for Entertainment, '26' for Howto).
4. Engaging SEO Title: Must be under 60 characters with the primary keyword right at the very beginning. NEVER include money amounts, currency signs ($ € £ etc.), or fake stats.
5. Description: First 2 lines must be an intriguing hook, followed by a brief summary.
6. 10 to 15 relevant SEO tags (comma joined length under 460 chars).
7. Exactly 3 relevant hashtags (include #shorts if duration is <= 60 seconds).

Return strictly JSON format:
{
  "inferred_topic": "topic summary",
  "language": "en",
  "category_id": "22",
  "title": "Keyword First: Engaging Short Title",
  "description": "Hook line 1\nHook line 2\nDetailed description...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}"""

    max_attempts = 4
    final_meta = None

    try:
        for attempt in range(max_attempts):
            model = models[attempt % len(models)]
            print(f"[retry] Attempt {attempt+1}/{max_attempts} with model {model}", flush=True)

            gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            }
            body = {
                "contents": [{
                    "parts": [
                        {"file_data": {"mime_type": "video/mp4", "file_uri": file_uri}},
                        {"text": prompt}
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.4,
                    "responseMimeType": "application/json"
                }
            }

            try:
                res = requests.post(gen_url, headers=headers, json=body, timeout=60)
                if res.status_code == 200:
                    cand = res.json().get("candidates", [])
                    if cand:
                        text_part = cand[0]["content"]["parts"][0]["text"]
                        meta = clean_text(text_part)
                        if isinstance(meta, dict):
                            validate_metadata(meta)
                            meta["path"] = "video_ai_gemini"
                            meta["model_used"] = model
                            final_meta = meta
                            break
                        else:
                            print("[fail] Response is not a valid JSON dictionary.", flush=True)
                else:
                    print(f"[fail] Gemini HTTP {res.status_code}: {res.text[:120]}", flush=True)
            except Exception as e:
                print(f"[fail] Validation failed: {e}", flush=True)
            time.sleep(2)

        if not final_meta:
            raise RuntimeError("Failed to generate validated video metadata after 4 attempts.")

        # Log according to exact spec
        topic = final_meta.get("inferred_topic", "General Entertainment")
        title = final_meta.get("title", "")
        desc = final_meta.get("description", "")
        hook = "\n".join([line for line in desc.splitlines() if line.strip()][:2])
        tags = final_meta.get("tags", [])
        hashtags = final_meta.get("hashtags", [])

        print(f"[topic] Inferred channel topic: '{topic}'", flush=True)
        print(f"[llm_meta] Gemini watched the video and inferred channel topic: '{topic}'", flush=True)
        print(f"[meta] Path used: video_ai_gemini | Model used: {final_meta['model_used']}", flush=True)
        print(f"[meta] Title ({len(title)} chars): {title}", flush=True)
        print(f"[meta] Description hook: {hook}", flush=True)
        print(f"[meta] Tags ({len(tags)}): {','.join(tags)}", flush=True)
        print(f"[meta] Hashtags: {' '.join(hashtags)}", flush=True)

        return final_meta
    finally:
        delete_gemini_file(file_name, api_key)
