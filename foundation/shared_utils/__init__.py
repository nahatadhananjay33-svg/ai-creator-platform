"""Cross-cutting utilities: timing, hashing, audio I/O, hardware probing, text."""

from foundation.shared_utils.timing import Stopwatch, utc_now_iso
from foundation.shared_utils.hashing import sha256_file, sha256_text, short_hash
from foundation.shared_utils.audio_io import WavData, read_wav, write_wav, generate_sine_wav
from foundation.shared_utils.hardware import HardwareProfile, probe_hardware
from foundation.shared_utils.text import slugify, new_run_id, split_sentences
from foundation.shared_utils.video_io import (
    VideoFrames,
    generate_test_pattern_video,
    read_raw_avi,
    write_raw_avi,
)

__all__ = [
    "Stopwatch",
    "utc_now_iso",
    "sha256_file",
    "sha256_text",
    "short_hash",
    "WavData",
    "read_wav",
    "write_wav",
    "generate_sine_wav",
    "VideoFrames",
    "generate_test_pattern_video",
    "read_raw_avi",
    "write_raw_avi",
    "HardwareProfile",
    "probe_hardware",
    "slugify",
    "new_run_id",
    "split_sentences",
]
