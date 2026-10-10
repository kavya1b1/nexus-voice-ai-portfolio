"""Local speech-to-text with faster-whisper (CTranslate2). The model downloads once, then runs offline on CPU.

The model is warmed up in a background thread at server start and verified with a silent self-test, so a broken
install (for example an outdated `av` package) is detected immediately and the website falls back to the
browser's own speech recognition instead of hanging.
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
import threading
import wave

import numpy as np

from .config import Settings

log = logging.getLogger("voice-agent.stt")


def decode_audio_16k(path: str) -> np.ndarray:
    """Decode any audio file (browser WebM/Opus, WAV, MP3 ...) to 16 kHz mono float32 using PyAV directly.

    faster-whisper's own decoder passes an argument (`metadata_errors`) that PyAV 19 removed, which breaks the
    latest faster-whisper with the latest PyAV. Decoding here uses only long-stable PyAV calls, so it works with
    any PyAV version, and the resulting array is handed to Whisper directly.
    """
    import av

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)

    def frames(out):
        if out is None:
            return []
        return out if isinstance(out, (list, tuple)) else [out]

    parts = []
    with av.open(path, mode="r") as container:
        stream = next(s for s in container.streams if s.type == "audio")
        for frame in container.decode(stream):
            parts += [f.to_ndarray().reshape(-1) for f in frames(resampler.resample(frame))]
        parts += [f.to_ndarray().reshape(-1) for f in frames(resampler.resample(None))]
    if not parts:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(parts).astype(np.float32) / 32768.0


class Transcriber:
    def __init__(self, settings: Settings):
        self.s = settings
        self._model = None
        self._lock = threading.Lock()
        self.ready = False
        self.error = ""

    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:
            return False

    def _load(self):
        with self._lock:  # one load at a time, even if several requests arrive together
            if self._model is None:
                from faster_whisper import WhisperModel

                log.info("loading Whisper model %s …", self.s.whisper_model)
                self._model = WhisperModel(self.s.whisper_model, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, data: bytes, suffix: str = ".webm") -> str:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            path = f.name
        try:
            audio = decode_audio_16k(path)
            if audio.size < 1600:  # under 0.1 s: nothing to transcribe
                return ""
            segments, _ = self._load().transcribe(audio, language="en", vad_filter=True, beam_size=1)
            return " ".join(seg.text.strip() for seg in segments).strip()
        finally:
            os.unlink(path)

    # ── start-up warm-up + self-test ──────────────────────
    def warmup_async(self) -> None:
        if self.available():
            threading.Thread(target=self._warmup, daemon=True, name="whisper-warmup").start()

    def _warmup(self) -> None:
        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:  # one second of silence
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\x00\x00" * 16000)
            self.transcribe(buf.getvalue(), ".wav")
            self.ready, self.error = True, ""
            log.info("local speech-to-text ready (%s)", self.s.whisper_model)
        except Exception as exc:
            self.ready, self.error = False, f"{type(exc).__name__}: {exc}"
            log.warning("Local speech-to-text disabled -> the website will use browser speech recognition. Reason: %s", self.error)
            if "metadata_errors" in self.error:
                log.warning("Fix: pip install --upgrade av   (your PyAV is older than faster-whisper expects)")
