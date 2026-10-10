"""Audio decoding must work with whatever PyAV version is installed (regression for the 'metadata_errors' crash)."""
import math
import wave

import numpy as np
import pytest

av = pytest.importorskip("av")

from app.stt import decode_audio_16k


def _sine(n=48000, rate=48000):
    return (np.sin(2 * math.pi * 440 * np.arange(n) / rate) * 12000).astype(np.int16)


def test_decodes_wav_to_16k_mono(tmp_path):
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(_sine(16000, 16000).tobytes())
    a = decode_audio_16k(str(p))
    assert a.dtype == np.float32 and abs(len(a) - 16000) < 400 and np.abs(a).max() > 0.1


def test_decodes_browser_style_webm_opus(tmp_path):
    p = tmp_path / "a.webm"
    out = av.open(str(p), "w", format="webm")
    st = out.add_stream("libopus", rate=48000)
    st.layout = "mono"
    frame = av.AudioFrame.from_ndarray(_sine().reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = 48000
    for pkt in st.encode(frame):
        out.mux(pkt)
    for pkt in st.encode(None):
        out.mux(pkt)
    out.close()
    a = decode_audio_16k(str(p))
    assert 14000 < len(a) < 18500 and np.abs(a).max() > 0.1   # ~1 s at 16 kHz, not silent
