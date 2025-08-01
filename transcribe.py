from faster_whisper import WhisperModel
import sys
import os
import time

model_size = "medium"
audio_path = sys.argv[1]
output_dir = sys.argv[2]

print("Loading model on GPU (device='cuda', compute_type='float16')...")
try:
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print("Model loaded successfully on CUDA.")
except Exception as e:
    print(f"Failed to load model: {e}")
    sys.exit(1)

print("  Running inference on GPU…")
print(f"Transcribing file: {audio_path}")
start_time = time.perf_counter()
try:
    segments, info = model.transcribe(audio_path)
    elapsed = time.perf_counter() - start_time
    print(f"Successful transcribing: {elapsed:.1f} seconds")
except Exception as e:
    print(f"Transcription failed: {e}")
    elapsed = time.perf_counter() - start_time
    print(f"Failed to transcribing: {elapsed:.1f} seconds")
    sys.exit(1)
    
# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

print("Generating segments (this is GPU heavy)…")
start_inf = time.perf_counter()
segments_list = list(segments)
inf_time = time.perf_counter() - start_inf
print(f"  → GPU inference took {inf_time:.1f} seconds")

print(f"Transcription complete. {len(segments_list)} segments found.")

output_path = os.path.join(
    output_dir,
    os.path.splitext(os.path.basename(audio_path))[0] + ".json"
)

with open(output_path, "w", encoding="utf-8") as f:
    import json
    json.dump([{
        "start": seg.start,
        "end": seg.end,
        "text": seg.text
    } for seg in segments_list], f, indent=2)

print(f"Saved transcript to {output_path}")
