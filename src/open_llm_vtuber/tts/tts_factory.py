from typing import Type
from .tts_interface import TTSInterface


class TTSFactory:
    @staticmethod
    def get_tts_engine(engine_type, **kwargs) -> Type[TTSInterface]:
        if engine_type == "azure_tts":
            from .azure_tts import TTSEngine as AzureTTSEngine

            return AzureTTSEngine(
                kwargs.get("api_key"),
                kwargs.get("region"),
                kwargs.get("voice"),
                kwargs.get("pitch"),
                kwargs.get("rate"),
            )
        elif engine_type == "bark_tts":
            from .bark_tts import TTSEngine as BarkTTSEngine

            return BarkTTSEngine(kwargs.get("voice"))
        elif engine_type == "edge_tts":
            from .edge_tts import TTSEngine as EdgeTTSEngine

            return EdgeTTSEngine(kwargs.get("voice"))
        elif engine_type == "pyttsx3_tts":
            from .pyttsx3_tts import TTSEngine as Pyttsx3TTSEngine

            return Pyttsx3TTSEngine()
        elif engine_type == "melo_tts":
            from .melo_tts import TTSEngine as MeloTTSEngine

            return MeloTTSEngine(
                speaker=kwargs.get("speaker"),
                language=kwargs.get("language"),
                device=kwargs.get("device"),
                speed=kwargs.get("speed"),
            )
        elif engine_type == "x_tts":
            from .x_tts import TTSEngine as XTTSEngine

            return XTTSEngine(
                api_url=kwargs.get("api_url"),
                speaker_wav=kwargs.get("speaker_wav"),
                language=kwargs.get("language"),
            )
        elif engine_type == "gpt_sovits_tts":
            from .gpt_sovits_tts import TTSEngine as GSVEngine

            return GSVEngine(
                api_url=kwargs.get("api_url"),
                text_lang=kwargs.get("text_lang"),
                ref_audio_path=kwargs.get("ref_audio_path"),
                prompt_lang=kwargs.get("prompt_lang"),
                prompt_text=kwargs.get("prompt_text"),
                text_split_method=kwargs.get("text_split_method"),
                batch_size=kwargs.get("batch_size"),
                media_type=kwargs.get("media_type"),
                streaming_mode=kwargs.get("streaming_mode"),
            )
        elif engine_type == "coqui_tts":
            from .coqui_tts import TTSEngine as CoquiTTSEngine

            return CoquiTTSEngine(
                model_name=kwargs.get("model_name"),
                speaker_wav=kwargs.get("speaker_wav"),
                language=kwargs.get("language"),
                device=kwargs.get("device"),
            )

        elif engine_type == "fish_api_tts":
            from .fish_api_tts import TTSEngine as FishAPITTSEngine

            return FishAPITTSEngine(
                api_key=kwargs.get("api_key"),
                reference_id=kwargs.get("reference_id"),
                latency=kwargs.get("latency"),
                base_url=kwargs.get("base_url"),
            )
        elif engine_type == "sherpa_onnx_tts":
            from .sherpa_onnx_tts import TTSEngine as SherpaOnnxTTSEngine

            return SherpaOnnxTTSEngine(**kwargs)
        elif engine_type == "openai_tts":
            from .openai_tts import TTSEngine as OpenAITTSEngine

            # Pass relevant config options, allowing defaults in openai_tts.py if not provided
            return OpenAITTSEngine(
                model=kwargs.get("model"),  # Will use default "kokoro" if not in kwargs
                voice=kwargs.get(
                    "voice"
                ),  # Will use default "af_sky+af_bella" if not in kwargs
                api_key=kwargs.get(
                    "api_key"
                ),  # Will use default "not-needed" if not in kwargs
                base_url=kwargs.get(
                    "base_url"
                ),  # Will use default "http://localhost:8880/v1" if not in kwargs
                file_extension=kwargs.get(
                    "file_extension"
                ),  # Will use default "mp3" if not in kwargs
            )

        elif engine_type == "elevenlabs_tts":
            from .elevenlabs_tts import TTSEngine as ElevenLabsTTSEngine

            return ElevenLabsTTSEngine(
                api_key=kwargs.get("api_key"),
                voice_id=kwargs.get("voice_id"),
                model_id=kwargs.get("model_id", "eleven_multilingual_v2"),
                output_format=kwargs.get("output_format", "mp3_44100_128"),
                stability=kwargs.get("stability", 0.5),
                similarity_boost=kwargs.get("similarity_boost", 0.5),
                style=kwargs.get("style", 0.0),
                use_speaker_boost=kwargs.get("use_speaker_boost", True),
            )
        elif engine_type == "cartesia_tts":
            from .cartesia_tts import TTSEngine as CartesiaTTSEngine

            return CartesiaTTSEngine(
                api_key=kwargs.get("api_key"),
                voice_id=kwargs.get("voice_id", "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"),
                model_id=kwargs.get("model_id", "sonic-3"),
                output_format=kwargs.get("output_format", "wav"),
                language=kwargs.get("language", "en"),
                emotion=kwargs.get("emotion", "neutral"),
                volume=kwargs.get("volume", 1.0),
                speed=kwargs.get("speed", 1.0),
            )
        elif engine_type == "piper_tts":
            from .piper_tts import TTSEngine as PiperTTSEngine

            return PiperTTSEngine(
                model_path=kwargs.get("model_path"),
                speaker_id=kwargs.get("speaker_id"),
                length_scale=kwargs.get("length_scale"),
                noise_scale=kwargs.get("noise_scale"),
                noise_w=kwargs.get("noise_w"),
                volume=kwargs.get("volume"),
                normalize_audio=kwargs.get("normalize_audio"),
                use_cuda=kwargs.get("use_cuda"),
            )
        else:
            raise ValueError(f"Unknown TTS engine type: {engine_type}")


