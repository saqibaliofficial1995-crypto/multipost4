import os
import time
import requests

REQUIRED_ENV_VARS = [
    "YT_CLIENT_ID",
    "YT_CLIENT_SECRET",
    "YT_REFRESH_TOKEN",
    "DRIVE_FOLDER_ID",
    "GEMINI_API_KEY"
]

def validate_env():
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")

def get_access_token():
    validate_env()
    client_id = os.environ["YT_CLIENT_ID"]
    client_secret = os.environ["YT_CLIENT_SECRET"]
    refresh_token = os.environ["YT_REFRESH_TOKEN"]

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    for attempt in range(5):
        try:
            res = requests.post(token_url, data=data, timeout=20)
            if res.status_code == 200:
                return res.json()["access_token"]
            elif res.status_code in [400, 401]:
                raise RuntimeError(f"OAuth token refresh rejected: {res.status_code} {res.text}")
        except requests.exceptions.RequestException as e:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("Failed to obtain Google access token after multiple attempts.")

def get_gemini_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set.")
    return key

def get_drive_folder_id():
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    if not folder_id:
        raise ValueError("DRIVE_FOLDER_ID is not set.")
    return folder_id
