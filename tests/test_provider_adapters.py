import base64
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-produce/scripts/provider_adapters.py"
SPEC = importlib.util.spec_from_file_location("short_drama_provider_adapters", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
provider_adapters = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider_adapters)


class ProviderCompilerTests(unittest.TestCase):
    def reference_binding(self) -> dict[str, object]:
        return {
            "slot_id": "REF-HERO",
            "order": 1,
            "path": "输入/reference.png",
            "label": "女主定妆照",
            "role": "identity",
            "may_control": ["脸型", "发型"],
            "must_not_control": ["构图", "动作"],
        }

    def image_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "image",
            "prompt": "vertical character portrait",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/images/portrait.png"],
            "parameters": parameters,
        }

    def video_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "video",
            "prompt": "slow push in as the evidence is revealed",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/video/shot.mp4"],
            "parameters": parameters,
        }

    def music_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "music",
            "prompt": "restrained urban drama score",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/music/cue.mp3"],
            "parameters": parameters,
        }

    def test_seedance_payload_is_explicit_and_contains_only_proven_fields(self) -> None:
        payload = provider_adapters.compile_seedance_payload(
            self.video_job(duration=5, ratio="9:16"),
            model="account-enabled-endpoint",
            allowed_ratios={"9:16"},
            duration_range=(5, 10),
        )
        self.assertEqual(
            payload,
            {
                "model": "account-enabled-endpoint",
                "content": [
                    {
                        "type": "text",
                        "text": "slow push in as the evidence is revealed",
                    }
                ],
                "ratio": "9:16",
                "duration": 5,
            },
        )

    def test_seedance_fails_closed_on_unproven_or_unsafe_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicitly configured"):
            provider_adapters.compile_seedance_payload(self.video_job(), model="")
        with self.assertRaisesRegex(ValueError, "supported profile"):
            provider_adapters.compile_seedance_payload(
                self.video_job(ratio="9:16 --seed 4"),
                model="configured",
                allowed_ratios={"9:16"},
            )
        with self.assertRaisesRegex(ValueError, "1 to 30"):
            provider_adapters.compile_seedance_payload(
                self.video_job(duration=31), model="configured"
            )
        with self.assertRaisesRegex(ValueError, "configured model profile"):
            provider_adapters.compile_seedance_payload(
                self.video_job(duration=12),
                model="configured",
                duration_range=(4, 10),
            )
        fallback_seedance = provider_adapters.compile_seedance_payload(
            self.video_job(duration=5, ratio="9:16"), model="configured"
        )
        self.assertEqual(fallback_seedance["duration"], 5)
        self.assertEqual(fallback_seedance["ratio"], "9:16")

        referenced = self.video_job()
        referenced["references"] = ["输入/reference.png"]
        inline = provider_adapters.compile_seedance_payload(
            referenced,
            model="configured",
            reference_urls=["data:image/png;base64,AAAA"],
            reference_roles=["reference_image"],
        )
        self.assertEqual(
            inline["content"][1]["image_url"]["url"], "data:image/png;base64,AAAA"
        )
        with self.assertRaisesRegex(ValueError, "HTTPS, asset:// or a base64 data URI"):
            provider_adapters.compile_seedance_payload(
                referenced,
                model="configured",
                reference_urls=["file:///etc/passwd"],
                reference_roles=["reference_image"],
            )
        payload = provider_adapters.compile_seedance_payload(
            referenced,
            model="configured",
            reference_urls=["asset://asset-202608160001-example"],
            reference_roles=["reference_image"],
        )
        self.assertEqual(payload["content"][1]["role"], "reference_image")
        adaptive = provider_adapters.compile_seedance_payload(
            self.video_job(ratio="adaptive"),
            model="configured",
            allowed_ratios={"adaptive"},
        )
        self.assertEqual(adaptive["ratio"], "adaptive")

    def test_provider_prompts_preserve_confirmed_reference_semantics(self) -> None:
        video = self.video_job()
        video["references"] = ["输入/reference.png"]
        video["reference_bindings"] = [self.reference_binding()]
        seedance = provider_adapters.compile_seedance_payload(
            video,
            model="configured",
            reference_urls=["asset://asset-202608160001-example"],
            reference_roles=["reference_image"],
        )
        text = seedance["content"][0]["text"]
        self.assertIn("Reference @图片1 (女主定妆照), role identity", text)
        self.assertIn("May control: 脸型, 发型", text)
        self.assertIn("Must not control: 构图, 动作", text)

        image = self.image_job()
        image["references"] = ["输入/reference.png"]
        image["reference_bindings"] = [self.reference_binding()]
        gpt_image = provider_adapters.compile_gpt_image_2_payload(image)
        self.assertIn("Reference contract:", gpt_image["prompt"])
        self.assertIn("Must not control: 构图, 动作", gpt_image["prompt"])

    def test_minimax_continuation_keeps_both_media_and_uses_prompt_language(self) -> None:
        video = self.video_job(
            duration=6,
            resolution="768P",
            prompt_language="en",
        )
        video["references"] = ["输入/previous.mp4", "输入/previous-tail.png"]
        video["reference_bindings"] = [
            {
                **self.reference_binding(),
                "path": "输入/previous.mp4",
                "role": "continuity_video",
                "label": "上一段实际视频",
            },
            {
                **self.reference_binding(),
                "slot_id": "REF-TAIL",
                "order": 2,
                "path": "输入/previous-tail.png",
                "role": "actual_tail_frame",
                "label": "实际尾帧",
            },
        ]
        payload = provider_adapters.compile_minimax_h3_payload(
            video,
            model="configured",
            reference_urls=[
                "https://media.example/previous.mp4",
                "https://media.example/previous-tail.png",
            ],
            reference_roles=["reference_video", "reference_image"],
            allowed_resolutions={"768P"},
            duration_range=(6, 6),
        )
        text = payload["content"][0]["text"]
        self.assertIn("Reference contract:", text)
        self.assertIn("Reference <Video 1> (上一段实际视频), role continuity_video", text)
        self.assertIn("Reference <Picture 1> (实际尾帧), role actual_tail_frame", text)
        self.assertNotIn("prompt_language", payload)
        self.assertEqual(payload["content"][1]["type"], "video_url")
        self.assertEqual(payload["content"][2]["type"], "image_url")

    def speech_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "tts",
            "prompt": "你们做了多久？",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/voice/line.mp3"],
            "parameters": parameters,
        }

    def test_speech_carries_the_confirmed_voice_and_nothing_invented(self) -> None:
        payload = provider_adapters.compile_minimax_speech_payload(
            self.speech_job(
                model="configured-speech-model",
                voice_id="a-preset-voice",
                emotion="neutral",
                speed=0.95,
            )
        )
        self.assertEqual(payload["voice_setting"]["voice_id"], "a-preset-voice")
        self.assertEqual(payload["voice_setting"]["emotion"], "neutral")
        self.assertEqual(payload["text"], "你们做了多久？")
        self.assertEqual(payload["audio_setting"]["format"], "mp3")

    def test_speech_fails_closed_without_a_confirmed_voice_or_model(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicitly configured"):
            provider_adapters.compile_minimax_speech_payload(
                self.speech_job(voice_id="a-preset-voice")
            )
        with self.assertRaisesRegex(ValueError, "confirmed voice_id"):
            provider_adapters.compile_minimax_speech_payload(
                self.speech_job(model="configured-speech-model")
            )
        with self.assertRaisesRegex(ValueError, "unsupported MiniMax speech emotion"):
            provider_adapters.compile_minimax_speech_payload(
                self.speech_job(
                    model="configured-speech-model",
                    voice_id="a-preset-voice",
                    emotion="愤怒",
                )
            )

    def test_speech_does_not_enumerate_the_voice_catalogue(self) -> None:
        """Which presets an account reaches depends on model and account.

        A list frozen into the adapter would either refuse a voice that works or
        vouch for one that does not, so the document owns the value.
        """

        payload = provider_adapters.compile_minimax_speech_payload(
            self.speech_job(
                model="configured-speech-model",
                voice_id="a-voice-this-file-has-never-heard-of",
            )
        )
        self.assertEqual(
            payload["voice_setting"]["voice_id"], "a-voice-this-file-has-never-heard-of"
        )

    def test_seedance_carries_opening_and_closing_frames(self) -> None:
        """A shot anchors both ends, so both frame roles have to reach the wire.

        The adapter used to accept only the three reference roles, which left the
        closing state — already written in every storyboard entry — with no way
        to be bound.
        """

        video = self.video_job(duration=5, ratio="9:16", prompt_language="zh-CN")
        video["references"] = ["输入/start.png", "输入/end.png", "输入/look.png"]
        video["reference_bindings"] = [
            {**self.reference_binding(), "path": "输入/start.png", "order": 1},
            {**self.reference_binding(), "path": "输入/end.png", "order": 2},
            {**self.reference_binding(), "path": "输入/look.png", "order": 3},
        ]
        payload = provider_adapters.compile_seedance_payload(
            video,
            model="doubao-seedance-2-5-260628",
            reference_urls=[
                "https://media.example/start.png",
                "https://media.example/end.png",
                "https://media.example/look.png",
            ],
            reference_roles=["first_frame", "last_frame", "reference_image"],
            allowed_ratios={"9:16"},
            duration_range=(4, 30),
        )
        roles = [item.get("role") for item in payload["content"][1:]]
        self.assertEqual(roles, ["first_frame", "last_frame", "reference_image"])
        # Frame roles keep counting, so the prose token still names the third
        # picture rather than the first.
        self.assertIn("@图片3", payload["content"][0]["text"])

    def test_seedance_takes_one_frame_of_each_end(self) -> None:
        video = self.video_job(duration=5, ratio="9:16")
        video["references"] = ["输入/a.png", "输入/b.png"]
        video["reference_bindings"] = [
            {**self.reference_binding(), "path": "输入/a.png", "order": 1},
            {**self.reference_binding(), "path": "输入/b.png", "order": 2},
        ]
        with self.assertRaisesRegex(ValueError, "one first_frame"):
            provider_adapters.compile_seedance_payload(
                video,
                model="doubao-seedance-2-5-260628",
                reference_urls=[
                    "https://media.example/a.png",
                    "https://media.example/b.png",
                ],
                reference_roles=["first_frame", "first_frame"],
                allowed_ratios={"9:16"},
                duration_range=(4, 30),
            )

    def test_seedance_does_not_inherit_a_sibling_providers_exclusivity(self) -> None:
        """Frame and reference conditioning together is refused by the other
        provider, on that provider's own reference. Nothing in this one's says
        the same, so the adapter must not invent it here."""

        video = self.video_job(duration=5, ratio="9:16")
        video["references"] = ["输入/start.png", "输入/look.png"]
        video["reference_bindings"] = [
            {**self.reference_binding(), "path": "输入/start.png", "order": 1},
            {**self.reference_binding(), "path": "输入/look.png", "order": 2},
        ]
        payload = provider_adapters.compile_seedance_payload(
            video,
            model="doubao-seedance-2-5-260628",
            reference_urls=[
                "https://media.example/start.png",
                "https://media.example/look.png",
            ],
            reference_roles=["first_frame", "reference_image"],
            allowed_ratios={"9:16"},
            duration_range=(4, 30),
        )
        self.assertEqual(len(payload["content"]), 3)

    def test_seedance_2_5_task_types_compile_their_distinct_contracts(self) -> None:
        video = self.video_job(
            duration=20,
            ratio="9:16",
            generate_audio=True,
            omni_reference_task_type="reference",
            prompt_language="zh-CN",
        )
        video["references"] = ["输入/look.png"]
        video["reference_bindings"] = [
            {**self.reference_binding(), "path": "输入/look.png"}
        ]
        reference = provider_adapters.compile_seedance_payload(
            video,
            model="doubao-seedance-2-5-260628",
            reference_urls=["https://media.example/look.png"],
            reference_roles=["reference_image"],
            allowed_ratios={"9:16"},
            duration_range=(4, 30),
        )
        self.assertEqual(reference["duration"], 20)
        self.assertTrue(reference["generate_audio"])
        self.assertEqual(reference["omni_reference_task_type"], "reference")
        self.assertIn("参考 @图片1（女主定妆照），用途：外貌", reference["content"][0]["text"])

        edit = self.video_job(
            duration=-1,
            ratio="adaptive",
            omni_reference_task_type="edit",
        )
        edit["references"] = ["输入/source.mp4"]
        compiled_edit = provider_adapters.compile_seedance_payload(
            edit,
            model="doubao-seedance-2-5-260628",
            reference_urls=["https://media.example/source.mp4"],
            reference_roles=["reference_video"],
            allowed_ratios={"adaptive"},
        )
        self.assertEqual(compiled_edit["duration"], -1)
        with self.assertRaisesRegex(ValueError, "adaptive ratio and duration -1"):
            provider_adapters.compile_seedance_payload(
                {**edit, "parameters": {**edit["parameters"], "duration": 8}},
                model="doubao-seedance-2-5-260628",
                reference_urls=["https://media.example/source.mp4"],
                reference_roles=["reference_video"],
                allowed_ratios={"adaptive"},
                duration_range=(4, 30),
            )

        extend = self.video_job(
            duration=5,
            ratio="adaptive",
            omni_reference_task_type="extend",
            prompt_language="zh-CN",
        )
        extend["references"] = ["输入/previous.mp4", "输入/tail.png"]
        extend["reference_bindings"] = [
            {
                **self.reference_binding(),
                "path": "输入/previous.mp4",
                "label": "上一段实际视频",
                "role": "continuity_video",
            },
            {
                **self.reference_binding(),
                "slot_id": "REF-TAIL",
                "order": 2,
                "path": "输入/tail.png",
                "label": "实际尾帧",
                "role": "actual_tail_frame",
            },
        ]
        compiled_extend = provider_adapters.compile_seedance_payload(
            extend,
            model="doubao-seedance-2-5-260628",
            reference_urls=[
                "https://media.example/previous.mp4",
                "https://media.example/tail.png",
            ],
            reference_roles=["reference_video", "reference_image"],
            allowed_ratios={"adaptive"},
            duration_range=(4, 30),
        )
        extend_text = compiled_extend["content"][0]["text"]
        self.assertIn("输入素材 @视频1（上一段实际视频）", extend_text)
        self.assertIn("输入素材 @图片1（实际尾帧）", extend_text)
        self.assertNotIn("参考 @视频1", extend_text)
        self.assertEqual(compiled_extend["content"][1]["type"], "video_url")
        self.assertEqual(compiled_extend["content"][2]["type"], "image_url")

    def test_provider_rejects_reference_semantics_that_do_not_match_paths(self) -> None:
        image = self.image_job()
        image["references"] = ["输入/another.png"]
        image["reference_bindings"] = [self.reference_binding()]
        with self.assertRaisesRegex(ValueError, "path does not match"):
            provider_adapters.compile_gpt_image_2_payload(image)

    def test_gpt_image_2_payload_matches_the_current_contract(self) -> None:
        payload = provider_adapters.compile_gpt_image_2_payload(
            self.image_job(size="1152x2048", quality="medium")
        )
        self.assertEqual(
            payload,
            {
                "model": "gpt-image-2",
                "prompt": "vertical character portrait",
                "n": 1,
                "output_format": "png",
                "size": "1152x2048",
                "quality": "medium",
            },
        )

    def test_gpt_image_2_rejects_unsupported_and_invalid_geometry(self) -> None:
        for parameters in (
            {"background": "transparent"},
            {"input_fidelity": "high"},
            {"size": "1023x1024"},
            {"size": "512x512"},
            {"size": "3840x3840"},
        ):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                provider_adapters.compile_gpt_image_2_payload(
                    self.image_job(**parameters)
                )

    def test_minimax_music_payload_is_music_3_and_never_invents_duration(self) -> None:
        payload = provider_adapters.compile_minimax_music_payload(
            self.music_job(is_instrumental=True)
        )
        self.assertEqual(
            payload,
            {
                "model": "music-3.0",
                "prompt": "restrained urban drama score",
                "stream": False,
                "output_format": "hex",
                "audio_setting": {
                    "sample_rate": 44100,
                    "bitrate": 256000,
                    "format": "mp3",
                },
                "lyrics_optimizer": False,
                "is_instrumental": True,
            },
        )
        self.assertNotIn("duration", payload)

    def test_minimax_rejects_tts_missing_lyrics_and_instrumental_lyrics(self) -> None:
        tts = self.music_job(is_instrumental=True)
        tts["modality"] = "tts"
        with self.assertRaisesRegex(ValueError, "music job"):
            provider_adapters.compile_minimax_music_payload(tts)
        with self.assertRaisesRegex(ValueError, "requires confirmed lyrics"):
            provider_adapters.compile_minimax_music_payload(self.music_job())
        with self.assertRaisesRegex(ValueError, "must not carry lyrics"):
            provider_adapters.compile_minimax_music_payload(
                self.music_job(is_instrumental=True, lyrics="not allowed")
            )
        with self.assertRaisesRegex(ValueError, "optimizer is forbidden"):
            provider_adapters.compile_minimax_music_payload(
                self.music_job(lyrics_optimizer=True)
            )


    def minimax_video_profile(self) -> dict[str, object]:
        return {
            "allowed_ratios": {"9:16"},
            "allowed_resolutions": {"768P"},
            "duration_range": (4, 15),
        }

    def test_minimax_h3_payload_carries_only_configured_values(self) -> None:
        payload = provider_adapters.compile_minimax_h3_payload(
            self.video_job(duration=6, ratio="9:16", resolution="768P"),
            model="account-enabled-video-model",
            **self.minimax_video_profile(),
        )
        self.assertEqual(
            payload,
            {
                "model": "account-enabled-video-model",
                "content": [
                    {
                        "type": "text",
                        "text": "slow push in as the evidence is revealed",
                    }
                ],
                "duration": 6,
                "resolution": "768P",
                "ratio": "9:16",
            },
        )

    def test_minimax_h3_supports_default_and_narrowed_runtime_profiles(self) -> None:
        job = self.video_job(duration=6, ratio="9:16", resolution="768P")
        with self.assertRaisesRegex(ValueError, "explicitly configured"):
            provider_adapters.compile_minimax_h3_payload(
                job, model="", **self.minimax_video_profile()
            )
        default_payload = provider_adapters.compile_minimax_h3_payload(job, model="m")
        self.assertEqual(default_payload["duration"], 6)
        self.assertEqual(default_payload["ratio"], "9:16")
        self.assertEqual(default_payload["resolution"], "768P")
        with self.assertRaisesRegex(ValueError, "outside the configured model profile"):
            provider_adapters.compile_minimax_h3_payload(
                self.video_job(duration=31, ratio="9:16", resolution="768P"),
                model="m",
            )
        with self.assertRaisesRegex(ValueError, "outside the configured model profile"):
            provider_adapters.compile_minimax_h3_payload(
                self.video_job(duration=30, ratio="9:16", resolution="768P"),
                model="m",
                **self.minimax_video_profile(),
            )
        with self.assertRaisesRegex(ValueError, "outside the configured model profile"):
            provider_adapters.compile_minimax_h3_payload(
                job,
                model="m",
                allowed_ratios={"16:9"},
            )
        with self.assertRaisesRegex(ValueError, "outside the configured model profile"):
            provider_adapters.compile_minimax_h3_payload(
                job,
                model="m",
                allowed_resolutions={"480P"},
            )
        with self.assertRaisesRegex(ValueError, "outside the supported profile"):
            provider_adapters.compile_minimax_h3_payload(
                self.video_job(duration=6, ratio="9:16", resolution="8K"),
                model="m",
                **self.minimax_video_profile(),
            )

    def test_gpt_image_2_supports_batch_outputs_up_to_sixteen(self) -> None:
        batch_job = {
            **self.image_job(size="1024x1536"),
            "outputs": [
                f"剧集/EP001/制作成果/images/candidate-{index}.png"
                for index in range(1, 4)
            ],
        }
        payload = provider_adapters.compile_gpt_image_2_payload(batch_job)
        self.assertEqual(payload["n"], 3)
        self.assertEqual(payload["output_format"], "png")

        mixed = {
            **batch_job,
            "outputs": [
                "剧集/EP001/制作成果/images/a.png",
                "剧集/EP001/制作成果/images/b.webp",
            ],
        }
        with self.assertRaisesRegex(ValueError, "share an output format"):
            provider_adapters.compile_gpt_image_2_payload(mixed)

        too_many = {
            **batch_job,
            "outputs": [
                f"剧集/EP001/制作成果/images/c-{index}.png" for index in range(17)
            ],
        }
        with self.assertRaisesRegex(ValueError, "at most 16 outputs"):
            provider_adapters.compile_gpt_image_2_payload(too_many)

        multi_video = {
            **self.video_job(duration=5, ratio="9:16"),
            "outputs": ["制作成果/a.mp4", "制作成果/b.mp4"],
        }
        with self.assertRaisesRegex(ValueError, "exactly one output"):
            provider_adapters.compile_seedance_payload(multi_video, model="m")

    def test_native_multimodal_prompts_do_not_append_duplicate_reference_tail(
        self,
    ) -> None:
        h3_prompt = (
            "retention_analysis:\n"
            "  anchors: [<Picture 1> protagonist look, <Audio 1> protagonist voice]\n"
            "shot_timeline:\n"
            "  0-5s: <Picture 1> speaks with <Audio 1>."
        )
        h3_job = {
            **self.video_job(
                duration=5,
                ratio="9:16",
                resolution="768P",
                prompt_language="zh-CN",
            ),
            "prompt": h3_prompt,
            "references": ["输入/look.png", "输入/voice.wav"],
            "reference_bindings": [
                {
                    **self.reference_binding(),
                    "path": "输入/look.png",
                    "role": "reference_image",
                },
                {
                    "slot_id": "REF-VOICE",
                    "order": 2,
                    "path": "输入/voice.wav",
                    "label": "音色参考",
                    "role": "reference_audio",
                    "character": "女主",
                    "may_control": ["音色"],
                    "must_not_control": ["台词"],
                },
            ],
        }
        h3_payload = provider_adapters.compile_minimax_h3_payload(
            h3_job,
            model="m",
            reference_urls=[
                "https://cdn.example/look.png",
                "https://cdn.example/voice.wav",
            ],
            reference_roles=["reference_image", "reference_audio"],
        )
        self.assertEqual(h3_payload["content"][0]["text"], h3_prompt)

        seedance_prompt = "@图片1 中的女主转身推门，用 @音频1 的声线低声开口。"
        seedance_job = {
            **h3_job,
            "prompt": seedance_prompt,
            "parameters": {"duration": 5, "ratio": "9:16", "prompt_language": "zh-CN"},
        }
        seedance_payload = provider_adapters.compile_seedance_payload(
            seedance_job,
            model="m",
            reference_urls=[
                "https://cdn.example/look.png",
                "https://cdn.example/voice.wav",
            ],
            reference_roles=["reference_image", "reference_audio"],
        )
        self.assertEqual(seedance_payload["content"][0]["text"], seedance_prompt)

        partial_seedance = {
            **seedance_job,
            "prompt": "@图片1 中的女主转身推门。",
        }
        partial_payload = provider_adapters.compile_seedance_payload(
            partial_seedance,
            model="m",
            reference_urls=[
                "https://cdn.example/look.png",
                "https://cdn.example/voice.wav",
            ],
            reference_roles=["reference_image", "reference_audio"],
        )
        self.assertIn("参考约束：", partial_payload["content"][0]["text"])
        self.assertIn("@音频1", partial_payload["content"][0]["text"])

    def test_minimax_h3_text_to_video_needs_a_concrete_ratio(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires an explicit ratio"):
            provider_adapters.compile_minimax_h3_payload(
                self.video_job(duration=6, resolution="768P"),
                model="m",
                **self.minimax_video_profile(),
            )
        with self.assertRaisesRegex(ValueError, "adaptive ratio"):
            provider_adapters.compile_minimax_h3_payload(
                self.video_job(duration=6, ratio="adaptive", resolution="768P"),
                model="m",
                allowed_ratios={"adaptive"},
                allowed_resolutions={"768P"},
                duration_range=(4, 15),
            )

    def test_minimax_h3_references_need_a_hosted_uri_and_a_declared_role(self) -> None:
        job = {
            **self.video_job(duration=6, resolution="768P"),
            "references": ["输入/first.png"],
            "reference_bindings": [
                {
                    **self.reference_binding(),
                    "path": "输入/first.png",
                    "role": "start_frame",
                }
            ],
        }
        payload = provider_adapters.compile_minimax_h3_payload(
            job,
            model="m",
            reference_urls=["https://cdn.example/first.png"],
            reference_roles=["first_frame"],
            **self.minimax_video_profile(),
        )
        self.assertEqual(
            payload["content"][1],
            {
                "type": "image_url",
                "image_url": {"url": "https://cdn.example/first.png"},
                "role": "first_frame",
            },
        )
        self.assertNotIn("ratio", payload)
        inline = provider_adapters.compile_minimax_h3_payload(
            job,
            model="m",
            reference_urls=["data:image/png;base64,AAAA"],
            reference_roles=["first_frame"],
            **self.minimax_video_profile(),
        )
        self.assertEqual(
            inline["content"][1]["image_url"]["url"], "data:image/png;base64,AAAA"
        )
        with self.assertRaisesRegex(
            ValueError, "HTTPS, mm_file:// or a base64 data URI"
        ):
            provider_adapters.compile_minimax_h3_payload(
                job,
                model="m",
                reference_urls=["file:///etc/passwd"],
                reference_roles=["first_frame"],
                **self.minimax_video_profile(),
            )
        with self.assertRaisesRegex(ValueError, "unsupported MiniMax reference role"):
            provider_adapters.compile_minimax_h3_payload(
                job,
                model="m",
                reference_urls=["https://cdn.example/first.png"],
                reference_roles=["identity"],
                **self.minimax_video_profile(),
            )

    def test_minimax_h3_rejects_mixed_frame_and_reference_modes(self) -> None:
        job = {
            **self.video_job(duration=6, resolution="768P"),
            "references": ["输入/previous.mp4", "输入/tail.png"],
        }
        with self.assertRaisesRegex(ValueError, "cannot be mixed"):
            provider_adapters.compile_minimax_h3_payload(
                job,
                model="m",
                reference_urls=[
                    "https://media.example/previous.mp4",
                    "https://media.example/tail.png",
                ],
                reference_roles=["reference_video", "first_frame"],
                **self.minimax_video_profile(),
            )
    def test_minimax_h3_refuses_a_prompt_beyond_the_provider_limit(self) -> None:
        long_job = {
            **self.video_job(duration=6, ratio="9:16", resolution="768P"),
            "prompt": "a" * (provider_adapters.MINIMAX_VIDEO_PROMPT_LIMIT + 1),
        }
        with self.assertRaisesRegex(ValueError, "exceeds the provider limit"):
            provider_adapters.compile_minimax_h3_payload(
                long_job, model="m", **self.minimax_video_profile()
            )


class ProviderRuntimeTests(unittest.TestCase):
    def test_http_failures_expose_only_stable_whitelisted_evidence(self) -> None:
        cases = (
            (401, "authentication", False),
            (429, "rate_limit", True),
            (503, "server", True),
        )
        for status, category, retryable in cases:
            with self.subTest(status=status):
                error = urllib.error.HTTPError(
                    "https://api.openai.com/v1/images/generations",
                    status,
                    "secret provider message",
                    {
                        "x-request-id": f"req_{status}",
                        "authorization": "Bearer credential-must-not-appear",
                    },
                    io.BytesIO(
                        json.dumps(
                            {
                                "error": {
                                    "code": "rate_limit_exceeded",
                                    "message": "credential-must-not-appear",
                                }
                            }
                        ).encode()
                    ),
                )
                public = provider_adapters._http_failure(
                    "gpt-image-2", error
                ).public("gpt-image-2")
                error.close()
                self.assertEqual(public["http_status"], status)
                self.assertEqual(public["category"], category)
                self.assertEqual(public["retryable"], retryable)
                self.assertEqual(public["code"], "rate_limit_exceeded")
                self.assertEqual(public["request_id"], f"req_{status}")
                self.assertNotIn("message", public)
                self.assertNotIn("credential", json.dumps(public))

    def test_each_runtime_maps_a_successful_offline_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common_env = {
                "ARK_API_KEY": "ark-secret",
                "SEEDANCE_MODEL": "configured-endpoint",
                "OPENAI_API_KEY": "openai-secret",
                "MINIMAX_API_KEY": "minimax-secret",
            }
            with mock.patch.dict(os.environ, common_env, clear=False):
                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    side_effect=[
                        ({"id": "seedance-task"}, {}),
                        (
                            {
                                "status": "succeeded",
                                "content": {"video_url": "https://cdn.example/shot.mp4"},
                            },
                            {},
                        ),
                    ],
                ), mock.patch.object(
                    provider_adapters,
                    "_download",
                    return_value=root / "shot.mp4",
                ):
                    path, task_id = provider_adapters._run_seedance(
                        {
                            "modality": "video",
                            "prompt": "camera holds",
                            "references": [],
                            "outputs": ["制作成果/shot.mp4"],
                            "parameters": {},
                            "project_root": str(root),
                            "output_root": str(root),
                        }
                    )
                    self.assertEqual((path, task_id), (root / "shot.mp4", "seedance-task"))

                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    return_value=(
                        {
                            "data": [
                                {
                                    "b64_json": base64.b64encode(
                                        b"\x89PNG\r\n\x1a\ncontent"
                                    ).decode()
                                }
                            ]
                        },
                        {"x-request-id": "openai-request"},
                    ),
                ):
                    path, request_id = provider_adapters._run_openai(
                        {
                            "modality": "image",
                            "prompt": "portrait",
                            "references": [],
                            "outputs": ["制作成果/portrait.png"],
                            "parameters": {},
                            "project_root": str(root),
                            "output_root": str(root),
                        }
                    )
                    self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
                    self.assertEqual(request_id, "openai-request")

                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    return_value=(
                        {
                            "data": {"audio": b"ID3music".hex(), "status": 2},
                            "trace_id": "minimax-trace",
                            "base_resp": {"status_code": 0},
                        },
                        {},
                    ),
                ):
                    path, trace_id = provider_adapters._run_minimax(
                        {
                            "modality": "music",
                            "prompt": "score",
                            "references": [],
                            "outputs": ["制作成果/cue.mp3"],
                            "parameters": {"is_instrumental": True},
                            "project_root": str(root),
                            "output_root": str(root),
                        }
                    )
                    self.assertEqual(path.read_bytes(), b"ID3music")
                    self.assertEqual(trace_id, "minimax-trace")

    def test_minimax_video_runtime_maps_a_successful_offline_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "MINIMAX_API_KEY": "minimax-secret",
                "MINIMAX_VIDEO_MODEL": "configured-video-model",
                "MINIMAX_VIDEO_RESOLUTIONS": "768P",
                "MINIMAX_VIDEO_RATIOS": "9:16",
                "MINIMAX_VIDEO_MIN_DURATION": "4",
                "MINIMAX_VIDEO_MAX_DURATION": "15",
            }
            job = {
                "modality": "video",
                "prompt": "camera holds",
                "references": [],
                "outputs": ["制作成果/shot.mp4"],
                "parameters": {"duration": 6, "ratio": "9:16", "resolution": "768P"},
                "project_root": str(root),
                "output_root": str(root),
            }
            with mock.patch.dict(os.environ, environment, clear=False):
                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    side_effect=[
                        ({"task_id": "minimax-video-task"}, {}),
                        ({"task": {"status": "running"}}, {}),
                        (
                            {
                                "task": {
                                    "status": "succeeded",
                                    "content": {"url": "https://cdn.example/shot.mp4"},
                                }
                            },
                            {},
                        ),
                    ],
                ), mock.patch.object(
                    provider_adapters, "_download", return_value=root / "shot.mp4"
                ), mock.patch.object(provider_adapters.time, "sleep"):
                    path, task_id = provider_adapters._run_minimax_video(job)
                self.assertEqual((path, task_id), (root / "shot.mp4", "minimax-video-task"))

                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    side_effect=[
                        ({"task_id": "minimax-video-task"}, {}),
                        ({"task": {"status": "surprising"}}, {}),
                    ],
                ), mock.patch.object(provider_adapters.time, "sleep"):
                    with self.assertRaises(provider_adapters.AdapterFailure) as raised:
                        provider_adapters._run_minimax_video(job)
                self.assertEqual(
                    raised.exception.public("minimax-h3")["code"], "unknown_task_status"
                )

    def test_minimax_video_runtime_refuses_an_invalid_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = {
                "modality": "video",
                "prompt": "camera holds",
                "references": [],
                "outputs": ["制作成果/shot.mp4"],
                "parameters": {"duration": 6, "ratio": "9:16", "resolution": "768P"},
                "project_root": str(root),
                "output_root": str(root),
            }
            broken = {
                "MINIMAX_API_KEY": "minimax-secret",
                "MINIMAX_VIDEO_MODEL": "configured-video-model",
                "MINIMAX_VIDEO_RESOLUTIONS": "4K",
                "MINIMAX_VIDEO_MIN_DURATION": "4",
                "MINIMAX_VIDEO_MAX_DURATION": "15",
            }
            with mock.patch.dict(os.environ, broken, clear=False):
                with self.assertRaises(provider_adapters.AdapterFailure) as raised:
                    provider_adapters._run_minimax_video(job)
            self.assertEqual(
                raised.exception.public("minimax-h3")["code"], "invalid_model_profile"
            )

    def test_local_project_references_are_sent_inline(self) -> None:
        """Issue #95: a project image had no way to reach either video provider.

        Both document a base64 data URI as an accepted media input, so the file
        the creator bound is sent directly instead of demanding an upload host
        the suite never provided.
        """
        png = (
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        )
        for provider, runner, env, role, parameters in (
            (
                "Seedance",
                provider_adapters._run_seedance,
                {
                    "ARK_API_KEY": "secret",
                    "SEEDANCE_MODEL": "configured",
                    "SEEDANCE_ALLOWED_RATIOS": "9:16",
                    "SEEDANCE_MIN_DURATION": "4",
                    "SEEDANCE_MAX_DURATION": "15",
                },
                "reference_image",
                {"duration": 5, "ratio": "9:16"},
            ),
            (
                "MiniMax",
                provider_adapters._run_minimax_video,
                {
                    "MINIMAX_API_KEY": "secret",
                    "MINIMAX_VIDEO_MODEL": "configured",
                    "MINIMAX_VIDEO_RESOLUTIONS": "768P",
                    "MINIMAX_VIDEO_RATIOS": "9:16",
                    "MINIMAX_VIDEO_MIN_DURATION": "4",
                    "MINIMAX_VIDEO_MAX_DURATION": "15",
                },
                "first_frame",
                {"duration": 5, "ratio": "9:16", "resolution": "768P"},
            ),
        ):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "reference.png").write_bytes(png)
                job = {
                    "modality": "video",
                    "prompt": "camera holds",
                    "references": ["reference.png"],
                    "reference_bindings": [
                        {
                            "slot_id": "REF-A",
                            "order": 1,
                            "path": "reference.png",
                            "label": "参考图",
                            "role": role,
                            "may_control": ["身份"],
                            "must_not_control": ["构图"],
                        }
                    ],
                    "outputs": ["制作成果/shot.mp4"],
                    "parameters": parameters,
                    "project_root": str(root),
                }
                captured: dict[str, object] = {}

                def fake_request(url, **kwargs):  # type: ignore[no-untyped-def]
                    captured["body"] = kwargs.get("body")
                    raise provider_adapters.AdapterFailure("stop after compile")

                with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(
                    provider_adapters, "_request_json", fake_request
                ):
                    with self.assertRaisesRegex(
                        provider_adapters.AdapterFailure, "stop after compile"
                    ):
                        runner(job)
                body = captured["body"]
                assert isinstance(body, dict)
                urls = [
                    item[item["type"]]["url"]
                    for item in body["content"]
                    if item["type"] != "text"
                ]
                self.assertEqual(len(urls), 1)
                self.assertTrue(urls[0].startswith("data:image/png;base64,"))

    def test_inline_references_are_bounded_and_type_checked(self) -> None:
        """Inlining reads local bytes, so the guards have to hold at that edge."""
        limits = provider_adapters.INLINE_REFERENCE_LIMITS
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "frame.png"
            good.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
            lying = root / "frame2.png"
            lying.write_bytes(b"\xff\xd8\xff" + b"\x00" * 24)
            empty = root / "frame3.png"
            empty.write_bytes(b"")
            wrong_kind = root / "clip.mp4"
            wrong_kind.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16)

            urls = provider_adapters._inline_reference_urls(
                [good], ["reference_image"],
                allowed=provider_adapters.SEEDANCE_REFERENCE_ROLES,
                provider="Seedance",
            )
            self.assertTrue(urls[0].startswith("data:image/png;base64,"))

            for label, paths, roles, expected in (
                ("bytes do not match the suffix", [lying], ["reference_image"], "target media type"),
                ("empty file", [empty], ["reference_image"], "reference is empty"),
                (
                    "video bound to an image role",
                    [wrong_kind],
                    ["reference_image"],
                    "does not accept a .mp4 file",
                ),
            ):
                with self.subTest(case=label):
                    with self.assertRaisesRegex(
                        provider_adapters.AdapterFailure, expected
                    ):
                        provider_adapters._inline_reference_urls(
                            paths, roles,
                            allowed=provider_adapters.SEEDANCE_REFERENCE_ROLES,
                            provider="Seedance",
                        )

            oversized = root / "big.png"
            oversized.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00" * limits["image_url"]
            )
            with self.assertRaisesRegex(
                provider_adapters.AdapterFailure, "exceeds the 30MB inline limit"
            ):
                provider_adapters._inline_reference_urls(
                    [oversized], ["reference_image"],
                    allowed=provider_adapters.SEEDANCE_REFERENCE_ROLES,
                    provider="Seedance",
                )

    def test_minimax_polls_the_official_query_endpoint(self) -> None:
        """Issue #95: the task was created and generated, then never retrieved.

        The official query path is `/query/video_generation/{id}`; this adapter
        polled `/video_generation/{id}`, which never reports a terminal state.
        """
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
        requested: list[tuple[str, str]] = []

        class Response:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload
                self.headers = {}

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, *exc: object) -> bool:
                return False

            def read(self, *_: object) -> bytes:
                payload, self._payload = self._payload, b""
                return payload

        def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
            url = request if isinstance(request, str) else request.full_url
            method = "GET" if isinstance(request, str) else request.method
            requested.append((method, url))
            if url.endswith("/video_generation") and method == "POST":
                return Response(b'{"task_id": "task-1"}')
            if "/query/video_generation/task-1" in url:
                return Response(
                    b'{"task": {"status": "succeeded",'
                    b' "content": {"url": "https://cdn.example/out.mp4"}}}'
                )
            if url == "https://cdn.example/out.mp4":
                return Response(mp4)
            raise AssertionError(f"unexpected request: {method} {url}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.png").write_bytes(png)
            outputs = root / "out"
            outputs.mkdir()
            job = {
                "modality": "video",
                "prompt": "camera holds",
                "references": ["reference.png"],
                "reference_bindings": [
                    {
                        "slot_id": "REF-A",
                        "order": 1,
                        "path": "reference.png",
                        "label": "起始帧",
                        "role": "first_frame",
                        "may_control": ["起始构图"],
                        "must_not_control": ["动作"],
                    }
                ],
                "outputs": ["制作成果/shot.mp4"],
                "parameters": {"duration": 5, "resolution": "768P"},
                "project_root": str(root),
                "output_root": str(outputs),
            }
            environment = {
                "MINIMAX_API_KEY": "secret",
                "MINIMAX_VIDEO_MODEL": "configured",
                "MINIMAX_VIDEO_RESOLUTIONS": "768P",
                "MINIMAX_VIDEO_MIN_DURATION": "4",
                "MINIMAX_VIDEO_MAX_DURATION": "15",
            }
            with mock.patch.dict(os.environ, environment, clear=False), mock.patch.object(
                provider_adapters.urllib.request, "urlopen", fake_urlopen
            ):
                path, task_id = provider_adapters._run_minimax_video(job)
            self.assertEqual(task_id, "task-1")
            self.assertEqual(path.read_bytes(), mp4)

        self.assertEqual(
            requested[0],
            ("POST", "https://api.minimax.io/v2/video_generation"),
        )
        self.assertEqual(
            requested[1],
            ("GET", "https://api.minimax.io/v2/query/video_generation/task-1"),
        )
        create = requested[0]
        self.assertNotIn("/query/", create[1])

    def test_a_reference_without_a_declared_role_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
            with mock.patch.dict(
                os.environ,
                {"ARK_API_KEY": "secret", "SEEDANCE_MODEL": "configured"},
                clear=False,
            ):
                with self.assertRaisesRegex(
                    provider_adapters.AdapterFailure, "reference_bindings entry each"
                ):
                    provider_adapters._run_seedance(
                        {
                            "modality": "video",
                            "prompt": "camera holds",
                            "references": ["reference.png"],
                            "outputs": ["制作成果/shot.mp4"],
                            "parameters": {},
                            "project_root": str(root),
                        }
                    )

    def test_provider_output_must_match_the_confirmed_media_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                provider_adapters.AdapterFailure, "target media type"
            ):
                provider_adapters._temporary_output(
                    {"output_root": directory},
                    "制作成果/frame.png",
                    b"not-a-png",
                )

    def test_multipart_references_are_bounded_and_read_from_pinned_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.png"
            path.write_bytes(b"small-image")
            encoded, content_type = provider_adapters._multipart(
                {"model": "gpt-image-2"}, [path]
            )
            self.assertIn(b"small-image", encoded)
            self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
            with mock.patch.object(provider_adapters, "MAX_REFERENCE_BYTES", 4):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    provider_adapters._multipart({}, [path])

    def test_reference_bytes_survive_a_text_mode_descriptor(self) -> None:
        # 回归：_read_reference 曾用 os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        # 打开描述符。Windows 没有 O_BINARY 时那是文本模式的描述符——os.read 会
        # 把每个 \r\n 折成 \n，并在第一个 0x1A（DOS 文件结束符）处停住。PNG 签名
        # 是 89 50 4E 47 0D 0A 1A 0A，第七个字节正是 0x1A，于是每张参考图都以
        # 5 字节送到 gpt-image-2，供应商回 invalid_image_file / HTTP 400，
        # references 与 reference_bindings 在这个平台上从未成功过。
        #
        # POSIX 没有文本模式，直接断言读回的字节数无法在这里变红。所以本例把
        # O_BINARY 立成一个真实常量，并让 os.read 在调用方没有点名二进制时按
        # Windows CRT 的方式截断：断言的是这段代码有没有「要求」二进制模式。
        payload = b"\x89PNG\r\n\x1a\nIHDR\r\ntail"
        native_binary = getattr(os, "O_BINARY", 0)
        probe = native_binary or 0x8000  # MSVC CRT 的 _O_BINARY
        real_open, real_read = os.open, os.read
        text_mode: set[int] = set()

        def fake_open(target, flags, *args, **kwargs):  # type: ignore[no-untyped-def]
            descriptor = real_open(
                target, (flags & ~probe) | native_binary, *args, **kwargs
            )
            if not flags & probe:
                text_mode.add(descriptor)
            return descriptor

        def fake_read(descriptor: int, length: int) -> bytes:
            data = real_read(descriptor, length)
            if descriptor in text_mode:
                return data.replace(b"\r\n", b"\n").split(b"\x1a", 1)[0]
            return data

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.png"
            path.write_bytes(payload)
            with mock.patch.object(os, "O_BINARY", probe, create=True), mock.patch.object(
                os, "open", fake_open
            ), mock.patch.object(os, "read", fake_read):
                content = provider_adapters._read_reference(path)
        self.assertEqual(content, payload)

    def test_cli_selftest_and_safe_failure_do_not_expose_credentials(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--selftest"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        secret = "credential-must-not-appear"
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = secret
        failed = subprocess.run(
            [sys.executable, str(SCRIPT), "gpt-image-2"],
            input=json.dumps({"modality": "video"}),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(failed.returncode, 1)
        public = json.loads(failed.stdout)
        self.assertEqual(
            public,
            {
                "error": {
                    "provider": "gpt-image-2",
                    "category": "invalid_request",
                    "code": "invalid_job",
                    "retryable": False,
                    "submitted": False,
                    "detail": "adapter requires a image job",
                }
            },
        )
        self.assertEqual(failed.stderr.strip(), "provider adapter failed safely")
        self.assertNotIn(secret, failed.stdout)
        self.assertNotIn(secret, failed.stderr)

    def test_openai_runtime_writes_multiple_requested_images_and_minimax_env_defaults(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            png_a = b"\x89PNG\r\n\x1a\nfirst"
            png_b = b"\x89PNG\r\n\x1a\nsecond"
            with mock.patch.dict(
                os.environ, {"OPENAI_API_KEY": "openai-secret"}, clear=False
            ), mock.patch.object(
                provider_adapters,
                "_request_json",
                return_value=(
                    {
                        "data": [
                            {"b64_json": base64.b64encode(png_a).decode()},
                            {"b64_json": base64.b64encode(png_b).decode()},
                        ]
                    },
                    {"x-request-id": "req-multi"},
                ),
            ):
                paths, request_id = provider_adapters._run_openai(
                    {
                        "modality": "image",
                        "prompt": "two variations",
                        "references": [],
                        "outputs": ["制作成果/a.png", "制作成果/b.png"],
                        "parameters": {},
                        "project_root": str(root),
                        "output_root": str(root),
                    }
                )
            assert isinstance(paths, list)
            self.assertEqual(len(paths), 2)
            self.assertEqual([p.read_bytes() for p in paths], [png_a, png_b])
            self.assertEqual(request_id, "req-multi")

            clean_env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("MINIMAX_VIDEO_")
            }
            clean_env.update(
                {
                    "MINIMAX_API_KEY": "minimax-secret",
                    "MINIMAX_VIDEO_MODEL": "h3-default-profile-model",
                    "MINIMAX_VIDEO_ALLOWED_RATIOS": "9:16,16:9",
                    "MINIMAX_VIDEO_ALLOWED_RESOLUTIONS": "768P,2K",
                }
            )
            with mock.patch.dict(os.environ, clean_env, clear=True):
                ratios, resolutions, duration_range = (
                    provider_adapters._minimax_video_runtime_profile()
                )
            self.assertEqual(ratios, frozenset({"9:16", "16:9"}))
            self.assertEqual(resolutions, frozenset({"768P", "2K"}))
            self.assertIsNone(duration_range)

    def test_prompt_reference_binding_lookahead_does_not_treat_index_10_as_index_1(
        self,
    ) -> None:
        binding = {
            "slot_id": "REF-HERO",
            "order": 1,
            "path": "输入/hero.png",
            "label": "女主定妆照",
            "role": "reference_image",
            "may_control": ["身份"],
            "must_not_control": ["构图"],
        }
        job = {
            "modality": "video",
            "prompt": "保持镜头稳定",
            "references": ["输入/hero.png"],
            "reference_bindings": [binding],
            "outputs": ["制作成果/shot.mp4"],
            "parameters": {"prompt_language": "zh-CN"},
        }
        for false_hit, tokens in (
            ("请避免出现@图片10里的杂物。", ["@图片1"]),
            ("Keep <Picture 10> out of frame.", ["<Picture 1>"]),
            ("请避免出现@图片10里的杂物。", ()),
            ("Keep <Picture 10> out of frame.", ()),
            ("不要混入图10的背景。", ()),
        ):
            with self.subTest(false_hit=false_hit, tokens=tokens):
                self.assertFalse(
                    provider_adapters._prompt_already_binds_references(
                        false_hit, [binding], tokens
                    )
                )
                augmented = provider_adapters._prompt_with_reference_contract(
                    false_hit,
                    job,
                    prompt_language="zh-CN",
                    reference_tokens=tokens,
                )
                self.assertNotEqual(augmented, false_hit)

        for genuine, tokens in (
            ("主角沿用@图片1的五官与发型。", ["@图片1"]),
            ("Match <Picture 1> identity.", ["<Picture 1>"]),
            ("主角沿用图1的五官。", ()),
        ):
            with self.subTest(genuine=genuine, tokens=tokens):
                self.assertTrue(
                    provider_adapters._prompt_already_binds_references(
                        genuine, [binding], tokens
                    )
                )

    def test_minimax_h3_reference_count_caps_fail_preflight_without_burning_confirmation(
        self,
    ) -> None:
        for role, count, cap_label in (
            ("reference_image", 10, "9 image_url"),
            ("reference_video", 4, "3 video_url"),
            ("reference_audio", 4, "3 audio_url"),
        ):
            ext = ".png" if role == "reference_image" else (".mp4" if role == "reference_video" else ".wav")
            refs = [f"输入/ref-{idx}{ext}" for idx in range(1, count + 1)]
            urls = [f"https://cdn.example/ref-{idx}{ext}" for idx in range(1, count + 1)]
            roles = [role] * count
            bindings = [
                {
                    "slot_id": f"REF-{idx:02d}",
                    "order": idx,
                    "path": refs[idx - 1],
                    "label": f"参考{idx}",
                    "role": role,
                    "may_control": ["身份"],
                    "must_not_control": ["动作"],
                }
                for idx in range(1, count + 1)
            ]
            job = {
                "modality": "video",
                "prompt": "camera holds steady",
                "references": refs,
                "reference_bindings": bindings,
                "outputs": ["制作成果/shot.mp4"],
                "parameters": {"duration": 6, "ratio": "9:16", "resolution": "768P"},
            }
            with self.subTest(role=role, count=count):
                with self.assertRaises(provider_adapters.AdapterError) as raised:
                    provider_adapters.compile_minimax_h3_payload(
                        job,
                        model="MiniMax-Hailuo-03",
                        reference_urls=urls,
                        reference_roles=roles,
                    )
                err = raised.exception.public("minimax-h3")
                self.assertEqual(err["code"], "too_many_references")
                self.assertFalse(err["retryable"])
                self.assertFalse(err["submitted"])
                self.assertIn(cap_label, err["detail"])

        # End-to-end check with production_tool: 10 reference images fail preflight and preserve confirmation.
        prod_spec = importlib.util.spec_from_file_location(
            "production_tool_for_h3_cap",
            SUITE / "skills/short-drama-produce/scripts/production_tool.py",
        )
        assert prod_spec and prod_spec.loader
        prod_mod = importlib.util.module_from_spec(prod_spec)
        prod_spec.loader.exec_module(prod_mod)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "proj"
            (root / "输入").mkdir(parents=True)
            (root / "剧集/EP001/制作成果/video").mkdir(parents=True)
            (root / "short-drama.json").write_text("{}", encoding="utf-8")
            refs = []
            bindings = []
            for idx in range(1, 11):
                rel = f"输入/img-{idx:02d}.png"
                (root / rel).write_bytes(png)
                refs.append(rel)
                bindings.append(
                    {
                        "slot_id": f"REF-{idx:02d}",
                        "order": idx,
                        "path": rel,
                        "label": f"图{idx}",
                        "role": "reference_image",
                        "may_control": ["外貌"],
                        "must_not_control": ["台词"],
                    }
                )
            job_path = root / "over-cap-h3.json"
            job_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "job_id": "EP001-H3-OVERCAP",
                        "modality": "video",
                        "adapter": "minimax-h3",
                        "prompt": "Ten reference images.",
                        "references": refs,
                        "reference_bindings": bindings,
                        "outputs": ["剧集/EP001/制作成果/video/out.mp4"],
                        "parameters": {"duration": 6, "ratio": "9:16", "resolution": "768P"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prepared = prod_mod.prepare_job(root, job_path)
            prod_mod.confirm_job(
                root,
                job_id="EP001-H3-OVERCAP",
                confirmation=prepared["confirmation"],
            )
            cfg = Path(directory) / "h3-adapter.json"
            cfg.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "minimax-h3": {
                                "command": [sys.executable, str(SCRIPT), "minimax-h3"],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "MINIMAX_API_KEY": "secret-key",
                    "MINIMAX_VIDEO_MODEL": "MiniMax-Hailuo-03",
                },
                clear=False,
            ):
                with self.assertRaisesRegex(prod_mod.AdapterError, "9 image_url"):
                    prod_mod.run_job(
                        root, job_id="EP001-H3-OVERCAP", adapter_config=cfg
                    )
            self.assertEqual(
                prod_mod.job_status(root, job_id="EP001-H3-OVERCAP")["state"],
                "confirmed",
            )


if __name__ == "__main__":
    unittest.main()
