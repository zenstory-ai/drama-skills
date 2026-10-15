# Seedance adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "seedance"], "timeout_seconds": 3600}
```

Required environment:

- `ARK_API_KEY`: Volcengine Ark API key.
- `SEEDANCE_MODEL`: the exact enabled model/endpoint ID. There is intentionally no model default; in particular the
  adapter never assumes Seedance 2.0.

Optional environment:

- `SEEDANCE_BASE_URL` (default `https://ark.cn-beijing.volces.com/api/v3`)
- `SEEDANCE_POLL_INTERVAL` (default `5` seconds)
- `SEEDANCE_TIMEOUT_SECONDS` (default `1800` seconds)
- `SEEDANCE_ALLOWED_RATIOS`: comma-separated subset explicitly supported by
  the configured model, such as `9:16,16:9`.
- `SEEDANCE_MIN_DURATION` and `SEEDANCE_MAX_DURATION`: the configured model's
  explicit inclusive duration range. Set both or neither. Official integer profiles are `4–15`
  for Seedance 2.0 and `4–30` for Seedance 2.5.

The job must have modality `video` and exactly one `.mp4` output. Optional
`duration` and `ratio` parameters are accepted only when the external runtime
profile above explicitly permits their values, then sent as the API's top-level fields. Optional
`generate_audio` is a boolean. The broad compiler envelope remains configurable rather than proving
that every Seedance release supports every value.

The compiler also forwards `duration: -1` without applying the positive-integer range. For ordinary
Seedance 2.0/2.5 generation this asks the model to choose within its native range; for 2.5 `edit` it
preserves the source video's duration instead. The adapter does not estimate spoken dialogue or
lengthen a short job. Fixed-duration delivery needs an explicit accepted duration; auto-duration
output needs its actual media length and speech checked before timing is accepted. The API response's
integer `duration` rounds down the frame-based duration, so it is not a precise media measurement.

`compile_seedance_payload` accepts explicit `first_frame`, `last_frame`, `reference_image`,
`reference_video`, and `reference_audio` roles with matching HTTPS, `asset://` or base64 data URI values.
Each frame role may appear once; supported role combinations depend on the configured model.
It emits the matching multimodal
content type and uses `@图片N`、`@视频N`、`@音频N` in its appended reference contract. The bundled
runtime sends a project-relative reference inline as a `data:<mime>;base64,<...>` URI, which the
official contract lists alongside a public URL and `asset://`, so binding an image in the creator
documents is enough to run the job. Each file's bytes must match the media type its extension claims.
This adapter applies the same local guards as the MiniMax path: 30MB per image, 50MB per video,
15MB per audio clip, and 64MB for combined base64 reference strings. These guards do not establish
the configured model's native limits; request metadata adds further bytes. An over-limit input
fails before submission. Each
reference takes its provider role from the confirmed job's `reference_bindings[].role`; a job with
references but no bindings fails closed rather than guessing.

Prompt wording for Seedance 2.0 is version-specific: normal reference uses “参考 @视频1”, while
continuation says “向后延长 @视频1” and binds the actual tail as `@图片1`. Use
`$short-drama-video-prompts` for the version's prompt dialect.
These are compiler capabilities; the current creator-first source selector cannot declare the
continuation video, so that route remains unsubmitted in the bundled workflow. See the
[source-interface boundary](../adapter-contract.md).

Seedance 2.5 has its own prompt dialect and may carry
`omni_reference_task_type: reference|edit|extend|auto`. The compiler enforces the documented hard
parameter combinations for `edit` (`adaptive`, `-1`, reference video) and `extend` (`adaptive`,
reference video). It does not infer the task type from prompt keywords, because the API checks that
the explicit type and semantic intent agree.

The adapter creates an asynchronous task, polls `GET /contents/generations/tasks/{id}` until a terminal state, and
downloads `content.video_url` into a private temporary directory. Any unknown status fails closed.

Protocol reference: [Volcengine video generation API](https://www.volcengine.com/docs/82379/1520757).
