"""Decodifica el audio que graba el navegador (webm/opus, mp4/aac, ogg...) a lo que espera Whisper."""

import io

import av
import numpy as np

SAMPLE_RATE = 16_000


def decode(data: bytes) -> np.ndarray:
    """Devuelve el audio en mono, 16 kHz y float32 entre -1 y 1.

    Se hace aquí, y no con el decodificador interno de faster-whisper, para no depender de cómo
    llama esa librería a PyAV: un cambio de versión entre ambas dejó la transcripción sin funcionar.
    """
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    with av.open(io.BytesIO(data), mode="r") as container:
        if not container.streams.audio:
            raise ValueError("El archivo no contiene audio")
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                chunks.append(resampled.to_ndarray().reshape(-1))
        # Vaciar el remuestreador: sin esto se pierden las últimas muestras.
        for resampled in resampler.resample(None):
            chunks.append(resampled.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("El audio está vacío")
    return np.concatenate(chunks).astype(np.float32) / 32768.0
