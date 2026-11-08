# Adapter Contract

The creator-first Markdown source selector declares only image and character-voice references, so video continuation segments cannot be submitted directly through this path; follow the `continuation_route` workflow in `SKILL.md` (`independent_starts` vs `relay_external`) without omitting the source selector.

## Job file

```json
{
  "schema_version": "1.0",
  "job_id": "EP001-MOTION001-video",
  "modality": "video",
  "adapter": "studio-video",
  "prompt": "the exact copyable prompt from MOTION-EP001-001",
  "source": "剧集/EP001/视频提示词.md",
  "source_entry": "MOTION-EP001-001",
  "reference_bindings": [
    {
      "slot_id": "REF-HERO",
      "order": 1,
      "path": "输入/approved-character-reference.png",
      "label": "女主定妆照",
      "role": "reference_image",
      "may_control": ["身份", "造型"],
      "must_not_control": ["构图", "动作"]
    }
  ],
  "references": ["输入/approved-character-reference.png"],
  "outputs": ["剧集/EP001/制作成果/video/SHOT-EP001-001.mp4"],
  "parameters": {"duration": 5, "ratio": "9:16", "prompt_language": "zh-CN"},
  "overwrite": false
}
```

- `modality`: `image`, `video`, `tts` (one spoken utterance), or `music` (one timeline-level cue or song).
- `source` & `source_entry`: for canonical `剧集|episodes/<EP>/` documents, `图片提示词.md` takes `IMG-*` (image), `视频提示词.md` takes `MOTION-*` (video), and `分镜.md` takes `SHOT-*` (image, matching `### 冻结关键帧提示词`). A `music` job uses the timeline music section of `视频提示词.md` without a `MOTION-*` selector. `prepare` requires `prompt` to equal the selected copyable prompt after stripping Markdown quote markers.
- `reference_bindings`: 0–16 ordered bindings (`slot_id`, contiguous `order` from 1, unique project-relative `path`, Chinese `label`, non-empty `role`, and disjoint non-empty `may_control` / `must_not_control` lists).
  - When `source_entry` is present, all fields except provider-specific `role` must match the entry's `参考` (`IMG-*`) or `输入参考图` (`SHOT-*` / `MOTION-*`). Bundled video adapters accept `first_frame`, `last_frame`, `reference_image`, `reference_video`, and `reference_audio` (a video job with references but no bindings fails closed).
  - A `MOTION-*` entry's `参考音频` slots follow the image bindings in audio `顺序` with `role: "reference_audio"` and `character` copied verbatim from `角色`. Bundled compilers derive the voice label from `character`.
  - When rendering a `SHOT-*` start frame from `分镜.md`, `prepare` may omit `PLAN-...` slots only if the remaining `REF-...` bindings stay contiguous from 1. Duplicate binding paths are rejected.
- `references`: 0–16 project-relative file paths; derived in binding order when omitted, or verified to match `reference_bindings` when present.
- `outputs`: 1–16 unique paths rooted at top-level `production/` or `剧集|episodes/<EP>/制作成果|production/` with modality-matching extensions.
- `parameters`: provider-neutral settings only (secret-like keys rejected). Image/video jobs carry `prompt_language` so bundled compilers append reference contracts in the prompt's language without forwarding `prompt_language` to the provider.
- `overwrite`: must be `true` to replace an existing file.

`prepare` records internal byte digests of source and reference files and returns the one-time confirmation phrase; any input change invalidates prior confirmations.

## Adapter config

Keep this file outside the project:

```json
{
  "adapters": {
    "studio-image": {
      "command": ["python3", "/opt/studio/image_adapter.py"],
      "timeout_seconds": 600
    }
  }
}
```

- `command`: argv array (never a shell string); `timeout_seconds`: `1–3600`. Credentials must come from the environment or OS credential store, never this file.
- `reference_roles` (optional list): roles the configured model accepts. When present, `run` rejects unlisted roles before consuming confirmation; `reference_audio` always requires explicit listing in `reference_roles`.

## Adapter stdin

The adapter reads one UTF-8 JSON document from raw stdin (`sys.stdin.buffer`) containing the confirmed job plus:

- `run_id`: unique attempt ID (reused on `collect`).
- `project_root`: on `run`, absolute path to a temporary run-scoped snapshot of confirmed `source` and `references` (deleted after the attempt).
- `output_root`: temporary staging directory where every adapter output must be written as a direct regular-file child (deleted after the attempt).
- `handle_path`: on `run`, persistent path where the adapter atomically writes `{"provider_job_id": "<id>"}` **before polling** so interrupted tasks can be recovered via `collect`.
- `collect_provider_job_id`: present only on `collect`; the adapter must poll and download that existing task without submitting a new request or reading `project_root`.

Bundled image/video compilers append an ordered reference contract (`label`, `role`, `may_control`, `must_not_control`) in `parameters.prompt_language` using the model's native tokens (`@图片1`, `<Picture 1>`), and encode confirmed local project files inline as base64 data URIs after verifying file signatures and size caps (30MB/image, 50MB/video, 15MB/audio, 64MB combined base64 references). External adapters must preserve equivalent semantics or reject the job.

## Adapter stdout

On success, write one UTF-8 JSON object (ASCII-escaped for portability) to stdout:

```json
{
  "outputs": [
    {
      "target": "剧集/EP001/制作成果/images/SHOT001.png",
      "source": "/temporary/adapter/result.png"
    }
  ],
  "provider_job_id": "optional-public-id"
}
```

Targets must match the confirmed order; sources must be direct regular-file children of `output_root` (no symlinks).

On failure, write only whitelisted error metadata to stdout (never prompts, response bodies, paths, or credentials):

```json
{
  "error": {
    "provider": "studio-image",
    "category": "rate_limit",
    "code": "rate_limit_exceeded",
    "http_status": 429,
    "request_id": "request_safe_123",
    "retryable": true
  }
}
```

Confirmation is consumed as soon as `run` starts. A nonzero exit, timeout, malformed response, or mismatched output marks the attempt failed; retry requires a new confirmation, and a job with an unresolved `running` attempt blocks new `prepare`/`confirm`/`run` calls.

## Operational reconciliation

`production_tool.py audit <project>` inspects local metadata and output bytes to report terminal/retryable failures, `orphaned_provider_job` (`action: collect_before_retry`), `running_attempt`, `repeated_content`, `superseded` history, and missing or modified outputs. Claims are ordered by validated completion time and must match the current job fingerprint's exact output set and media types. `audit` always returns `quality_verdict: not_assessed`: execution custody never implies creative or media quality.
