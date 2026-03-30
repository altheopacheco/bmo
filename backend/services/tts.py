import wave, io
from piper import PiperVoice
def synthesize(text: str, voice: PiperVoice) -> tuple[bytes, list]:
    
    buffer = io.BytesIO()
    sample_rate = voice.config.sample_rate
    
    with wave.open(buffer, "wb") as b:
        phonemes = voice.synthesize_wav(text, b, include_alignments=True)

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