# MiniMax Music adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "minimax-music"], "timeout_seconds": 600}
```

Required environment: `MINIMAX_API_KEY`. `MINIMAX_BASE_URL` optionally overrides the default
`https://api.minimax.io/v1` and must remain HTTPS.

The job uses the suite's `music` modality and must have exactly one output. The production prompt becomes the
music style/mood prompt. Supported public parameters are `lyrics`, `is_instrumental`, `sample_rate`,
`bitrate`, and `format`. The requested format must match the target extension
and be `mp3` or `wav`.

For this confirmed-production profile, `lyrics_optimizer` is rejected even when `true` is requested: supplier-authored lyrics would not have
appeared in the preview. A vocal job therefore requires the exact
accepted lyrics; an instrumental job carries neither lyrics nor an optimizer request.

The request always uses model `music-3.0`, non-streaming `output_format: hex`, and
`POST /music_generation`. The adapter validates `base_resp.status_code`, decodes `data.audio` as hexadecimal bytes,
and writes it to a private temporary file.

Protocol reference: [MiniMax Music Generation](https://platform.minimax.io/docs/api-reference/music-generation).
