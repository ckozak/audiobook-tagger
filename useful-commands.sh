!/bin/bash

# cut the end of the audiofile. Takes file from 0 to timestamp 3120 seconds
ffmpeg -i input.m4b -t 3120 -c copy trimmed.m4b

# cut the first 40 seconds with seeking for keyframe in the audiofile.
ffmpeg -i input.m4b -ss 40 -c copy output.m4b


docker run --rm -it -v "$HOME/.cache/huggingface":/root/.cache/huggingface -v "$PWD":/app audiobook-env python transcribe.py /app/audiobook.m4b /app/transcript