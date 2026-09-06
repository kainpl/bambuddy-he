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
