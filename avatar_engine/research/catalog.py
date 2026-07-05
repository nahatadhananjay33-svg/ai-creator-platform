"""Candidate avatar model catalog (Phase A3 research, observed 2026-07-04).

Facts verified against upstream repositories and license files on the
observation date recorded in each profile. VRAM figures are practical
inference envelopes reported by maintainers/community, not marketing
numbers. Update ``observed_on`` whenever a profile is re-verified.

Sources per model are recorded in ``avatar_engine/research/*.md``.
"""
from __future__ import annotations

from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec

from avatar_engine.research.schema import (
    AvatarModelProfile,
    AvatarTask,
    InstallComplexity,
    MaintenanceStatus,
    RepositoryActivity,
    ResearchRatings,
)

_OBSERVED = "2026-07-04"


def _spec(
    model_id: str,
    display_name: str,
    version: str,
    repo_url: str,
    weights_source: str,
    license_info: LicenseInfo,
    hardware: HardwareRequirements,
    parameters_millions: float | None = None,
    tags: tuple[str, ...] = (),
) -> ModelSpec:
    return ModelSpec(
        model_id=model_id,
        display_name=display_name,
        family="avatar",
        version=version,
        repo_url=repo_url,
        weights_source=weights_source,
        license=license_info,
        hardware=hardware,
        parameters_millions=parameters_millions,
        tags=tags,
    )


CANDIDATE_PROFILES: dict[str, AvatarModelProfile] = {
    # ------------------------------------------------------------ lip-sync (video dubbing)
    "musetalk": AvatarModelProfile(
        spec=_spec(
            "musetalk", "MuseTalk", "1.5",
            "https://github.com/TMElyralab/MuseTalk",
            "TMElyralab/MuseTalk",
            LicenseInfo("MIT", "MIT", True,
                        "Tencent Music; README explicitly allows commercial use of the "
                        "trained models."),
            HardwareRequirements(6.0, 8.0, 16.0, False, 10.0,
                                 "30 fps real-time on a V100; fp16 fits in ~6 GB"),
            tags=("real-time", "lip-sync", "dubbing"),
        ),
        task=AvatarTask.VIDEO_LIP_SYNC,
        activity=RepositoryActivity(6118, "2025-09-26", MaintenanceStatus.SLOWING, _OBSERVED,
                                    "1.5 release landed 2025; commits tapering since"),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2", "windows"),
        dependencies=("torch", "diffusers", "mmcv/mmpose", "ffmpeg", "whisper"),
        ratings=ResearchRatings(lip_sync=5, realism=4, identity_consistency=5,
                                expressiveness=2, motion_naturalness=3),
        strengths=(
            "True real-time inference (30 fps+ on V100) — enables interactive avatars",
            "Identity preserved perfectly outside the mouth region (inpainting approach)",
            "MIT license incl. weights, explicit commercial permission",
            "Works on any existing video — pairs naturally with a motion source",
        ),
        weaknesses=(
            "Only edits the mouth: needs a driving/template video for everything else",
            "256x256 face crop limits quality on tight close-ups",
            "mmcv/mmpose dependency chain is painful to install, esp. on Windows",
        ),
        production_candidate=True,
    ),
    "latentsync": AvatarModelProfile(
        spec=_spec(
            "latentsync", "LatentSync", "1.6",
            "https://github.com/bytedance/LatentSync",
            "ByteDance/LatentSync-1.6",
            LicenseInfo("Apache-2.0", "OpenRAIL++", True,
                        "Weights under OpenRAIL++: commercial use allowed subject to "
                        "responsible-AI use restrictions (no deception/impersonation)."),
            HardwareRequirements(6.5, 8.0, 16.0, False, 12.0,
                                 "6.5 GB VRAM inference; 512x512 training resolution in 1.6"),
            tags=("lip-sync", "diffusion", "dubbing"),
        ),
        task=AvatarTask.VIDEO_LIP_SYNC,
        activity=RepositoryActivity(5835, "2025-06-20", MaintenanceStatus.SLOWING, _OBSERVED),
        install_complexity=InstallComplexity.MODERATE,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "diffusers", "ffmpeg", "insightface(detection)"),
        ratings=ResearchRatings(lip_sync=5, realism=4, identity_consistency=4,
                                expressiveness=2, motion_naturalness=3),
        strengths=(
            "State-of-the-art lip-sync accuracy (end-to-end audio-conditioned diffusion)",
            "1.6 fixed the 1.5 blurriness by moving to 512x512 training",
            "Modest inference VRAM (6.5 GB) for a diffusion approach",
        ),
        weaknesses=(
            "Slower than MuseTalk — offline dubbing, not real-time",
            "Mouth-region editor only; needs existing footage",
            "OpenRAIL++ use restrictions require a compliance check for avatar products",
        ),
        production_candidate=True,
    ),
    "wav2lip": AvatarModelProfile(
        spec=_spec(
            "wav2lip", "Wav2Lip", "1.0 (2020)",
            "https://github.com/Rudrabha/Wav2Lip",
            "manual download (IIIT-H)",
            LicenseInfo("custom (research-only)", "research-only", False,
                        "README restricts to personal/research/non-commercial use; "
                        "commercial licensing requires contacting Sync Labs."),
            HardwareRequirements(2.0, 4.0, 8.0, True, 1.0, "runs on CPU, slowly"),
            tags=("lip-sync", "legacy", "baseline"),
        ),
        task=AvatarTask.VIDEO_LIP_SYNC,
        activity=RepositoryActivity(13083, "2025-06-22", MaintenanceStatus.STALE, _OBSERVED,
                                    "occasional README-level commits only"),
        install_complexity=InstallComplexity.LOW,
        os_support=("linux", "windows", "wsl2", "macos"),
        dependencies=("torch", "opencv", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=3, realism=2, identity_consistency=4,
                                expressiveness=1, motion_naturalness=2),
        strengths=(
            "Trivial to install; historical baseline every paper compares against",
            "Tiny model, CPU-capable",
        ),
        weaknesses=(
            "2020-era visual quality: blurry 96x96 mouth region",
            "Research-only license — cannot ship",
        ),
        production_candidate=False,
        excluded_reason="Non-commercial license and obsolete visual quality; useful only "
                        "as a benchmark baseline on a research machine.",
    ),
    # ------------------------------------------------------------ portrait reenactment
    "liveportrait": AvatarModelProfile(
        spec=_spec(
            "liveportrait", "LivePortrait", "2024-07 (maintained)",
            "https://github.com/KwaiVGI/LivePortrait",
            "KwaiVGI/LivePortrait",
            LicenseInfo("MIT", "MIT (but InsightFace dep is non-commercial)", False,
                        "Code+weights MIT, but the bundled InsightFace buffalo_l detection "
                        "models are research-only. Commercial use requires replacing the "
                        "InsightFace components (e.g. MediaPipe/YOLO-face) — feasible, "
                        "documented in issue #193, but engineering work we must budget."),
            HardwareRequirements(3.0, 6.0, 8.0, False, 2.0,
                                 "~12.8 ms/frame on RTX 4090; low VRAM footprint"),
            tags=("reenactment", "real-time", "stylized-support"),
        ),
        task=AvatarTask.PORTRAIT_REENACTMENT,
        activity=RepositoryActivity(18680, "2026-06-01", MaintenanceStatus.ACTIVE, _OBSERVED,
                                    "repo moved to KlingAIResearch org; most-starred "
                                    "portrait animation project"),
        install_complexity=InstallComplexity.MODERATE,
        os_support=("linux", "windows", "wsl2", "macos"),
        dependencies=("torch", "onnxruntime", "insightface", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=3, realism=5, identity_consistency=5,
                                expressiveness=5, motion_naturalness=5),
        strengths=(
            "Best-in-class expression/pose transfer with excellent identity retention",
            "Near real-time on midrange GPUs; official Windows one-click package",
            "Very active, huge community (ComfyUI ecosystem)",
            "Stitching/retargeting controls (eyes, lips) for editorial use",
        ),
        weaknesses=(
            "Video-driven, not audio-driven: needs a driving performance video or an "
            "audio-to-motion front-end to make talking avatars",
            "InsightFace dependency blocks commercial use until replaced",
        ),
        production_candidate=True,
    ),
    # ------------------------------------------------------------ audio-driven heads
    "sadtalker": AvatarModelProfile(
        spec=_spec(
            "sadtalker", "SadTalker", "0.0.2 (CVPR 2023)",
            "https://github.com/OpenTalker/SadTalker",
            "vinthony/SadTalker (HF)",
            LicenseInfo("Apache-2.0", "Apache-2.0", True,
                        "Relicensed to Apache-2.0; earlier non-commercial README wording "
                        "was retracted by the maintainers."),
            HardwareRequirements(4.0, 8.0, 8.0, True, 3.0,
                                 "CPU inference possible but minutes-per-second slow"),
            tags=("talking-head", "legacy", "baseline"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(13937, "2024-06-26", MaintenanceStatus.STALE, _OBSERVED,
                                    "no meaningful commits since mid-2024"),
        install_complexity=InstallComplexity.LOW,
        os_support=("linux", "windows", "wsl2", "macos"),
        dependencies=("torch", "face-alignment", "ffmpeg", "gfpgan(optional)"),
        ratings=ResearchRatings(lip_sync=3, realism=3, identity_consistency=4,
                                expressiveness=2, motion_naturalness=2),
        strengths=(
            "Easiest full image->talking-head pipeline to stand up; lowest hardware bar",
            "Permissive license, enormous install base and documentation",
        ),
        weaknesses=(
            "Unmaintained; quality clearly behind 2024+ diffusion models",
            "Stiff head motion, waxy faces, visible jaw artifacts",
        ),
        production_candidate=True,  # as low-end fallback / baseline only
    ),
    "echomimic-v2": AvatarModelProfile(
        spec=_spec(
            "echomimic-v2", "EchoMimicV2", "CVPR 2025",
            "https://github.com/antgroup/echomimic_v2",
            "BadToBest/EchoMimicV2",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Ant Group"),
            HardwareRequirements(16.0, 24.0, 32.0, False, 15.0,
                                 "community reports 8 GB cards hang; 16 GB practical floor"),
            tags=("half-body", "gestures", "diffusion"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(4607, "2026-02-23", MaintenanceStatus.ACTIVE, _OBSERVED),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2", "windows"),
        dependencies=("torch", "diffusers", "ffmpeg", "sd-vae"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Half-body animation with hand gestures — richer than head-only models",
            "Apache-2.0 end to end; active Ant Group backing",
            "Simplified conditioning vs v1 (fewer control inputs to wrangle)",
        ),
        weaknesses=(
            "16 GB+ VRAM practical requirement",
            "Minutes of generation per clip — offline only",
            "English + Mandarin driving audio officially; other languages untested",
        ),
        production_candidate=True,
    ),
    "echomimic-v3": AvatarModelProfile(
        spec=_spec(
            "echomimic-v3", "EchoMimicV3", "AAAI 2026",
            "https://github.com/antgroup/echomimic_v3",
            "BadToBest/EchoMimicV3",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Ant Group"),
            HardwareRequirements(6.5, 12.0, 32.0, False, 8.0,
                                 "768x512 in 6.5 GB, 768x768 in 12 GB (flash variant, 8 steps)"),
            parameters_millions=1300,
            tags=("multi-task", "half-body", "efficient"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(968, "2026-03-18", MaintenanceStatus.ACTIVE, _OBSERVED),
        install_complexity=InstallComplexity.MODERATE,
        os_support=("linux", "wsl2", "windows"),
        dependencies=("torch", "diffusers", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Best quality-per-GB in the family: 1.3B params, 12 GB covers 768x768",
            "Unified multi-modal/multi-task: talking head AND talking body in one model",
            "Fresh (AAAI 2026), actively developed, Apache-2.0",
        ),
        weaknesses=(
            "Young project — smaller community and fewer battle scars than v2",
            "Still diffusion-offline; not real-time",
        ),
        production_candidate=True,
    ),
    "ditto": AvatarModelProfile(
        spec=_spec(
            "ditto", "Ditto TalkingHead", "ACM MM 2025",
            "https://github.com/antgroup/ditto-talkinghead",
            "digital-avatar/ditto-talkinghead",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Ant Group"),
            HardwareRequirements(6.0, 12.0, 16.0, False, 6.0,
                                 "real-time with TensorRT engines; PyTorch fallback slower"),
            tags=("real-time", "streaming", "talking-head"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(826, "2025-11-12", MaintenanceStatus.SLOWING, _OBSERVED),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "tensorrt", "ffmpeg", "onnx"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=3, motion_naturalness=3),
        strengths=(
            "Real-time streaming audio->talking-head — the interactive-avatar niche",
            "Motion-space diffusion keeps identity stable; controllable style",
            "Apache-2.0 end to end",
        ),
        weaknesses=(
            "TensorRT engine build makes installs GPU/driver-specific and brittle",
            "Face-region animation only; torso/background static",
            "Small community relative to the majors",
        ),
        production_candidate=True,
    ),
    "hallo2": AvatarModelProfile(
        spec=_spec(
            "hallo2", "Hallo2", "ICLR 2025",
            "https://github.com/fudan-generative-vision/hallo2",
            "fudan-generative-ai/hallo2",
            LicenseInfo("MIT", "MIT", True,
                        "MIT, but pipeline pulls SD1.5-era components — verify each "
                        "checkpoint's terms at packaging time."),
            HardwareRequirements(16.0, 24.0, 32.0, False, 20.0,
                                 "long-duration 4K mode is VRAM- and time-hungry"),
            tags=("talking-head", "long-duration", "4k"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(3716, "2025-02-27", MaintenanceStatus.STALE, _OBSERVED,
                                    "team's attention moved to Hallo3/4"),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "diffusers", "insightface", "audio-separator", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Hour-scale generation with identity drift countermeasures",
            "High-resolution (up to 4K) portrait output",
            "MIT licensed",
        ),
        weaknesses=(
            "Research-grade codebase; heavy preprocessing chain",
            "Slow generation; high VRAM floor",
            "Effectively in maintenance freeze",
        ),
        production_candidate=True,
    ),
    "hallo3": AvatarModelProfile(
        spec=_spec(
            "hallo3", "Hallo3", "CVPR 2025",
            "https://github.com/fudan-generative-vision/hallo3",
            "fudan-generative-ai/hallo3",
            LicenseInfo("MIT", "MIT", True, "built on CogVideoX DiT"),
            HardwareRequirements(24.0, 40.0, 64.0, False, 40.0,
                                 "video DiT: datacenter-class GPUs for sensible latency"),
            tags=("talking-head", "dit", "dynamic-scenes"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(1391, "2025-03-13", MaintenanceStatus.STALE, _OBSERVED),
        install_complexity=InstallComplexity.SEVERE,
        os_support=("linux",),
        dependencies=("torch", "CogVideoX stack", "flash-attn", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=5, identity_consistency=4,
                                expressiveness=5, motion_naturalness=5),
        strengths=(
            "Handles dynamic backgrounds and non-frontal poses that break UNet models",
            "Top-tier realism from the video-DiT prior",
        ),
        weaknesses=(
            "40 GB-class VRAM recommendation prices out our deployment targets",
            "Very slow; research scaffolding; stale repo",
        ),
        production_candidate=False,
        excluded_reason="Hardware envelope (24-40 GB VRAM) and generation latency are "
                        "incompatible with platform serving economics in 2026.",
    ),
    "memo": AvatarModelProfile(
        spec=_spec(
            "memo", "MEMO", "CVPR 2025",
            "https://github.com/memoavatar/memo",
            "memoavatar/memo",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Skywork/NUS"),
            HardwareRequirements(16.0, 24.0, 32.0, False, 20.0),
            tags=("talking-head", "emotion-aware", "long-form"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(1068, "2025-08-06", MaintenanceStatus.SLOWING, _OBSERVED),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "diffusers", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Memory-guided temporal module targets long-video identity drift",
            "Emotion-aware audio conditioning",
            "Apache-2.0",
        ),
        weaknesses=(
            "Heavy VRAM and slow generation",
            "Modest community; release cadence slowed after initial drop",
        ),
        production_candidate=True,
    ),
    "sonic": AvatarModelProfile(
        spec=_spec(
            "sonic", "Sonic", "CVPR 2025",
            "https://github.com/jixiaozhong/Sonic",
            "LeonJoe13/Sonic",
            LicenseInfo("CC-BY-NC-SA-4.0", "CC-BY-NC-SA-4.0", False,
                        "explicitly non-commercial (Tencent/Zhejiang)"),
            HardwareRequirements(10.0, 16.0, 32.0, False, 15.0),
            tags=("talking-head", "global-motion"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(3263, "2026-01-08", MaintenanceStatus.ACTIVE, _OBSERVED),
        install_complexity=InstallComplexity.MODERATE,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "svd", "whisper", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=5, realism=5, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Excellent perceptual quality and audio-motion coupling",
            "Strong community adoption despite the license",
        ),
        weaknesses=("Non-commercial license — unusable for the platform",),
        production_candidate=False,
        excluded_reason="CC-BY-NC-SA-4.0 forbids commercial use.",
    ),
    "float": AvatarModelProfile(
        spec=_spec(
            "float", "FLOAT", "2024-12 (DeepBrain AI)",
            "https://github.com/deepbrainai-research/float",
            "deepbrainai-research/float",
            LicenseInfo("CC-BY-NC-ND-4.0", "CC-BY-NC-ND-4.0", False,
                        "research-only; commercial licensing via DeepBrain sales"),
            HardwareRequirements(8.0, 12.0, 16.0, False, 5.0,
                                 "flow-matching: fast generation for its quality class"),
            tags=("talking-head", "flow-matching", "emotion"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_HEAD,
        activity=RepositoryActivity(483, "2025-11-10", MaintenanceStatus.SLOWING, _OBSERVED),
        install_complexity=InstallComplexity.MODERATE,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=("Fast flow-matching sampling; emotion control",),
        weaknesses=("Non-commercial, no-derivatives license — unusable for the platform",),
        production_candidate=False,
        excluded_reason="CC-BY-NC-ND-4.0 forbids commercial use and derivative works.",
    ),
    # ------------------------------------------------------------ video-model generation
    "infinitetalk": AvatarModelProfile(
        spec=_spec(
            "infinitetalk", "InfiniteTalk", "2025-08 (MeiGen)",
            "https://github.com/MeiGen-AI/InfiniteTalk",
            "MeiGen-AI/InfiniteTalk",
            LicenseInfo("Apache-2.0", "Apache-2.0", True,
                        "built on Wan2.1-I2V-14B (also Apache-2.0)"),
            HardwareRequirements(12.0, 24.0, 64.0, False, 60.0,
                                 "480p fits a 4090 (quantized lower); 720p needs >24 GB"),
            parameters_millions=14000,
            tags=("unlimited-length", "dubbing", "image-to-video", "wan"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(7349, "2026-05-22", MaintenanceStatus.ACTIVE, _OBSERVED,
                                    "fastest-growing talking-video repo of the past year"),
        install_complexity=InstallComplexity.SEVERE,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "Wan2.1 stack", "flash-attn", "wav2vec2", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=5, identity_consistency=4,
                                expressiveness=5, motion_naturalness=5),
        strengths=(
            "Unlimited-length generation with stable identity (sparse-frame dubbing)",
            "Both image->video and video->video modes; full-body motion follows audio",
            "Apache-2.0 on a 14B video prior — best open realism ceiling",
            "Very active development and ComfyUI ecosystem support",
        ),
        weaknesses=(
            "14B model: heavy downloads (~60 GB), datacenter-adjacent hardware for 720p",
            "Minutes per clip; flash-attn/Wan stack is Linux-first and fragile",
        ),
        production_candidate=True,
    ),
    "fantasy-talking": AvatarModelProfile(
        spec=_spec(
            "fantasy-talking", "FantasyTalking", "2025-04 (AMAP)",
            "https://github.com/Fantasy-AMAP/fantasy-talking",
            "acvlab/FantasyTalking",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Alibaba AMAP; Wan2.1-based"),
            HardwareRequirements(5.0, 24.0, 32.0, False, 40.0,
                                 "low-VRAM offload mode reaches ~5 GB at heavy speed cost"),
            parameters_millions=14000,
            tags=("wan", "image-to-video", "body-motion"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(1623, "2026-01-26", MaintenanceStatus.ACTIVE, _OBSERVED),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "Wan2.1 stack", "wav2vec2", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Wan-quality realism with documented low-VRAM offload paths",
            "Apache-2.0",
        ),
        weaknesses=(
            "Same Wan-stack install burden as InfiniteTalk with a smaller community",
            "Slow generation",
        ),
        production_candidate=True,
    ),
    "omniavatar": AvatarModelProfile(
        spec=_spec(
            "omniavatar", "OmniAvatar", "2025-06 (Alibaba/ZJU)",
            "https://github.com/Omni-Avatar/OmniAvatar",
            "OmniAvatar/OmniAvatar-14B",
            LicenseInfo("Apache-2.0", "Apache-2.0", True, "Wan2.1-based; 1.3B and 14B variants"),
            HardwareRequirements(8.0, 24.0, 32.0, False, 40.0,
                                 "1.3B variant lowers the floor; 14B for quality"),
            parameters_millions=14000,
            tags=("wan", "full-body", "prompt-controllable"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(1842, "2025-08-06", MaintenanceStatus.SLOWING, _OBSERVED),
        install_complexity=InstallComplexity.HIGH,
        os_support=("linux", "wsl2"),
        dependencies=("torch", "Wan2.1 stack", "wav2vec2", "ffmpeg"),
        ratings=ResearchRatings(lip_sync=4, realism=4, identity_consistency=4,
                                expressiveness=4, motion_naturalness=4),
        strengths=(
            "Prompt-controllable full-body avatar behavior",
            "1.3B variant offers a lighter quality/cost point",
        ),
        weaknesses=(
            "Human evaluators rate its naturalness below its objective scores "
            "(over-optimized lip region)",
            "Momentum shifted to InfiniteTalk within the same ecosystem",
        ),
        production_candidate=True,
    ),
    "omnihuman": AvatarModelProfile(
        spec=_spec(
            "omnihuman", "OmniHuman-1/1.5", "closed",
            "https://omnihuman-lab.github.io/",
            "not released",
            LicenseInfo("closed", "not released", False,
                        "ByteDance commercial API only (Dreamina/BytePlus)"),
            HardwareRequirements(None, None, 0.0, False, 0.0, "SaaS only"),
            tags=("closed-source", "reference-quality"),
        ),
        task=AvatarTask.AUDIO_DRIVEN_BODY,
        activity=RepositoryActivity(0, "n/a", MaintenanceStatus.ACTIVE, _OBSERVED,
                                    "active as a product, closed as a model"),
        install_complexity=InstallComplexity.SEVERE,
        os_support=(),
        dependencies=(),
        ratings=ResearchRatings(lip_sync=5, realism=5, identity_consistency=5,
                                expressiveness=5, motion_naturalness=5),
        strengths=("Industry-reference quality bar for audio-driven full-body animation",),
        weaknesses=("Weights never released; API pricing and ToS control the product",),
        production_candidate=False,
        excluded_reason="Not open-source: weights unavailable as of 2026-07; tracked only "
                        "as the quality reference the open models chase.",
    ),
}


def all_profiles() -> list[AvatarModelProfile]:
    """Every researched model, sorted by model_id."""
    return sorted(CANDIDATE_PROFILES.values(), key=lambda p: p.model_id)


def get_profile(model_id: str) -> AvatarModelProfile:
    try:
        return CANDIDATE_PROFILES[model_id]
    except KeyError:
        raise KeyError(
            f"Unknown avatar model {model_id!r}; known: {sorted(CANDIDATE_PROFILES)}"
        ) from None


def production_candidates() -> list[AvatarModelProfile]:
    """Models that can realistically serve production workloads."""
    return [p for p in all_profiles() if p.production_candidate]


def commercial_ready_profiles() -> list[AvatarModelProfile]:
    """Models whose weights we may deploy commercially today, as-shipped."""
    return [p for p in all_profiles() if p.spec.license.commercial_use]


def profiles_by_task(task: AvatarTask) -> list[AvatarModelProfile]:
    return [p for p in all_profiles() if p.task is task]
