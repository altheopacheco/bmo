import tempfile, subprocess, os

from faster_whisper import WhisperModel

model = WhisperModel("base.en", device="cpu", compute_type="int8")

def transcribe_audio(audio_bytes: bytes):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        webm_path = tmp.name

    wav_path = webm_path + ".wav"

    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", webm_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path
        ], check=True, capture_output=True)

        result = model.transcribe(wav_path, language="en", without_timestamps=True)

        return result

    except Exception as e:
        print(f"Transcription error: {e}")
        raise e

    finally:
        for path in [webm_path, wav_path]:
            if os.path.exists(path):
                os.unlink(path)