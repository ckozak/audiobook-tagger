# Audiobook Chapter Tagger

This project is a suite of Python scripts designed to automatically generate chapter markers for an audiobook (`.m4b` format) based on its corresponding e-book version (`.epub` format). It uses AI-powered transcription and semantic text matching to align the e-book's chapters with the audiobook's timeline.

## Features

-   **Automatic Transcription**: Uses `faster-whisper` to generate a timestamped transcript of the audiobook.
-   **Semantic Chapter Matching**: Intelligently finds where each chapter from the e-book begins in the audio transcript.
-   **Lossless Tagging**: Uses FFmpeg to write the generated chapter markers to a new audio file without re-encoding or losing audio quality.
-   **Flexible**: Supports multi-part audiobooks and is resilient to minor transcription errors.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Python 3.8+**
2.  **pip** (Python package installer)
3.  **FFmpeg**: Must be installed and accessible from your system's PATH. This is used for the final tagging step.
4.  **A CUDA-compatible GPU** (Recommended for `transcribe.py`): While not strictly required, transcription will be significantly faster with a GPU.

## Installation

1.  Clone or download the scripts into a directory.
2.  Install the required Python packages using the `requirements.txt` file:

    ```bash
    pip install -r requirements.txt
    ```

## Workflow

The process involves four main steps.

### Step 1: Transcribe the Audiobook

First, generate a timestamped transcript from your `.m4b` audio file. This is the most time-consuming step, especially without a GPU.

**Usage:**
```bash
python transcribe.py <path_to_audiobook.m4b> <output_directory>
```

**Example:**
```bash
python transcribe.py "E-Day (1 of 2).m4b" "transcript/"
```
This will create a `transcript/E-Day (1 of 2).json` file.

### Step 2: (Optional) Preview Chapter Matches

You can run `main.py` to see a detailed preview of how the e-book chapters align with the transcript. This is useful for debugging or verifying the alignment before tagging.

**Usage:**
```bash
python main.py <path_to_ebook.epub> <path_to_transcript.json>
```

**Example:**
```bash
python main.py "E-Day.epub" "transcript/E-Day (1 of 2).json"
```

### Step 3: Tag the M4B File with Chapters

This is the final step. The script will find the chapters (the same logic as `main.py`) and then use FFmpeg to create a new, tagged version of your audiobook. **Your original file will not be modified.**

**Usage:**
```bash
python tag-chapters.py <ebook.epub> <transcript.json> <input.m4b> <output.m4b>
```

**Example:**
```bash
python tag-chapters.py "E-Day.epub" "transcript/E-Day (1 of 2).json" "E-Day (1 of 2).m4b" "E-Day (1 of 2) tagged.m4b"
```

#### For Multi-Part Audiobooks

If you are working with the second or third part of a book, use the `--start-chapter` flag to tell the script where to begin matching.

**Example (for Part 2 starting at Chapter 19):**
```bash
python tag-chapters.py "E-Day.epub" "transcript/E-Day (2 of 2).json" "E-Day (2 of 2).m4b" "E-Day (2 of 2) tagged.m4b" --start-chapter 19
```

### Step 4: Verify the Chapters

You can verify the chapters in the new file using either `list-chapters.py` or FFmpeg directly.

**Using `list-chapters.py`:**
```bash
python list-chapters.py "E-Day (1 of 2) tagged.m4b"
```

**Using FFmpeg:**
```bash
ffmpeg -i "E-Day (1 of 2) tagged.m4b"
```
(Look for the `Chapters:` section in the output.)

---

## Developer & AI Contributor Notes

This section provides guidance for developers or other AI agents looking to modify or extend this project.

### Architectural Overview

The project follows a modular, pipeline-based architecture. Each script has a distinct responsibility, and they are designed to be used in sequence. The core logic is intentionally separated from the scripts that perform actions.

-   **Data Flow**: `M4B` → `transcribe.py` → `JSON Transcript` → `main.py` → `Chapter Data` → `tag-chapters.py` → `FFmpeg Metadata` → `Tagged M4B`

### Module Descriptions

-   `transcribe.py`: A standalone utility script. Its only job is to execute the `faster-whisper` transcription model on an audio file and save the result as a JSON file. It does not contain any logic related to chapters.

-   `main.py`: This script contains the "brains" of the operation in the `find_chapters` function. This function takes an e-book and a transcript and performs the semantic search to find chapter alignments. The `if __name__ == '__main__':` block in this script is purely for **preview and debugging purposes**; it is not part of the main tagging workflow.

-   `tag-chapters.py`: This is the primary orchestration script for the final action. It calls `find_chapters` from `main.py` to get the chapter data, generates a standard FFmpeg metadata file, and then executes `ffmpeg` via a `subprocess` call to create the final, tagged audio file.

-   `list-chapters.py`: A simple verification utility that uses `mutagen` to read and print existing chapter markers from a file.

### Key Design Decisions

-   **Separation of Logic**: The core chapter-finding logic (`find_chapters`) is decoupled from the file I/O and tagging actions. When modifying the matching algorithm, changes should primarily be made within `find_chapters`.

-   **FFmpeg for Tagging**: Early attempts to use Python libraries (`mutagen`, `tbm-utils`) for writing M4B chapter metadata proved unreliable and led to persistent, difficult-to-debug errors. The decision was made to switch to an FFmpeg-based approach, which is the industry standard and has proven to be robust. **Any future modifications to the tagging process should continue to use FFmpeg.** Avoid re-introducing direct Python M4B tagging libraries.

-   **Immutability**: The workflow is designed to be non-destructive. The original audio file is never modified. The `tag-chapters.py` script always creates a new, tagged copy.