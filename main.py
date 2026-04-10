import os
import re
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import AssistantEditorPro
from app.core.scanner import XMLScanner, consolidate_consecutive, resolve_archival_types
from app.core.edl_parser import EDLScanner
from app.modules.archival import generate_archival_report
from app.modules.music import generate_music_report
from app.modules.effects import generate_effects_report
from app.ai.ollama_client import GemmaWorker, prepare_attachments

_FX_DEDUP_TOLERANCE = 48  # frames (~2 sec at 24fps)


def _parse_track_num(text: str) -> int:
    """Parse '16', 'A16', 'a16', 'V3' etc. into the integer portion."""
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def _dedup_effects(
    existing: list[dict], new: list[dict], fps: float
) -> list[dict]:
    """
    Return only those entries from *new* that don't already have a
    match in *existing* (same clip name, overlapping sequence TC).
    """
    kept: list[dict] = []
    for entry in new:
        name = entry.get("Name", "").lower()
        start = entry.get("_seq_start_frames", 0)
        dup = False
        for ex in existing:
            if ex.get("Name", "").lower() != name:
                continue
            ex_start = ex.get("_seq_start_frames", 0)
            if abs(start - ex_start) <= _FX_DEDUP_TOLERANCE:
                dup = True
                break
        if not dup:
            kept.append(entry)
    return kept

class AppController(AssistantEditorPro):
    """
    The 'Brain' that connects the UI buttons to the 
    actual processing logic.
    """
    def __init__(self):
        super().__init__()
        # Connect the 'GENERATE' button to the processing function
        self.btn_run.clicked.connect(self.run_generation)
        self.btn_send.clicked.connect(self.send_to_ai)
        self.chat_input.submitted.connect(self.send_to_ai)

    def run_generation(self):
        self._switch_panel(0)

        has_xml = bool(self.xml_path)
        has_edl = bool(self.edl_paths)

        if not (has_xml or has_edl) or not self.export_folder:
            QMessageBox.warning(
                self,
                "Error",
                "Please select a source file (XML and/or EDL) and an Export folder.",
            )
            return

        scanner: XMLScanner | None = None
        edl_scanners: list[EDLScanner] = []

        user_fps = self.get_selected_fps()

        if has_xml:
            scanner = XMLScanner(self.xml_path, fps=user_fps)

        fps = scanner.fps if scanner else user_fps

        if scanner and abs(fps - user_fps) > 0.01:
            self.fps_combo.setEditText(f"{fps:.3f}".rstrip("0").rstrip("."))

        for edl_path in self.edl_paths:
            edl_scanners.append(EDLScanner(edl_path, fps=fps))

        self.report_log.append("<b>System:</b> Starting scan...")
        self.report_log.append(f"Sequence frame rate: {fps:.3f} fps")
        if has_edl and has_xml:
            self.report_log.append(
                "EDL is primary source · XML used for supplemental "
                "effect detection only"
            )

        # ── Archival ────────────────────────────────────────────
        archival_tag = self.tag_input.text().strip()
        if archival_tag:
            arc_raw: list[dict] = []
            if edl_scanners:
                self.report_log.append(
                    f"Scanning EDL(s) for archival tag: {archival_tag}"
                )
                for edl in edl_scanners:
                    arc_raw.extend(edl.scan_for_archival(archival_tag))
            elif scanner:
                self.report_log.append(
                    f"Scanning XML for archival tag: {archival_tag}"
                )
                arc_raw.extend(scanner.scan_for_archival(archival_tag))

            if arc_raw:
                arc_data = resolve_archival_types(arc_raw)
                out = os.path.join(
                    self.export_folder, f"ARCHIVAL_LOG_{archival_tag}.csv"
                )
                if generate_archival_report(arc_data, out):
                    self.report_log.append(
                        f"✅ Archival Report saved: {os.path.basename(out)}"
                    )

        # ── Music Cue Sheet ─────────────────────────────────────
        m_start = _parse_track_num(self.m_start.text())
        m_end = _parse_track_num(self.m_end.text()) or m_start
        has_dedicated_music_edl = bool(self.music_edl_path)

        music_scanners: list[EDLScanner] = []
        if has_dedicated_music_edl:
            music_scanners.append(EDLScanner(self.music_edl_path, fps=fps))
            self.report_log.append(
                f"Using dedicated music EDL: "
                f"{os.path.basename(self.music_edl_path)}"
            )
        elif edl_scanners:
            music_scanners = edl_scanners

        mus_raw: list[dict] = []
        if music_scanners:
            for edl in music_scanners:
                summary = edl.audio_track_summary()
                if summary:
                    parts = []
                    for pos in sorted(summary):
                        sample = summary[pos][0][:40]
                        parts.append(f"Pos {pos}: {sample}…")
                    self.report_log.append(
                        f"EDL audio tracks: {' · '.join(parts)}"
                    )

                if has_dedicated_music_edl:
                    self.report_log.append(
                        "Scanning all audio in dedicated music EDL..."
                    )
                    mus_raw.extend(edl.scan_by_tracks(media_type="audio"))
                elif m_start > 0:
                    self.report_log.append(
                        f"Scanning EDL audio track position {m_start}"
                        + (f"–{m_end}" if m_end != m_start else "")
                        + " for music..."
                    )
                    mus_raw.extend(
                        edl.scan_by_tracks(m_start, m_end, media_type="audio")
                    )
                else:
                    self.report_log.append("Scanning all EDL audio for music...")
                    mus_raw.extend(edl.scan_by_tracks(media_type="audio"))
        elif scanner and m_start > 0:
            self.report_log.append(f"Scanning XML Music Tracks: A{m_start}–A{m_end}")
            mus_raw.extend(
                scanner.scan_by_tracks(m_start, m_end, media_type="audio")
            )

        if mus_raw:
            mus_data = consolidate_consecutive(mus_raw, fps)
            out = os.path.join(self.export_folder, "MUSIC_CUE_SHEET.csv")
            if generate_music_report(mus_data, out):
                self.report_log.append(
                    f"✅ Music Cue Sheet saved: {os.path.basename(out)}"
                )
        elif m_start > 0 or music_scanners:
            self.report_log.append("⚠️ No music clips found.")

        # ── Effects ─────────────────────────────────────────────
        fps_map: dict[str, float] | None = None
        if scanner:
            fps_map = scanner.clip_fps_map()
            if fps_map:
                self.report_log.append(
                    f"Loaded native frame rates for {len(fps_map)} clips "
                    "from XML (used to filter false speed detections)"
                )

        fx_data: list[dict] = []
        fx_review: list[dict] = []
        if edl_scanners:
            self.report_log.append("Scanning EDL(s) for speed changes...")
            for edl in edl_scanners:
                confirmed, filtered = edl.scan_for_effects(
                    clip_fps_map=fps_map
                )
                fx_data.extend(confirmed)
                fx_review.extend(filtered)
        if scanner:
            self.report_log.append("Scanning XML for Time Remap effects...")
            xml_fx = scanner.scan_for_effects()
            fx_data.extend(_dedup_effects(fx_data, xml_fx, fps))

        if not scanner and not edl_scanners:
            pass
        elif fx_data:
            out = os.path.join(self.export_folder, "TECH_EFFECTS_TRACKER.csv")
            if generate_effects_report(fx_data, out):
                self.report_log.append(
                    f"✅ Effects Report saved: {os.path.basename(out)}"
                )
        else:
            self.report_log.append("ℹ️ No effects detected.")

        if fx_review:
            out_review = os.path.join(
                self.export_folder, "TECH_EFFECTS_REVIEW.csv"
            )
            if generate_effects_report(fx_review, out_review):
                self.report_log.append(
                    f"ℹ️ {len(fx_review)} possible false positives saved "
                    f"for review: {os.path.basename(out_review)}"
                )

        self.report_log.append(
            "<br><b>All tasks complete.</b> "
            "Switch to the Assistant panel to ask Gemma about these files."
        )
    
    def send_to_ai(self) -> None:
        user_query = self.chat_input.toPlainText().strip()
        if not user_query:
            return

        attached = list(self.attached_files)
        attachment_names = [os.path.basename(p) for p in attached]

        display = f"<br><b>You:</b> {user_query}"
        if attachment_names:
            chips = ", ".join(attachment_names)
            display += f"<br><small style='color:#5C7CFA;'>Attached: {chips}</small>"
        self.chat_box.append(display)

        self.chat_input.clear()
        self.attached_files.clear()
        self._rebuild_chips()
        self.chat_box.append("<i>Gemma is thinking...</i>")

        images, file_texts = prepare_attachments(attached)
        self.worker = GemmaWorker(
            user_query, images=images, file_texts=file_texts
        )
        self.worker.response_received.connect(self.display_ai_response)
        self.worker.error_occurred.connect(self.display_ai_error)
        self.worker.start()

    def display_ai_response(self, text: str) -> None:
        self.chat_box.append(f"<b>Gemma:</b> {text}")
        self._save_current_chat()

    def display_ai_error(self, error_msg: str) -> None:
        self.chat_box.append(
            f"<span style='color:red;'><b>Error:</b> {error_msg}</span>"
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController()
    controller.show()
    sys.exit(app.exec())
