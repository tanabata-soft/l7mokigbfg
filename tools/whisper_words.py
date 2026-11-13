import sys, json
import numpy as np
import av
from faster_whisper import WhisperModel

# usage: whisper_words.py file.mp4:ja:vad file2.mp4:en:novad ...
model = WhisperModel("small", device="cpu", compute_type="int8")

def decode(src):
    container = av.open(src)
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    frames = []
    for frame in container.decode(stream):
        for rf in resampler.resample(frame):
            frames.append(rf.to_ndarray().reshape(-1))
    return np.concatenate(frames).astype(np.float32) / 32768.0

for spec in sys.argv[1:]:
    src, lang, mode = spec.rsplit(":", 2)
    audio = decode(src)
    kw = dict(language=lang, word_timestamps=True, beam_size=5)
    if mode == "vad":
        kw["vad_filter"] = True
    segments, info = model.transcribe(audio, **kw)
    segs = []
    for s in segments:
        words = [[round(w.start, 2), len(w.word.strip())] for w in (s.words or []) if w.word.strip()]
        segs.append({"s": round(s.start, 2), "e": round(s.end, 2), "w": words})
    print("WORDSJSON " + json.dumps({"file": src, "segs": segs}, ensure_ascii=False), flush=True)
print("ALLDONE", flush=True)
