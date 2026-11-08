# MiniMax Music adapter

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "minimax-music"], "timeout_seconds": 600}
```

- **Environment**: `MINIMAX_API_KEY` (required); `MINIMAX_BASE_URL` (optional HTTPS override, default `https://api.minimax.io/v1`).
- **Job & parameters**: modality `music`, one `.mp3` or `.wav` output matching `format`. `prompt` is the style/mood prompt; supported parameters are `lyrics`, `is_instrumental`, `sample_rate`, `bitrate`, and `format`. `lyrics_optimizer` is always rejected: vocal jobs require exact accepted `lyrics`, and instrumental jobs omit lyrics.
- **Execution**: calls `POST /music_generation` with `model: "music-3.0"` and non-streaming `output_format: "hex"`, validates `base_resp.status_code`, and decodes `data.audio` hex bytes to staging.

Protocol reference: [MiniMax Music Generation](https://platform.minimax.io/docs/api-reference/music-generation).
