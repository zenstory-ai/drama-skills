# Seedance adapter

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "seedance"], "timeout_seconds": 3600}
```

- **Required environment**: `ARK_API_KEY`, `SEEDANCE_MODEL` (exact enabled model/endpoint ID, no default).
- **Optional environment**: `SEEDANCE_BASE_URL` (default `https://ark.cn-beijing.volces.com/api/v3`), `SEEDANCE_POLL_INTERVAL` (default `5`), `SEEDANCE_TIMEOUT_SECONDS` (default `1800`), `SEEDANCE_ALLOWED_RATIOS` (e.g. `9:16,16:9`), `SEEDANCE_MIN_DURATION` and `SEEDANCE_MAX_DURATION` (inclusive integer range, e.g. `4–15` for 2.0 or `4–30` for 2.5; set both or neither).

## Job & reference compilation

- **Job parameters**: modality `video`, one `.mp4` output. Optional `duration` and `ratio` must be permitted by the environment profile (`duration: -1` bypasses the positive-integer range for auto-duration or 2.5 `edit` source-duration preservation; integer response `duration` rounds down frames and is not a precise media measurement). Optional `generate_audio` is boolean.
- **Seedance 2.5 task type**: supports `omni_reference_task_type: reference|edit|extend|auto` and enforces hard parameter combinations for `edit` (`adaptive`, `-1`, reference video) and `extend` (`adaptive`, reference video) without inferring task type from prompt keywords.
- **References & tokens**: `compile_seedance_payload` accepts `first_frame`, `last_frame` (at most one each), `reference_image`, `reference_video`, and `reference_audio` from `reference_bindings[].role` (HTTPS, `asset://`, or base64 data URI per [adapter-contract.md](../adapter-contract.md)), emitting `@图片N` / `@视频N` / `@音频N` in the appended reference contract. Author version-specific prompt syntax via `$short-drama-video-prompts`.
- **Execution**: submits task, polls `GET /contents/generations/tasks/{id}`, and downloads `content.video_url` to staging (unknown status fails closed).

Protocol reference: [Volcengine video generation API](https://www.volcengine.com/docs/82379/1520757).
