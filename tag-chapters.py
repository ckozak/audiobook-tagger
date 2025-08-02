import argparse
import os
import subprocess
import tempfile

# Import the core logic from our other script
from main import find_chapters

def get_total_duration(media_file):
    """Gets the total duration of a media file in seconds using ffprobe."""
    command = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        media_file
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error running ffprobe: {e}")
        print("Please ensure ffprobe (part of FFmpeg) is installed and in your system's PATH.")
        return None

def tag_m4b_with_ffmpeg(ebook_path, transcript_path, input_m4b, output_m4b, start_chapter=1):
    """
    Finds chapters and uses FFmpeg to tag them into a new M4B file.
    """
    print("--- Step 1: Finding chapter timestamps ---")
    found_chapters = find_chapters(ebook_path, transcript_path, start_chapter)

    if not found_chapters:
        print("No chapters were found. Aborting tagging process.")
        return

    print("\n--- Step 2: Generating FFmpeg metadata file ---")
    
    # Get total duration for the last chapter's end time
    total_duration_s = get_total_duration(input_m4b)
    if total_duration_s is None:
        return

    metadata_content = ";FFMETADATA1\n"
    for i, ch_info in enumerate(found_chapters):
        start_ms = int(ch_info['start_time'] * 1000)
        
        # Determine end time
        if i + 1 < len(found_chapters):
            end_ms = int(found_chapters[i+1]['start_time'] * 1000)
        else:
            end_ms = int(total_duration_s * 1000)

        title = ch_info['title']
        
        metadata_content += "[CHAPTER]\n"
        metadata_content += "TIMEBASE=1/1000\n"
        metadata_content += f"START={start_ms}\n"
        metadata_content += f"END={end_ms}\n"
        metadata_content += f"title={title}\n"
        print(f"  Prepared chapter: '{title}' ({start_ms}ms -> {end_ms}ms)")

    # Write metadata to a temporary file
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8') as temp_meta_file:
        temp_meta_file.write(metadata_content)
        metadata_filepath = temp_meta_file.name
    
    print(f"\nMetadata written to temporary file: {metadata_filepath}")

    print("\n--- Step 3: Running FFmpeg to tag file ---")
    # Command to merge metadata with the audio file without re-encoding.
    # -map 0:a      -> Take the audio stream from the first input.
    # -map 0:v?     -> Take the video stream (cover art) from the first input, if it exists.
    # -map_chapters 1 -> Take the chapter markers from the second input.
    command = [
        'ffmpeg',
        '-i', input_m4b,
        '-i', metadata_filepath,
        '-map', '0:a',
        '-map', '0:v?',
        '-map_chapters', '1',
        '-codec', 'copy',
        '-y',  # Overwrite output file if it exists
        output_m4b
    ]

    print(f"Executing command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"\n--- Success! ---")
        print(f"Tagged audio saved to: {output_m4b}")
    except FileNotFoundError:
        print("\n--- ERROR ---")
        print("ffmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        print("\n--- ERROR ---")
        print("FFmpeg command failed.")
        print(f"Return code: {e.returncode}")
        print(f"Stderr: {e.stderr}")
    finally:
        # Clean up the temporary metadata file
        os.remove(metadata_filepath)
        print(f"Cleaned up temporary file: {metadata_filepath}")


def main():
    parser = argparse.ArgumentParser(description="Find chapters and tag them into a new M4B file using FFmpeg.")
    parser.add_argument("ebook", help="Path to the EPUB file.")
    parser.add_argument("transcript", help="Path to the transcript JSON file.")
    parser.add_argument("input_m4b", help="Path to the input M4B audio file.")
    parser.add_argument("output_m4b", help="Path for the new, tagged M4B audio file.")
    parser.add_argument("--start-chapter", type=int, default=1, help="The chapter number to start matching from.")
    args = parser.parse_args()

    tag_m4b_with_ffmpeg(args.ebook, args.transcript, args.input_m4b, args.output_m4b, args.start_chapter)

if __name__ == '__main__':
    main()