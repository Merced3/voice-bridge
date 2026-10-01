"""s16le 48 kHz mono ↔ stereo conversion.

The browser page speaks mono (one microphone, one speaker path); the
consumer contract mirrors discord-hub's wire format, which is stereo.
These two functions are the entire per-transport wire adaptation — the
event and ownership shapes are unaffected.
"""

from __future__ import annotations


def mono_to_stereo(pcm: bytes) -> bytes:
    """Duplicate each s16le sample into both channels."""
    n = len(pcm) - (len(pcm) % 2)
    return b"".join(pcm[i : i + 2] * 2 for i in range(0, n, 2))


def stereo_to_mono(pcm: bytes) -> bytes:
    """Keep the left channel of s16le stereo frames."""
    n = len(pcm) - (len(pcm) % 4)
    return b"".join(pcm[i : i + 2] for i in range(0, n, 4))
