"""Pruebas del decodificador con los formatos que producen los navegadores (sin cargar Whisper)."""

import io

import av
import numpy as np
import pytest

from audio import SAMPLE_RATE, decode

SECONDS = 2.0


def encode(container_format: str, codec: str, rate: int, layout: str = "stereo") -> bytes:
    """Un tono de 440 Hz codificado como lo haría MediaRecorder."""
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format=container_format) as container:
        stream = container.add_stream(codec, rate=rate)
        stream.layout = layout
        channels = len(stream.layout.channels)
        t = np.arange(int(rate * SECONDS)) / rate
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype(np.int16)
        samples = np.repeat(tone[np.newaxis, :], channels, axis=0)
        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(samples), format="s16p", layout=layout)
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("container_format", "codec", "rate"),
    [
        ("webm", "libopus", 48_000),  # Chrome y Android
        ("mp4", "aac", 44_100),  # Safari en iPhone
        ("ogg", "libopus", 48_000),  # Firefox
    ],
)
def test_decodifica_lo_que_graban_los_navegadores(container_format, codec, rate):
    audio = decode(encode(container_format, codec, rate))
    assert audio.dtype == np.float32 and audio.ndim == 1
    assert len(audio) / SAMPLE_RATE == pytest.approx(SECONDS, abs=0.15)
    assert 0.2 < np.abs(audio).max() <= 1.0


def test_mezcla_a_mono():
    assert decode(encode("webm", "libopus", 48_000, layout="stereo")).ndim == 1
    assert decode(encode("webm", "libopus", 48_000, layout="mono")).ndim == 1


def test_rechaza_lo_que_no_es_audio():
    with pytest.raises(Exception):  # noqa: B017 - PyAV lanza distintos errores según el contenido
        decode(b"esto no es un audio")
