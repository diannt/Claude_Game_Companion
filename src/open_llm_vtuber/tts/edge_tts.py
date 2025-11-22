import sys
import os
import asyncio

import edge_tts
from loguru import logger
from .tts_interface import TTSInterface

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)


# Check out doc at https://github.com/rany2/edge-tts
# Use `edge-tts --list-voices` to list all available voices


class TTSEngine(TTSInterface):
    def __init__(self, voice="en-US-AvaMultilingualNeural"):
        self.voice = voice

        self.temp_audio_file = "temp"
        self.file_extension = "mp3"
        self.new_audio_dir = "cache"

        if not os.path.exists(self.new_audio_dir):
            os.makedirs(self.new_audio_dir)

    async def async_generate_audio(self, text: str, file_name_no_ext=None) -> str:
        """
        Asynchronously generate speech audio file using TTS.
        Uses save_sync() wrapped in asyncio.to_thread() to avoid event loop conflicts.

        Args:
            text: The text to speak
            file_name_no_ext: Name of the file without extension

        Returns:
            str: The path to the generated audio file, or None on error
        """
        file_name = self.generate_cache_file_name(file_name_no_ext, self.file_extension)

        logger.info(
            f"Edge TTS: Generating audio for text: '{text[:50]}...' to file: {file_name}"
        )

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                # Use save_sync() wrapped in asyncio.to_thread() to avoid event loop conflicts
                communicate = edge_tts.Communicate(text, self.voice)

                # Run save_sync in a thread pool to avoid async event loop conflicts
                logger.debug(
                    f"Edge TTS: Attempt {attempt + 1}/{max_retries} - Calling save_sync via asyncio.to_thread"
                )
                await asyncio.to_thread(communicate.save_sync, file_name)

                # Verify file was created
                if not os.path.exists(file_name):
                    logger.error(
                        f"Edge TTS: File was NOT created after save_sync: {file_name}"
                    )
                    if attempt < max_retries - 1:
                        logger.info(f"Edge TTS: Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        continue
                    return None

                # Verify file has content
                file_size = os.path.getsize(file_name)
                if file_size == 0:
                    logger.error(
                        f"Edge TTS: File was created but is empty (0 bytes): {file_name}"
                    )
                    if attempt < max_retries - 1:
                        logger.info(f"Edge TTS: Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        continue
                    return None

                logger.info(
                    f"Edge TTS: Successfully created file {file_name} ({file_size} bytes)"
                )
                return file_name

            except asyncio.TimeoutError:
                logger.error(
                    f"Edge TTS: Timeout error on attempt {attempt + 1}/{max_retries}"
                )
                if attempt < max_retries - 1:
                    logger.info(f"Edge TTS: Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    return None
            except Exception as e:
                logger.error(
                    f"Edge TTS: Error on attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {e}"
                )
                logger.debug(f"Edge TTS: File path attempted: {file_name}")
                import traceback

                logger.debug(f"Edge TTS: Traceback:\n{traceback.format_exc()}")

                if attempt < max_retries - 1:
                    logger.info(f"Edge TTS: Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.critical(
                        f"Edge TTS: All {max_retries} attempts failed. "
                        "It's possible that edge-tts is blocked in your region or there's a network issue."
                    )
                    return None

        return None

    def generate_audio(self, text, file_name_no_ext=None):
        """
        Generate speech audio file using TTS (synchronous fallback).
        This method is used as a fallback or when called directly.

        Args:
            text: The text to speak
            file_name_no_ext: Name of the file without extension

        Returns:
            str: The path to the generated audio file, or None on error
        """
        file_name = self.generate_cache_file_name(file_name_no_ext, self.file_extension)

        logger.info(
            f"Edge TTS (sync): Generating audio for text: '{text[:50]}...' to file: {file_name}"
        )

        try:
            communicate = edge_tts.Communicate(text, self.voice)
            communicate.save_sync(file_name)

            # Verify file was created
            if not os.path.exists(file_name):
                logger.error(f"Edge TTS (sync): File was NOT created: {file_name}")
                return None

            file_size = os.path.getsize(file_name)
            if file_size == 0:
                logger.error(
                    f"Edge TTS (sync): File was created but is empty (0 bytes): {file_name}"
                )
                return None

            logger.info(
                f"Edge TTS (sync): Successfully created file {file_name} ({file_size} bytes)"
            )
        except Exception as e:
            logger.critical(f"\nError: edge-tts sync unable to generate audio: {e}")
            logger.critical(f"Exception type: {type(e).__name__}")
            logger.critical(f"File path attempted: {file_name}")
            logger.critical(
                "It's possible that edge-tts is blocked in your region or there's a network issue."
            )
            import traceback

            logger.critical(f"Full traceback:\n{traceback.format_exc()}")
            return None

        return file_name


# en-US-AvaMultilingualNeural
# en-US-EmmaMultilingualNeural
# en-US-JennyNeural
