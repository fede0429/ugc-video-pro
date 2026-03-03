"""
models/__init__.py
==================
Model adapter registry — maps model keys to adapter classes.
"""

from models.base import VideoModelAdapter, get_model_max_duration
from models.sora import SoraAdapter
from models.veo import VeoAdapter
from models.seedance import SeedanceAdapter


def get_model_adapter(model_key: str, config: dict) -> VideoModelAdapter:
    """Factory function: return the correct adapter for a model key.
    
    Args:
        model_key: One of: sora_2, sora_2_pro, seedance_2, veo_3, veo_3_pro, veo_31_pro
        config: Application configuration dict
    
    Returns:
        Configured VideoModelAdapter instance
    
    Raises:
        ValueError: If model_key is not recognized
    """
    adapter_map = {
        "sora_2": lambda: SoraAdapter(config, model_variant="sora_2"),
        "sora_2_pro": lambda: SoraAdapter(config, model_variant="sora_2_pro"),
        "seedance_2": lambda: SeedanceAdapter(config, model_variant="seedance_2"),
        "veo_3": lambda: VeoAdapter(config, model_variant="veo_3"),
        "veo_3_pro": lambda: VeoAdapter(config, model_variant="veo_3_pro"),
        "veo_31_pro": lambda: VeoAdapter(config, model_variant="veo_31_pro"),
    }

    if model_key not in adapter_map:
        raise ValueError(
            f"Unknown model key: '{model_key}'. "
            f"Valid options: {list(adapter_map.keys())}"
        )

    return adapter_map[model_key]()


__all__ = [
    "VideoModelAdapter",
    "SoraAdapter",
    "VeoAdapter",
    "SeedanceAdapter",
    "get_model_adapter",
    "get_model_max_duration",
]
