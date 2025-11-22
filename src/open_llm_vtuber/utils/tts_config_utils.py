"""
Utility functions for building TTS configuration dictionaries.
"""

from ..config_manager.tts import TTSConfig


def build_tts_config_dict(tts_config: TTSConfig) -> dict:
    """
    Build TTS configuration dictionary from TTSConfig object.

    Args:
        tts_config: TTSConfig instance

    Returns:
        dict: TTS configuration dictionary
    """
    tts_config_dict = {
        "tts_model": tts_config.tts_model,
    }
    # Add model-specific config
    if tts_config.tts_model == "edge_tts" and tts_config.edge_tts:
        tts_config_dict["edge_tts"] = {
            "voice": tts_config.edge_tts.voice,
        }
    elif tts_config.tts_model == "azure_tts" and tts_config.azure_tts:
        tts_config_dict["azure_tts"] = tts_config.azure_tts.model_dump()
    elif tts_config.tts_model == "bark_tts" and tts_config.bark_tts:
        tts_config_dict["bark_tts"] = tts_config.bark_tts.model_dump()
    elif tts_config.tts_model == "melo_tts" and tts_config.melo_tts:
        tts_config_dict["melo_tts"] = tts_config.melo_tts.model_dump()
    elif tts_config.tts_model == "coqui_tts" and tts_config.coqui_tts:
        tts_config_dict["coqui_tts"] = tts_config.coqui_tts.model_dump()
    elif tts_config.tts_model == "x_tts" and tts_config.x_tts:
        tts_config_dict["x_tts"] = tts_config.x_tts.model_dump()
    elif tts_config.tts_model == "gpt_sovits_tts" and tts_config.gpt_sovits_tts:
        tts_config_dict["gpt_sovits_tts"] = tts_config.gpt_sovits_tts.model_dump()
    elif tts_config.tts_model == "sherpa_onnx_tts" and tts_config.sherpa_onnx_tts:
        tts_config_dict["sherpa_onnx_tts"] = tts_config.sherpa_onnx_tts.model_dump()
    elif tts_config.tts_model == "openai_tts" and tts_config.openai_tts:
        tts_config_dict["openai_tts"] = tts_config.openai_tts.model_dump()
    elif tts_config.tts_model == "spark_tts" and tts_config.spark_tts:
        tts_config_dict["spark_tts"] = tts_config.spark_tts.model_dump()
    elif tts_config.tts_model == "minimax_tts" and tts_config.minimax_tts:
        tts_config_dict["minimax_tts"] = tts_config.minimax_tts.model_dump()
    elif tts_config.tts_model == "elevenlabs_tts" and tts_config.elevenlabs_tts:
        tts_config_dict["elevenlabs_tts"] = tts_config.elevenlabs_tts.model_dump()
    elif tts_config.tts_model == "siliconflow_tts" and tts_config.siliconflow_tts:
        tts_config_dict["siliconflow_tts"] = tts_config.siliconflow_tts.model_dump()
    elif tts_config.tts_model == "fish_api_tts" and tts_config.fish_api_tts:
        tts_config_dict["fish_api_tts"] = tts_config.fish_api_tts.model_dump()
    elif tts_config.tts_model == "cosyvoice_tts" and tts_config.cosyvoice_tts:
        tts_config_dict["cosyvoice_tts"] = tts_config.cosyvoice_tts.model_dump()
    elif tts_config.tts_model == "cosyvoice2_tts" and tts_config.cosyvoice2_tts:
        tts_config_dict["cosyvoice2_tts"] = tts_config.cosyvoice2_tts.model_dump()

    return tts_config_dict
