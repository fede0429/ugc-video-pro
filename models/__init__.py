"""
models/__init__.py
==================
Model adapter factory.

Maps model keys to their adapter classes.
Priority: KIE.AI adapters (unified gateway) > Direct API adapters (legacy).
"""

from models.base import VideoModelAdapter, get_model_max_duration
from utils.logger import get_logger

logger = get_logger(__name__)


def get_model_adapter(model: str, config: dict) -> VideoModelAdapter:
    """
    Get a video model adapter instance.

    Priority:
        1. KIE.AI unified adapters (if KIE API key is configured)
        2. Legacy direct API adapters (fallback)

    Args:
        model: Model key (e.g. "veo_31_fast", "seedance_15", "sora_2")
        config: Application configuration dict

    Returns:
        VideoModelAdapter instance
    """
    kie_key = config.get("kie", {}).get("api_key", "")

    # ── KIE.AI models (preferred) ────────────────────────────────────
    from models.kie_video import KIE_VIDEO_MODELS

    if model in KIE_VIDEO_MODELS and kie_key:
        from models.kie_video import KieVideoAdapter
        logger.info(f"Using KIE.AI adapter for model: {model}")
        return KieVideoAdapter(config, model_variant=model)

    # ── Legacy direct API adapters (fallback) ────────────────────────
    # Veo (direct Google API)
    if model in ("veo_3", "veo_3_pro", "veo_31_pro"):
        google_key = config.get("models", {}).get("google", {}).get("api_key", "")
        if google_key:
            from models.veo import VeoAdapter
            logger.info(f"Using legacy Veo adapter for model: {model}")
            return VeoAdapter(config, model_variant=model)

    # Sora (direct OpenAI API)
    if model in ("sora_2", "sora_2_pro"):
        openai_key = config.get("models", {}).get("openai", {}).get("api_key", "")
        if openai_key:
            from models.sora import SoraAdapter
            logger.info(f"Using legacy Sora adapter for model: {model}")
            return SoraAdapter(config, model_variant=model)

    # Seedance (direct ByteDance API)
    if model in ("seedance_2",):
        seedance_key = config.get("models", {}).get("seedance", {}).get("api_key", "")
        if seedance_key and seedance_key != "placeholder":
            from models.seedance import SeedanceAdapter
            logger.info(f"Using legacy Seedance adapter for model: {model}")
            return SeedanceAdapter(config, model_variant=model)

    # ── Default to KIE.AI if key exists ────────────────────────────
    if kie_key:
        # Try mapping legacy model names to KIE model keys
        legacy_to_kie = {
            "veo_3": "veo_31_fast",
            "veo_3_pro": "veo_31_quality",
            "veo_31_pro": "veo_31_quality",
            "sora_2_pro": "sora_2",
            "seedance_2": "seedance_15",  # fallback to 1.5 until 2.0 launches
        }
        kie_model = legacy_to_kie.get(model)
        if kie_model and kie_model in KIE_VIDEO_MODELS:
            from models.kie_video import KieVideoAdapter
            logger.info(
                f"Mapped legacy model '{model}' to KIE model '{kie_model}'"
            )
            return KieVideoAdapter(config, model_variant=kie_model)

    raise ValueError(
        f"No adapter available for model '{model}'. "
        f"Configure KIE_API_KEY in .env for unified access, "
        f"or set individual API keys for direct access."
    )
