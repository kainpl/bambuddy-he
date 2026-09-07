"""One reader for a queue row's print time — the queue response and the farm
forecast must agree on it, so it lives in a service, not in the route."""

from backend.app.models.archive import PrintArchive
from backend.app.models.library import LibraryFile
from backend.app.services import queue_times


def test_archive_time_wins_and_a_plate_overrides_it(monkeypatch, tmp_path):
    archive = PrintArchive(filename="a", file_path="a.3mf", file_size=1, status="completed", print_time_seconds=100)
    monkeypatch.setattr(queue_times.settings, "base_dir", tmp_path)
    assert queue_times.print_time_for_row(archive=archive, library_file=None, plate_id=None) == 100
    # A plate of a multi-plate archive: the cached per-plate reader answers.
    (tmp_path / "a.3mf").write_bytes(b"not a zip")
    monkeypatch.setattr(queue_times, "plate_metadata_cached", lambda path, plate: (250, 0.0, None))
    assert queue_times.print_time_for_row(archive=archive, library_file=None, plate_id=2) == 250


def test_a_library_row_reads_its_metadata_and_its_plate(monkeypatch, tmp_path):
    lib = LibraryFile(
        filename="l.gcode.3mf",
        file_path="l.gcode.3mf",
        file_size=1,
        file_type="gcode",
        file_metadata={"print_time_seconds": 400},
    )
    monkeypatch.setattr(queue_times.settings, "base_dir", tmp_path)
    assert queue_times.print_time_for_row(archive=None, library_file=lib, plate_id=None) == 400
    (tmp_path / "l.gcode.3mf").write_bytes(b"x")
    monkeypatch.setattr(queue_times, "plate_metadata_cached", lambda path, plate: (90, 0.0, None))
    assert queue_times.print_time_for_row(archive=None, library_file=lib, plate_id=1) == 90


def test_a_missing_file_falls_back_to_the_row_level_estimate(monkeypatch, tmp_path):
    lib = LibraryFile(
        filename="l.gcode.3mf",
        file_path="gone.gcode.3mf",
        file_size=1,
        file_type="gcode",
        file_metadata={"print_time_seconds": 400},
    )
    monkeypatch.setattr(queue_times.settings, "base_dir", tmp_path)
    assert queue_times.print_time_for_row(archive=None, library_file=lib, plate_id=3) == 400
    assert queue_times.print_time_for_row(archive=None, library_file=None, plate_id=None) is None


def test_a_library_row_reads_its_plate_filaments(monkeypatch, tmp_path):
    lib = LibraryFile(
        filename="l.gcode.3mf",
        file_path="l.gcode.3mf",
        file_size=1,
        file_type="gcode",
        file_metadata={
            "plates": [
                {
                    "index": 1,
                    "filaments": [{"slot_id": 1, "type": "PETG", "color": "#000000", "used_g": 12.5}],
                },
                {"index": 2, "filaments": [{"slot_id": 1, "type": "PLA", "used_g": 3.0}]},
            ]
        },
    )
    monkeypatch.setattr(queue_times.settings, "base_dir", tmp_path)
    assert [f["type"] for f in queue_times.filaments_for_row(archive=None, library_file=lib, plate_id=2)] == ["PLA"]
    assert [f["type"] for f in queue_times.filaments_for_row(archive=None, library_file=lib, plate_id=None)] == [
        "PETG",
        "PLA",
    ]
    empty = LibraryFile(filename="e", file_path="e", file_size=1, file_type="gcode", file_metadata={})
    assert queue_times.filaments_for_row(archive=None, library_file=empty, plate_id=None) is None


def test_an_archive_row_reads_the_3mf_or_answers_none(monkeypatch, tmp_path):
    archive = PrintArchive(filename="a", file_path="a.3mf", file_size=1, status="completed")
    monkeypatch.setattr(queue_times.settings, "base_dir", tmp_path)
    assert queue_times.filaments_for_row(archive=archive, library_file=None, plate_id=1) is None
    (tmp_path / "a.3mf").write_bytes(b"x")
    monkeypatch.setattr(
        queue_times,
        "extract_filament_usage_from_3mf",
        lambda path, plate: [{"type": "PETG", "used_g": 9.0}],
    )
    assert queue_times.filaments_for_row(archive=archive, library_file=None, plate_id=1) == [
        {"type": "PETG", "used_g": 9.0}
    ]
