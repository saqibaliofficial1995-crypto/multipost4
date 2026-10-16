import sys
import argparse
from src.ci_run import execute_pipeline
from src.comments import run_comment_responder
from src.analytics import run_weekly_analytics
from src.auth_env import get_access_token, get_gemini_api_key

def main():
    parser = argparse.ArgumentParser(description="Channel 4 Automation Pipeline")
    parser.add_argument("--mode", choices=["upload", "comments", "analytics"], default="upload",
                        help="Mode to run: upload (default), comments, or analytics")
    parser.add_argument("--config", default="config.ci.yaml", help="Path to config file")
    args = parser.parse_args()

    if args.mode == "upload":
        execute_pipeline(args.config)
    elif args.mode == "comments":
        token = get_access_token()
        gemini_key = get_gemini_api_key()
        run_comment_responder(token, gemini_key)
    elif args.mode == "analytics":
        token = get_access_token()
        run_weekly_analytics(token)

if __name__ == "__main__":
    main()
