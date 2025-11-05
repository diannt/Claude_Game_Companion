import base64
import os
import shutil
from pathlib import Path
from pydub import AudioSegment
from pydub.utils import make_chunks
from loguru import logger
from ..agent.output_types import Actions
from ..agent.output_types import DisplayText

# Configure FFmpeg paths for pydub if available
_ffmpeg_configured = False


def _configure_ffmpeg():
    """Configure FFmpeg paths for pydub if not already configured."""
    global _ffmpeg_configured
    if _ffmpeg_configured:
        return

    import subprocess
    import platform

    ffmpeg_path = None
    ffprobe_path = None

    # Method 1: Try shutil.which (standard method)
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    # Method 2: Try using subprocess with shell=True on Windows
    if not ffmpeg_path and platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["where", "ffmpeg"],
                capture_output=True,
                text=True,
                shell=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                ffmpeg_path = result.stdout.strip().split("\n")[0]
                logger.debug(f"Found FFmpeg via 'where' command: {ffmpeg_path}")
        except Exception:
            pass

    if not ffprobe_path and platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["where", "ffprobe"],
                capture_output=True,
                text=True,
                shell=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                ffprobe_path = result.stdout.strip().split("\n")[0]
                logger.debug(f"Found FFprobe via 'where' command: {ffprobe_path}")
        except Exception:
            pass

    # Method 3: Try WSL if available
    if not ffmpeg_path:
        try:
            result = subprocess.run(
                ["wsl", "which", "ffmpeg"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                wsl_path = result.stdout.strip()
                # Use wsl to call ffmpeg
                ffmpeg_path = f"wsl {wsl_path}"
                logger.debug(f"Found FFmpeg in WSL: {wsl_path}")
        except Exception:
            pass

    if not ffprobe_path:
        try:
            result = subprocess.run(
                ["wsl", "which", "ffprobe"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                wsl_path = result.stdout.strip()
                # Use wsl to call ffprobe
                ffprobe_path = f"wsl {wsl_path}"
                logger.debug(f"Found FFprobe in WSL: {wsl_path}")
        except Exception:
            pass

    # Method 4: Try common Windows locations
    if not ffmpeg_path:
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"C:\tools\ffmpeg\bin\ffmpeg.exe",
            Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        for path in common_paths:
            path_obj = Path(path) if isinstance(path, Path) else Path(path)
            if path_obj.exists():
                ffmpeg_path = str(path_obj)
                break

    if not ffprobe_path:
        common_paths = [
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
            r"C:\tools\ffmpeg\bin\ffprobe.exe",
            Path.home() / "ffmpeg" / "bin" / "ffprobe.exe",
        ]
        for path in common_paths:
            path_obj = Path(path) if isinstance(path, Path) else Path(path)
            if path_obj.exists():
                ffprobe_path = str(path_obj)
                break

    # Configure pydub if FFmpeg is found
    global _wsl_ffmpeg, _wsl_ffprobe
    if ffmpeg_path:
        # If FFmpeg is in WSL, we need to handle it specially
        if ffmpeg_path.startswith("wsl "):
            # Don't set converter directly - we'll handle WSL calls manually
            logger.info(f"FFmpeg found in WSL: {ffmpeg_path}")
            # Store WSL path for manual conversion
            _wsl_ffmpeg = ffmpeg_path.replace("wsl ", "")
            _wsl_ffprobe = (
                ffprobe_path.replace("wsl ", "")
                if ffprobe_path and ffprobe_path.startswith("wsl ")
                else None
            )
        else:
            AudioSegment.converter = ffmpeg_path
            logger.info(f"Configured pydub FFmpeg: {ffmpeg_path}")

    if ffprobe_path:
        if not ffprobe_path.startswith("wsl "):
            # Set FFprobe via pydub's utils
            import pydub.utils

            pydub.utils.ffprobe = ffprobe_path
            logger.info(f"Configured pydub FFprobe: {ffprobe_path}")

    if ffmpeg_path and ffprobe_path:
        _ffmpeg_configured = True
        if ffmpeg_path.startswith("wsl "):
            logger.info("FFmpeg configured for audio processing (WSL mode)")
        else:
            logger.info("FFmpeg configured for audio processing")
    else:
        logger.warning(
            "FFmpeg not found. Audio conversion may fail. "
            "Please ensure FFmpeg is installed and accessible."
        )


# Store WSL paths if needed
_wsl_ffmpeg = None
_wsl_ffprobe = None


# Configure FFmpeg on module import
_configure_ffmpeg()


def _get_volume_by_chunks(audio: AudioSegment, chunk_length_ms: int) -> list:
    """
    Calculate the normalized volume (RMS) for each chunk of the audio.

    Parameters:
        audio (AudioSegment): The audio segment to process.
        chunk_length_ms (int): The length of each audio chunk in milliseconds.

    Returns:
        list: Normalized volumes for each chunk.
    """
    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]


def prepare_audio_payload(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
    forwarded: bool = False,
) -> dict[str, any]:
    """
    Prepares the audio payload for sending to a broadcast endpoint.
    If audio_path is None, returns a payload with audio=None for silent display.

    Parameters:
        audio_path (str | None): The path to the audio file to be processed, or None for silent display
        chunk_length_ms (int): The length of each audio chunk in milliseconds
        display_text (DisplayText, optional): Text to be displayed with the audio
        actions (Actions, optional): Actions associated with the audio

    Returns:
        dict: The audio payload to be sent
    """
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()

    if not audio_path:
        # Return payload for silent display
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions.to_dict() if actions else None,
            "forwarded": forwarded,
        }

    # Normalize path for cross-platform compatibility
    audio_path = os.path.normpath(audio_path) if audio_path else None

    # Verify file exists before trying to load it
    if not os.path.exists(audio_path):
        raise ValueError(f"Audio file does not exist: {audio_path}")

    try:
        # Check if we need to use WSL for FFmpeg
        global _wsl_ffmpeg, _wsl_ffprobe
        if _wsl_ffmpeg:
            # Convert Windows absolute path to WSL path
            import subprocess

            # Get absolute path and convert to WSL format
            abs_audio_path = os.path.abspath(audio_path)
            # Convert Windows path to WSL: C:\path -> /mnt/c/path
            drive_letter = abs_audio_path[0].lower()
            wsl_audio_path = (
                "/mnt/" + drive_letter + abs_audio_path[2:].replace("\\", "/")
            )

            logger.debug(
                f"Converting audio: Windows='{abs_audio_path}' -> WSL='{wsl_audio_path}'"
            )

            # Create temporary WAV file in cache directory
            cache_dir = os.path.dirname(abs_audio_path)
            if not cache_dir.endswith("cache"):
                cache_dir = os.path.join(cache_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            wav_temp_path = os.path.join(
                cache_dir, f"temp_{os.path.basename(audio_path)}.wav"
            )
            wsl_wav_path = "/mnt/" + drive_letter + wav_temp_path[2:].replace("\\", "/")

            try:
                # Use WSL FFmpeg to convert MP3 to WAV
                cmd = ["wsl", _wsl_ffmpeg, "-i", wsl_audio_path, "-y", wsl_wav_path]
                logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    logger.error(f"FFmpeg conversion failed: {result.stderr}")
                    raise ValueError(f"FFmpeg conversion failed: {result.stderr}")

                # Verify WAV file was created
                if not os.path.exists(wav_temp_path):
                    raise ValueError(f"WAV file was not created: {wav_temp_path}")

                # Load the WAV file using pydub (no FFmpeg needed for WAV)
                audio = AudioSegment.from_wav(wav_temp_path)
                audio_bytes = audio.export(format="wav").read()

                logger.debug(
                    f"Successfully converted MP3 to WAV: {len(audio_bytes)} bytes"
                )

                # Clean up temp file
                try:
                    os.unlink(wav_temp_path)
                except Exception:
                    pass
            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(wav_temp_path):
                    try:
                        os.unlink(wav_temp_path)
                    except Exception:
                        pass
                logger.error(f"WSL FFmpeg conversion error: {e}")
                raise e
        else:
            # Normal pydub conversion (FFmpeg available in Windows PATH)
            # Only use this if FFmpeg is NOT in WSL
            audio = AudioSegment.from_file(audio_path)
            audio_bytes = audio.export(format="wav").read()
    except Exception as e:
        raise ValueError(
            f"Error loading or converting generated audio file to wav file '{audio_path}': {e}"
        )
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    volumes = _get_volume_by_chunks(audio, chunk_length_ms)

    payload = {
        "type": "audio",
        "audio": audio_base64,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions.to_dict() if actions else None,
        "forwarded": forwarded,
    }

    return payload


# Example usage:
# payload, duration = prepare_audio_payload("path/to/audio.mp3", display_text="Hello", expression_list=[0,1,2])
