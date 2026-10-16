# Channel 4 Automation Pipeline (multipost4)

Private cloud automation repository for YouTube Channel 4 (`Jennifer Castro` / `UCZondNewuq0gMQIxEaZOk2g`).

## Core Architecture
- **Cloud-Native**: Runs completely unattended via scheduled CI workflows.
- **Drive Source**: Fetches videos from confirmed inbox folder (`1yauKXcSpZ72rUPGIGO5bRqck7GI3scuA`).
- **FFmpeg Normalizer**: Standardizes video assets to 1080x1920 @ 30fps with 6M video bitrate.
- **Gemini Multimodal Analysis**: Inspects raw video frames to infer niche, language, SEO title, description, tags, and category without relying on filenames.
- **Safety Gate**: Enforces `video_ai_gemini` metadata verification before publishing.
- **Direct YouTube Upload**: Publishes video publicly with comments enabled (`made_for_kids: false`).
- **Autonomous Drive Archival**: Moves published videos to `Uploaded` subfolder and trashes source.
- **Community & Analytics**: Includes autonomous comment reply handler and weekly performance reporter.
