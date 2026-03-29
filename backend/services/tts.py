import wave, io
from piper import PiperVoice, SynthesisConfig

syn_config = SynthesisConfig(
    volume=0.5,  # half as loud
    length_scale=1.0,  # twice as slow
    noise_scale=0.9,  # more audio variation
    noise_w_scale=0.8,  # more speaking variation
    normalize_audio=False, # use raw audio from voice
)

def synthesize(text: str, voice: PiperVoice) -> bytes:
    
    buffer = io.BytesIO()
    
    with wave.open(buffer, "wb") as b:
        voice.synthesize_wav(text, b)
        
    buffer.seek(0)
    return buffer.read()