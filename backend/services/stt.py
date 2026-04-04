import asyncio
import tempfile, subprocess, os
from abc import ABC, abstractmethod
from faster_whisper import WhisperModel

class STTService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        pass
    
class WhisperSTT(STTService):
    def __init__(self, model="base.en", device="cpu", compute_type="int8"):
        self.model = WhisperModel(model, device=device, compute_type=compute_type)
        
    async def transcribe(self, audio_bytes) -> str:
        loop = asyncio.get_running_loop()
        segments, _ = await loop.run_in_executor(None, self._transcribe_sync, audio_bytes)
        return " ".join(seg.text for seg in segments)

    def _transcribe_sync(self, audio_bytes: bytes):
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            webm_path = tmp.name

        wav_path = webm_path + ".wav"

        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", webm_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path
            ], check=True, capture_output=True)

            result = self.model.transcribe(wav_path, language="en", without_timestamps=True)

            return result

        except Exception as e:
            print(f"Transcription error: {e}")
            raise e

        finally:
            for path in [webm_path, wav_path]:
                if os.path.exists(path):
                    os.unlink(path)