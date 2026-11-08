# MiniMax Speech adapter

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "minimax-speech"], "timeout_seconds": 600}
```

- **Environment**: `MINIMAX_API_KEY` (required); `MINIMAX_BASE_URL` (optional HTTPS override, default `https://api.minimax.io/v1`).
- **Job & parameters**: modality `tts`, one `.mp3` or `.wav` output matching `format`. `prompt` is the verbatim spoken line (no stage directions). Supported parameters: `model` (required, no default), `voice_id` (required preset ID recorded in `视觉设定.md` 声音方向 by `$short-drama-assets`), `emotion` (`happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, `neutral` — other values rejected), `speed`, `vol`, `pitch`, `sample_rate`, `bitrate`, and `format`.
- **Execution**: preset-voice synthesis only (never clones or uploads reference recordings). Sends non-streaming `POST /t2a_v2` with `output_format: "hex"`, `voice_setting`, and `audio_setting`, validates `base_resp.status_code`, and decodes `data.audio` hex bytes to staging.

Protocol reference: [MiniMax Text to Speech](https://platform.minimax.io/docs/api-reference/speech-t2a-http).
