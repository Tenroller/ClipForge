"""
Kokoro TTS wrapper for MoneyPrinter

Replaces the old TikTok TTS implementation with Kokoro, matching the
existing function signature used by MoneyPrinter (`tts`).
"""

from __future__ import annotations

import os
import tempfile
import warnings
from typing import List

import soundfile as sf
from termcolor import colored
from kokoro import KPipeline  # type: ignore
from moviepy import AudioFileClip  # type: ignore
import sys


# Subset of Kokoro voices (same set used by brainrot)
VOICES: List[str] = [
    # American English (lang_code='a') - B-grade and above
    "af_heart",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "af_aoede",
    "af_kore",
    "am_michael",
    "am_fenrir",
    "am_puck",
    # British English (lang_code='b') - B-grade and above
    "bf_emma",
    "bf_isabella",
    "bm_fable",
    "bm_george",
]


_PIPELINE = None
_CURRENT_LANG = None


def _lang_for_voice(voice: str) -> str:
    # British voices start with 'b', American with 'a' or 'af/am'
    if voice.startswith("b"):
        return "b"
    return "a"


def _ensure_pipeline(lang_code: str = "a") -> KPipeline:
    global _PIPELINE, _CURRENT_LANG
    if _PIPELINE is None or _CURRENT_LANG != lang_code:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
            warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")
            _PIPELINE = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
            _CURRENT_LANG = lang_code
    return _PIPELINE


def list_voices() -> List[str]:
    return VOICES.copy()


def tts(text: str, voice: str = "af_bella", filename: str = "output.mp3", play_sound: bool = False) -> None:
    if not text:
        print(colored("[-] Please specify a text", "red"))
        return
    if voice not in VOICES:
        print(colored("[-] Voice not available in Kokoro set", "red"))
        return

    try:
        pipeline = _ensure_pipeline(_lang_for_voice(voice))

        # Generate audio (24kHz, mono)
        generator = pipeline(text, voice=voice)
        audio_data = None
        for _, _, audio in generator:
            audio_data = audio
            break
        if audio_data is None:
            raise RuntimeError("Kokoro returned no audio data")

        # Always generate a WAV first, then convert to requested path
        tmp_wav = tempfile.mktemp(suffix=".wav")
        sf.write(tmp_wav, audio_data, 24000)

        # Convert using moviepy/ffmpeg to match requested extension
        clip = AudioFileClip(tmp_wav)
        # Let ffmpeg infer from extension; ensure mp3 when .mp3
        audio_codec = "libmp3lame" if filename.lower().endswith(".mp3") else None
        clip.write_audiofile(filename, codec=audio_codec)  # type: ignore[arg-type]
        clip.close()

        # Cleanup temp
        try:
            os.remove(tmp_wav)
        except OSError:
            pass

        print(colored(f"[+] Audio file saved successfully as '{filename}'", "green"))
        if play_sound:
            # Optional: avoid dependency on playsound; MoviePy already wrote the file
            try:
                import subprocess
                if os.name == "nt":
                    os.startfile(filename)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", filename])
            except Exception:
                pass

    except Exception as e:
        print(colored(f"[-] An error occurred during TTS: {e}", "red"))
