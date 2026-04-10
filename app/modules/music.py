import csv
from typing import Any

def generate_music_report(data: list[dict[str, Any]], output_path: str) -> bool:
    """
    Generates a Music Cue Sheet matching the user's specific columns
    while maintaining full SMPTE timecode for the Duration.
    """
    if not data:
        return False

    headers = [
        "TC IN",
        "TC OUT",
        "DURATION",
        "FILE NAME",
        "CUE NAME",
        "DESCRIPTION",
        "SOURCE",
        "COMPOSER/ARTIST",
        "NOTES",
        "CUE STATUS",
    ]

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for clip in data:
                writer.writerow(
                    [
                        clip.get("Seq_In", "01:00:00:00"),
                        clip.get("Seq_Out", "01:00:00:00"),
                        clip.get("Duration", "00:00:00:00"),
                        clip.get("Name", ""),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "PENDING",
                    ]
                )
        return True
    except OSError as e:
        print(f"Failed to write Music Cue Sheet: {e}")
        return False
