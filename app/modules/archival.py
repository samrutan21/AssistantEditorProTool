import csv
from typing import Any


def generate_archival_report(data: list[dict[str, Any]], output_path: str) -> bool:
    """
    Generates an Archival Master Log matching the production spreadsheet layout.
    """
    if not data:
        return False

    data.sort(key=lambda c: c.get("_seq_start_frames", 0))

    headers = [
        "SCREENGRAB",
        "TIMECODE IN",
        "TIMECODE OUT",
        "START",
        "SOURCE END",
        "SEQ DURATION",
        "SRC DURATION",
        "TYPE",
        "OX ID",
        "FILE NAME",
        "SOURCE LINK",
        "GETTY ID",
        "OWNER",
        "NOTES",
        "RESOLUTION",
        "MASTER?",
        "REQUESTED?",
        "RECEIVED?",
    ]

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for clip in data:
                raw_name = clip.get("Name", "")

                if "_" in raw_name:
                    ox_id, clip_name = raw_name.split("_", 1)
                else:
                    ox_id = ""
                    clip_name = raw_name

                writer.writerow(
                    [
                        "",                                 # SCREENGRAB
                        clip.get("Seq_In", ""),             # TIMECODE IN
                        clip.get("Seq_Out", ""),            # TIMECODE OUT
                        clip.get("Src_In", ""),             # START
                        clip.get("Src_Out", ""),            # SOURCE END
                        clip.get("Duration", ""),           # SEQ DURATION
                        clip.get("Src_Duration", ""),       # SRC DURATION
                        clip.get("Asset_Type", ""),         # TYPE
                        ox_id.strip(),                      # OX ID
                        clip_name.strip(),                  # FILE NAME
                        "",                                 # SOURCE LINK
                        "",                                 # GETTY ID
                        "",                                 # OWNER
                        "",                                 # NOTES
                        clip.get("Resolution", ""),         # RESOLUTION
                        "",                                 # MASTER?
                        "",                                 # REQUESTED?
                        "",                                 # RECEIVED?
                    ]
                )
        return True
    except OSError as e:
        print(f"Failed to write Archival Report: {e}")
        return False
