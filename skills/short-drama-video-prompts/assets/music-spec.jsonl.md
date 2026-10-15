# Timeline Music Spec

This file is retained for legacy-format inspection and offline regression fixtures. The current release keeps old project JSON/JSONL read-only; continued editing in that format requires pinned `v0.5.0`. Upgrade into a new project root and confirm the five Markdown documents episode by episode. The instructions below describe the legacy format.

Music is a timeline layer, not a default bed baked into every generated shot.
Create a record only when accepted story or directing material gives music a
specific dramatic job.

The file opens with a `sources` header that declares each upstream snapshot
once. A source key is short, lowercase and derived from the artifact basename;
it stays stable and unique within the file.

```jsonl
{"record_type":"sources","schema_version":"1.0.0","sources":{"screenplay":{"owner":"short-drama-write","artifact":"剧集/EP001/screenplay.md"}}}
```

Every record after the header names the snapshot through its key:

```json
{"music_id":"MUS-EP001-01","scope":{"episode_id":"EP001","start_seconds":0,"end_seconds":12},"source_refs":[{"src":"screenplay","record_id":"EP001-SC001"}],"narrative_function":"<what changes for the audience, and why picture/performance alone is insufficient>","prompt":"<provider-neutral style, mood, instrumentation, energy and scene description>","mode":"instrumental | song","lyrics":null,"mix_intent":{"entry":"<relative entry against picture or dialogue>","exit":"<relative exit or transition>","duck_under_dialogue":true,"loop":false},"status":"candidate"}
```

- `source_refs` carry `src` plus the record or field they point at; the
  artifact's `owner` and `artifact` live in the header entry that `src`
  names.
- `scope` is the accepted timeline interval; it does not promise a supplier can
  generate that exact duration.
- `prompt` contains musical intent only, never model names, API fields, artist
  imitation, remote task identifiers or credentials.
- `song` requires creator-owned or licensed `lyrics`; `instrumental` carries no
  lyrics. Do not ask a provider to silently rewrite accepted lyrics.
- `mix_intent` is an editorial handoff. Production generates a source track;
  editing still owns exact fades, ducking and placement.
