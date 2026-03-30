import wave, io
from piper import PiperVoice

def synthesize(text: str, voice: PiperVoice) -> bytes:
    
    buffer = io.BytesIO()
    
    with wave.open(buffer, "wb") as b:
        voice.synthesize_wav(text, b)
        
    buffer.seek(0)
    return buffer.read()