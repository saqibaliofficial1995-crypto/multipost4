# Channel 4 Automation Pipeline (`multipost4`)

Fully automated, cloud-native YouTube channel automation pipeline for **Jennifer Castro** (`UCZondNewuq0gMQIxEaZOk2g`), running entirely on GitHub-hosted runners without any local machine dependencies.

---

## 1. Channel & Infrastructure Details

| Parameter | Identifier / Value |
| :--- | :--- |
| **YouTube Channel Name** | `Jennifer Castro` |
| **YouTube Channel ID** | `UCZondNewuq0gMQIxEaZOk2g` |
| **Google Cloud Project** | `yt-multipost-channel4` |
| **Primary Account** | `alamhaiderazaz@gmail.com` |
| **GitHub Repo** | `alamhaiderazaz-commits/multipost4` (Private) |
| **GitHub Pages** | `https://alamhaiderazaz-commits.github.io/` |
| **Google Drive Inbox ID** | `1yauKXcSpZ72rUPGIGO5bRqck7GI3scuA` |
| **Google Drive Uploaded ID**| `11w1DI_UD7WzNZ-6egFXoVlV5gfSkPs-I` |

---

## 2. Automated Schedules (GitHub Actions)

All jobs execute on Microsoft Azure / GitHub-hosted runners (`ubuntu-latest`):

1. **Daily Upload (`daily-upload.yml`)**:
   - **Cron:** `15 2,8,14 * * *` (UTC)
   - **PKT Schedule:** Daily at **07:15**, **13:15**, and **19:15 PKT** (3 uploads/day, 1 per slot)
   - **Pipeline Actions:** Downloads oldest video from Drive inbox, normalizes to 1080x1920 30fps with FFmpeg, analyzes video with Gemini multimodal AI, enforces strict metadata contract (`video_ai_gemini`), uploads publicly to YouTube (`made_for_kids: false`), moves video to `Uploaded` subfolder, and commits upload history to `state/uploaded.json`.

2. **Comment Replies (`comment-replies.yml`)**:
   - **Cron:** `0 16 * * *` (UTC) -> Daily at **21:00 PKT**
   - **Pipeline Actions:** Reads recent top-level comments, generates context-aware engaging replies with Gemini, replies and records reply IDs in `state/replied.json`.

3. **Weekly Analytics (`weekly-analytics.yml`)**:
   - **Cron:** `0 17 * * 0` (UTC) -> Sundays at **22:00 PKT**
   - **Pipeline Actions:** Queries YouTube Analytics API for 7-day views, watch time, estimated subscribers, and publishes a markdown summary report to workflow summary.

---

## 3. GitHub Actions Secrets

The pipeline requires exactly 5 repository secrets configured via STDIN (never stored in repository files):

- `DRIVE_FOLDER_ID`: `1yauKXcSpZ72rUPGIGO5bRqck7GI3scuA`
- `GEMINI_API_KEY`: API key for Gemini Multimodal Analysis
- `YT_CLIENT_ID`: OAuth 2.0 Desktop Client ID
- `YT_CLIENT_SECRET`: OAuth 2.0 Desktop Client Secret
- `YT_REFRESH_TOKEN`: OAuth Refresh Token with YouTube & Drive scopes

*Note: No Personal Access Token (PAT) is used; all repository commits use the built-in `GITHUB_TOKEN` with `contents: write` permissions.*

---

## 4. Troubleshooting & Break-Risk Playbook

| Issue / Risk | Cause | One-Line Fix |
| :--- | :--- | :--- |
| **Drive Inbox Empty** | All 134+ videos processed | Drop new `.mp4` video files into Drive folder `1yauKXcSpZ72rUPGIGO5bRqck7GI3scuA`. |
| **Gemini 503 / Quota Spike** | Google AI transient high traffic | Automatic backoff retries handle transient spikes; video stays in inbox for next scheduled run. |
| **GitHub Inactivity Pause** | Repo without commits for 60 days pauses crons | The pipeline automatically commits `state/*.json` upon uploads, preventing inactivity pauses. If paused, click **Enable workflow** in GitHub Actions. |
| **YouTube API 10,000 Quota** | Daily YouTube upload quota exceeded (approx 6 uploads/day limit) | Keep daily schedule at 3 videos/day (`15 2,8,14 * * *`). Quota automatically resets at 00:00 PST (12:00 PKT). |
| **OAuth Token Revocation** | Password change or OAuth consent app reset | Re-authenticate locally with `Channel 4 Desktop` client and update `YT_REFRESH_TOKEN` via `gh secret set YT_REFRESH_TOKEN`. |

---

## 5. Security & Isolation Guarantee

- **Full Account Isolation:** 100% owned by `alamhaiderazaz@gmail.com`.
- **Zero Secrets in Git History:** Verified with `git log -S` and `git grep -E` (0 hits).
- **Ignored Credentials:** The local `tokens/` directory is strictly ignored in `.gitignore`.
- **Cloud-Native / PC-Off:** Workflows run autonomously in the cloud; user PC can remain powered off.
