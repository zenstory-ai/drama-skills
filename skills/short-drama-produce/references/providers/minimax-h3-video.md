# MiniMax H3 video adapter

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "minimax-h3"], "timeout_seconds": 3600}
```

- **Required environment**:
  - `MINIMAX_API_KEY`: MiniMax API key.
  - `MINIMAX_VIDEO_MODEL`: exact enabled model ID (no default).
  - `MINIMAX_VIDEO_RESOLUTIONS`: comma-separated subset of `480P`, `768P`, `2K`.
  - `MINIMAX_VIDEO_MIN_DURATION` and `MINIMAX_VIDEO_MAX_DURATION`: inclusive integer-second range (set both or neither; a job carrying `duration` without this range fails closed).
- **Optional environment**: `MINIMAX_VIDEO_BASE_URL` (default `https://api.minimax.io/v2`), `MINIMAX_VIDEO_RATIOS` (subset of `adaptive`, `1:1`, `3:4`, `4:3`, `9:16`, `16:9`, `21:9`), `MINIMAX_VIDEO_POLL_INTERVAL` (default `5`), `MINIMAX_VIDEO_TIMEOUT_SECONDS` (default `1800`).

## Job & reference compilation

- **Job parameters**: modality `video`, one `.mp4` output. `duration` and `resolution` are required and validated against the environment profile. `ratio` is optional for reference-conditioned jobs and required for text-to-video (`adaptive` is rejected without references). The API has no speech-rate parameter, and prompt timestamps do not change request `duration`.
- **Multimodal `content`**: prompt becomes one `text` item (max 7000 chars); each reference becomes one item with `role` from `reference_bindings[].role` (`first_frame`, `last_frame`, `reference_image`, `reference_video`, `reference_audio`).
  - Frame conditioning (`first_frame` / `last_frame`, at most one each) and full-reference conditioning (`reference_image` ≤ 9, `reference_video` ≤ 3, `reference_audio` ≤ 3; video/audio clips 2–15s each and ≤ 15s total per modality) are mutually exclusive in one request.
  - Compiler continuation support binds the previous video as `reference_video` (`<Video 1>`) and its tail frame as `reference_image` (`<Picture 1>`, never `first_frame`), though the bundled creator-first selector cannot submit video references (see [source-interface boundary](../adapter-contract.md)).
- **URI schemes**: the compiler accepts HTTPS, `mm_file://{file_id}`, or `data:<mime>;base64,<...>` URLs (bundled runtime data-URI encoding and size caps follow [adapter-contract.md](../adapter-contract.md)).
- **Execution**: submits `POST {base}/video_generation`, polls `GET {base}/query/video_generation/{task_id}`, and downloads `task.content.url` to staging (unknown status fails closed).
- **Prompt dialect**: H3 generates audio and video in the same pass; author prompt structure and sound-layer declarations via `$short-drama-video-prompts`.

Protocol reference: [MiniMax video generation API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create).
