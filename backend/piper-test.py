import wave
from piper import PiperVoice

MODEL_PATH = "./models/en_US-hfc_female-medium.onnx"

voice = PiperVoice.load(MODEL_PATH)
with wave.open("test.wav", "wb") as wav_file:
    voice.synthesize_wav("Hi I'm BMO", wav_file)