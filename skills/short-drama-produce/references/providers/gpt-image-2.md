# GPT Image 2 adapter

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "gpt-image-2"], "timeout_seconds": 600}
```

- **Environment**: `OPENAI_API_KEY` (required); `OPENAI_BASE_URL` (optional HTTPS override, default `https://api.openai.com/v1`).
- **Job & routing**: modality `image`, exactly one output (`.png`, `.jpeg`, or `.webp`). Zero references route to `POST /images/generations`; 1–16 references route to `POST /images/edits` (`image[]` multipart, high-fidelity behavior without `input_fidelity`). Fixes `model: "gpt-image-2"` and `n: 1`, writing `b64_json` to staging.
- **Parameters**: `width` + `height` (compiled to `size`) or `size`, plus `quality`, `background` (transparent rejected), and `moderation`.

Protocol references: [GPT Image 2 model](https://developers.openai.com/api/docs/models/gpt-image-2),
[image generation](https://developers.openai.com/api/reference/resources/images/methods/generate), and
[image edits](https://developers.openai.com/api/reference/resources/images/methods/edit).
