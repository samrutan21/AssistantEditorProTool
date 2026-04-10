import csv
from typing import Any


def generate_effects_report(data: list[dict[str, Any]], output_path: str) -> bool:
    """
    Generates an Online/Finishing Effects Tracker matching the
    production spreadsheet layout.
    """
    if not data:
        return False

    headers = [
        "Seq TC In",
        "Seq TC Out",
        "Clip Name",
        "Source TC In",
        "Source TC Out",
        "Effect",
        "Notes",
    ]

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for clip in data:
                writer.writerow(
                    [
                        clip.get("Seq_In", ""),
                        clip.get("Seq_Out", ""),
                        clip.get("Name", ""),
                        clip.get("Src_In", ""),
                        clip.get("Src_Out", ""),
                        clip.get("Effect", ""),
                        clip.get("Notes", ""),
                    ]
                )
        return True
    except OSError as e:
        print(f"Failed to write Effects Report: {e}")
        return False
