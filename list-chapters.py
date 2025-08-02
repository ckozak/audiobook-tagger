import sys
from mutagen.mp4 import MP4

if len(sys.argv) != 2:
    print("Usage: python list-chapters.py <audiobook.m4b>")
    sys.exit(1)

audio_path = sys.argv[1]
try:
    audio = MP4(audio_path)
except Exception as e:
    print(f"Error opening file: {e}")
    sys.exit(1)

# audio.chapters is a list of MP4Chapter objects
if audio.chapters:
    # Get total audio length for the last chapter's end time
    total_duration = audio.info.length

    for i, ch in enumerate(audio.chapters):
        # Mutagen provides start time in milliseconds
        start = ch.start / 1000.0
        title = ch.title or "<no title>"

        # Determine end time
        if i + 1 < len(audio.chapters):
            # End time is the start of the next chapter
            end = audio.chapters[i+1].start / 1000.0
        else:
            # For the last chapter, end time is the total file duration
            end = total_duration

        # format H:MM:SS
        h, rem = divmod(start, 3600)
        m, s   = divmod(rem, 60)
        print(f"{int(h):02d}:{int(m):02d}:{int(s):02d} → "
              f"{int(end//3600):02d}:{int((end%3600)//60):02d}:"
              f"{int(end%60):02d}   {title}")
else:
    print("No chapters found in the file.")
