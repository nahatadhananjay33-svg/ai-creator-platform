"""Installation specifications for every voice model adapter.

Consumed by ``foundation.model_manager.installer.InstallationManager``.
One venv per model (pins conflict across models). ``supported_on_this_platform``
encodes *known* blockers for native Windows so the installer reports them
honestly instead of burning hours on doomed builds; flip the flag when
running under WSL2/Linux.

Every venv also gets the platform's own runtime deps (pyyaml, psutil,
soundfile) so benchmark runs can execute inside it.
"""
from __future__ import annotations

import sys

from foundation.model_manager.installer import TORCH_CPU_INDEX, InstallSpec
from voice_engine.models.chatterbox_weights import build_prefetch_code as build_chatterbox_prefetch
from voice_engine.models.kokoro_weights import build_prefetch_code as build_kokoro_prefetch

_IS_WINDOWS = sys.platform == "win32"
_PLATFORM_CORE = ("pyyaml", "psutil", "soundfile", "numpy")

#: Kokoro's English G2P (misaki) needs spaCy's ``en_core_web_sm`` model, which
#: is NOT a pip dependency of anything — so English synthesis fails with spaCy
#: [E050] "Can't find model". We install it as a pinned wheel in ``pip_groups``
#: (below) so uv places it in the venv at build time. (B2.1: the old prefetch
#: ran ``spacy download`` at runtime, which shells out to pip and bootstraps it
#: via ``ensurepip`` — but uv venvs ship neither pip nor ensurepip, so that
#: aborted with ModuleNotFoundError. Same lesson as LatentSync: don't touch
#: pip/ensurepip in a prefetch.) The model wheel targets spaCy 3.8.x, which
#: kokoro>=0.9 pulls; bump it in lockstep if kokoro moves to a new spaCy minor.
_SPACY_EN_MODEL = (
    "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
)

#: Chatterbox prefetch. Two runtime downloads happen on first model load that
#: must be pulled at install time so the install is offline-ready (the LatentSync
#: rule — no hidden runtime downloads):
#:  1) spacy-pkuseg's Chinese segmentation model (``spacy_ontonotes``, ~34 MB)
#:     which the multilingual tokenizer fetches from a GitHub release into
#:     ``~/.pkuseg`` the first time ``pkuseg()`` is instantiated (verified in the
#:     B2.2 smoke run). Instantiating it here triggers the same fetch now.
#:  2) every HF weight in the manifest (idempotent, hard-validated).
#: No pip/ensurepip — both use the packages already in the venv.
_CHATTERBOX_PREFETCH = (
    "from spacy_pkuseg import pkuseg; pkuseg()\n"  # downloads spacy_ontonotes if absent
    "print('chatterbox: pkuseg spacy_ontonotes ready')\n"
    + build_chatterbox_prefetch()
)

#: Prefetch: verify the (pip-installed) G2P model loads, then pull every weight
#: straight from the manifest — like the Avatar Engine, so a fresh install is
#: offline-ready and manifest-verified. huggingface_hub only; no pip/ensurepip.
_KOKORO_PREFETCH = (
    "import spacy; spacy.load('en_core_web_sm')\n"  # installed via pip_groups; verify it loads
    "print('kokoro: en_core_web_sm ready')\n"
    + build_kokoro_prefetch()
)

INSTALL_SPECS: dict[str, InstallSpec] = {
    "kokoro": InstallSpec(
        model_id="kokoro",
        pip_groups=(("kokoro>=0.9",) + _PLATFORM_CORE, (_SPACY_EN_MODEL,)),
        verify_imports=("kokoro", "soundfile"),
        # Fetch the English spaCy G2P model so EN audio generates (A3.10).
        prefetch_code=_KOKORO_PREFETCH,
        approx_download_gb=0.6,
    ),
    "f5-tts": InstallSpec(
        model_id="f5-tts",
        # pyarrow pin resolved empirically (Phase A1.5): pyarrow 24.0 wheels crash
        # with an access violation on this Windows/CPU combination; 21.0.0 is the
        # oldest version satisfying datasets>=5.0 and imports cleanly.
        # numba>=0.60 keeps the resolver off numba 0.53 -> llvmlite 0.36, which
        # only builds on Python <3.10 (hit on the F5 benchmark re-install,
        # 2026-07-16; same pin as indic-parler/dia).
        # faster-whisper + indic-transliteration serve the T3 fine-tuning
        # pipeline (transcription + Devanagari romanization) — both wheel-clean
        # on Windows and Linux.
        pip_groups=(
            ("f5-tts", "numba>=0.60") + _PLATFORM_CORE,
            ("pyarrow==21.0.0", "faster-whisper>=1.0", "indic-transliteration>=2.3"),
        ),
        verify_imports=("f5_tts", "soundfile"),
        approx_download_gb=2.0,
    ),
    "xtts-v2": InstallSpec(
        model_id="xtts-v2",
        # transformers pin resolved empirically (Phase A1.5): coqui-tts 0.27 needs
        # >=4.54 (<5.0 removed isin_mps_friendly); torchcodec required by torch 2.9 audio IO.
        pip_groups=(
            ("coqui-tts",) + _PLATFORM_CORE,
            ("transformers==4.57.1", "torchcodec"),
        ),
        verify_imports=("TTS",),
        approx_download_gb=2.5,
        env_vars={"COQUI_TOS_AGREED": "1"},
    ),
    "chatterbox": InstallSpec(
        model_id="chatterbox",
        # torch 2.6.0 is chatterbox-tts 0.1.7's exact pin (its requires_dist:
        # torch==2.6.0 / torchaudio==2.6.0 for python<3.14). Pre-installing it
        # with the right index means the later `chatterbox-tts` pip call finds
        # the pin already satisfied and never downgrades/rebuilds torch. The
        # T4 is sm_75, supported by the cu124 wheels torch 2.6.0 ships (the
        # default PyPI Linux wheel is already cu124, but pinning the index makes
        # the CUDA build explicit — the LatentSync/MuseTalk lesson). GPU-aware
        # (A3.8): cu124 index on a GPU host, CPU index otherwise. chatterbox-tts
        # itself pins numpy<2 / transformers==5.2.0 / diffusers==0.29.0 etc.;
        # one isolated venv, so those pins never collide with other models.
        torch="auto",
        torch_packages=("torch==2.6.0", "torchaudio==2.6.0"),
        torch_cuda_index="https://download.pytorch.org/whl/cu124",
        pip_groups=(("chatterbox-tts",) + _PLATFORM_CORE,),
        verify_imports=("chatterbox", "soundfile"),
        # Prefetch every weight straight from the manifest + the pkuseg
        # segmentation model (offline-ready, hard-validated) instead of relying
        # on the adapter's lazy first-use downloads. No pip/ensurepip.
        prefetch_code=_CHATTERBOX_PREFETCH,
        approx_download_gb=4.5,
        platform_notes="GPU strongly recommended (~6.5 GB VRAM fp16, fits the 15 GB T4); "
        "CPU inference is far from real time. Weights (t3_mtl23ls_v2 + s3gen + ve + "
        "conds + tokenizers, ~3.2 GB) fetched from HF ResembleAI/chatterbox via the manifest.",
    ),
    "indic-parler": InstallSpec(
        model_id="indic-parler",
        # numba/llvmlite pins resolved empirically (Phase A1.5): without them the
        # descript-audiotools -> librosa -> numba chain backtracks to py3.9-era numba.
        pip_groups=(
            ("git+https://github.com/huggingface/parler-tts.git", "numba>=0.60",
             "llvmlite>=0.43", "sentencepiece") + _PLATFORM_CORE,
        ),
        verify_imports=("parler_tts", "transformers"),
        approx_download_gb=4.0,
        platform_notes="WEIGHTS GATED (verified A1.5): ai4bharat/indic-parler-tts requires "
        "accepting terms with a Hugging Face account and setting HF_TOKEN before download.",
    ),
    "styletts2": InstallSpec(
        model_id="styletts2",
        # torch 2.5.1 pin (A1.5): styletts2 loads pickled checkpoints incompatible
        # with the torch>=2.6 weights_only=True default.
        pip_groups=(
            ("styletts2",) + _PLATFORM_CORE,
            ("torch==2.5.1", "torchaudio==2.5.1", "--index-url", TORCH_CPU_INDEX),
        ),
        verify_imports=("styletts2",),
        prefetch_code="import nltk; nltk.download('punkt'); nltk.download('punkt_tab')",
        approx_download_gb=1.5,
        platform_notes="phonemizer requires an espeak-ng binary; may fail on native Windows",
    ),
    "dia": InstallSpec(
        model_id="dia",
        # numba/llvmlite pins: same descript-audiotools backtracking issue as indic-parler.
        pip_groups=(("git+https://github.com/nari-labs/dia.git", "numba>=0.60",
                     "llvmlite>=0.43") + _PLATFORM_CORE,),
        verify_imports=("dia",),
        approx_download_gb=7.0,
        platform_notes="1.6B model; CPU inference is offline-only on this class of machine",
    ),
    "melotts": InstallSpec(
        model_id="melotts",
        # py3.10 venv: MeloTTS pins transformers 4.27 -> tokenizers 0.13.3, which has
        # no cp312 wheel (source build needs Rust). cp310 wheels exist.
        python_version="3.10",
        pip_groups=(("git+https://github.com/myshell-ai/MeloTTS.git",) + _PLATFORM_CORE,),
        verify_imports=("melo",),
        # MeCab needs the full UniDic dictionary (~500 MB) + nltk tagger data.
        prefetch_code=(
            "from unidic.download import download_version; download_version(); "
            "import nltk; nltk.download('averaged_perceptron_tagger_eng'); "
            "nltk.download('cmudict')"
        ),
        approx_download_gb=1.5,
        platform_notes="verified working on native Windows after unidic download (A1.5)",
    ),
    "openvoice-v2": InstallSpec(
        model_id="openvoice-v2",
        python_version="3.10",  # same tokenizers-0.13.3 constraint as melotts
        pip_groups=(
            ("git+https://github.com/myshell-ai/MeloTTS.git",),
            ("git+https://github.com/myshell-ai/OpenVoice.git",) + _PLATFORM_CORE,
        ),
        verify_imports=("melo", "openvoice"),
        approx_download_gb=1.5,
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="BLOCKED on native Windows (verified A1.5): OpenVoice pins "
        "faster-whisper==0.9.0 -> av 10.x, which has no cp310 Windows wheel and fails "
        "to build from source. Use WSL2/Linux. Manual checkpoints_v2 download also required.",
    ),
    "cosyvoice2": InstallSpec(
        model_id="cosyvoice2",
        pip_groups=(),
        verify_imports=("cosyvoice",),
        approx_download_gb=5.0,
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="pynini/WeTextProcessing do not build on native Windows — use WSL2/Linux "
        "(voice_engine/docs/INSTALLATION.md)",
    ),
    "spark-tts": InstallSpec(
        model_id="spark-tts",
        pip_groups=(),
        verify_imports=("sparktts",),
        approx_download_gb=2.0,
        supported_on_this_platform=False,
        platform_notes="source-only install; deprioritized pending license clarification "
        "(voice_engine/research/medium_priority_models.md)",
    ),
}
