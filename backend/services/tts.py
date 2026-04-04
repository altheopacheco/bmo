from abc import ABC, abstractmethod
import asyncio
import wave, io
from piper import PiperVoice, SynthesisConfig

syn_config = SynthesisConfig(
    volume=0.8,  # half as loud
    length_scale=0.8,  # twice as slow
    noise_scale=0.6,  # more audio variation
    noise_w_scale=0.8,  # more speaking variation
    normalize_audio=False, # use raw audio from voice
)

class TTSService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> tuple[bytes, list]:
        """Returns (audio_bytes, viseme_timeline)"""
        pass
    
class PiperTTS(TTSService):
    def __init__(self, voice: PiperVoice):
        self.voice = voice
    
    async def synthesize(self, text: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text)
    
    def _synthesize_sync(self, text: str) -> tuple[bytes, list]:
        buffer = io.BytesIO()
        sample_rate = self.voice.config.sample_rate
        
        with wave.open(buffer, "wb") as b:
            phonemes = self.voice.synthesize_wav(text, b, include_alignments=True, syn_config=syn_config)

        timeline = []
        time_cursor = 0.0
        for pa in phonemes:
            duration = pa.num_samples / sample_rate
            timeline.append({
                "phoneme": pa.phoneme,
                "start": round(time_cursor, 4),
                "end":   round(time_cursor + duration, 4),
            })
            time_cursor += duration

        buffer.seek(0)
        return buffer.read(), timeline