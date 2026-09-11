# MiniMax Speech adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "minimax-speech"], "timeout_seconds": 600}
```

Required environment: `MINIMAX_API_KEY`. `MINIMAX_BASE_URL` optionally overrides the default
`https://api.minimax.io/v1` and must remain HTTPS.

The job uses the suite's `tts` modality and must have exactly one output. The production prompt is the
line to be spoken, verbatim — not a description of it. Supported public parameters are `model`,
`voice_id`, `emotion`, `speed`, `vol`, `pitch`, `sample_rate`, `bitrate`, and `format`. The requested
format must match the target extension and be `mp3` or `wav`.

`model` and `voice_id` are both required and neither has a default. The model is an account-enabled
endpoint, exactly as for the video providers. The voice is a creative decision recorded in
`视觉设定.md` under the character's 声音方向, and it reaches the adapter through the confirmed job.

## Why the voice catalogue is not listed here

Which preset voices an account can reach depends on the model and on the account, and no published
list is authoritative for both. A catalogue frozen into this suite would eventually refuse a voice
that works, or vouch for one that does not — and either failure would surface as a wrong voice in a
finished film rather than as an error. So the adapter validates the shape of `voice_id` and nothing
more; the value is owned by the document, where a reviewer can see it and a diff can show it
changing.

To discover what an account actually has, read the provider's own voice listing. Do not infer the
catalogue from a console, an aggregator, or any other relay — see the capability-claim rule in
[Adapter Contract](../adapter-contract.md).

## Cloning is out of scope for this adapter

This adapter synthesises from preset voices only. Cloning a voice from a recording is a question of
consent, not of capability: reproducing a natural person's voice requires that person's
authorisation. A creator-authorised reference recording still reaches production the way every other
creator input does — as a file under `输入/` with its authorisation recorded — and it is bound as a
reference, never re-derived here.

## Request shape

The request is non-streaming with `output_format: hex`, `POST /t2a_v2`, and carries
`voice_setting` (`voice_id`, and any of `emotion`, `speed`, `vol`, `pitch`) alongside `audio_setting`
(`sample_rate`, `bitrate`, `format`). The adapter validates `base_resp.status_code`, decodes
`data.audio` as hexadecimal bytes, and writes it to a private temporary file.

`emotion` accepts the provider's seven values: `happy`, `sad`, `angry`, `fearful`, `disgusted`,
`surprised`, `neutral`. Anything outside that set is refused rather than passed through — a rejected
emotion is a typo caught before it is paid for.

Protocol reference: [MiniMax Text to Speech](https://platform.minimax.io/docs/api-reference/speech-t2a-http).
