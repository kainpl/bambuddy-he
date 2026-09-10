"""Shared source validation at the queue's write boundaries."""

from pathlib import Path

from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.i18n import current_language, t
from backend.app.models.archive import PrintArchive
from backend.app.models.library import LibraryFile
from backend.app.services.filament_requirements import PrintRequirements, PrintRequirementsCache


def resolve_source_path(archive=None, library_file=None) -> Path | None:
    source = archive or library_file
    if source is None or not source.file_path:
        return None
    path = Path(source.file_path)
    return (
        path if path.is_absolute() else settings.base_dir / path
    )  # SEC-PATH-OK: persisted server-owned source path; external paths may be absolute.


def routing_detail(code: str, **params) -> dict:
    return {"code": code, "params": params, "message": t(current_language(), "filament_routing", code, **params)}


async def item_source(db, item):
    archive = await db.get(PrintArchive, item.archive_id) if item.archive_id else None
    library = None
    if not item.archive_id and item.library_file_id:
        library = (
            await db.execute(LibraryFile.active().where(LibraryFile.id == item.library_file_id))
        ).scalar_one_or_none()
    return archive, library


async def read_item_requirements(db, item, cache: PrintRequirementsCache | None = None) -> PrintRequirements:
    archive, library = await item_source(db, item)
    return await (cache or PrintRequirementsCache()).read(
        resolve_source_path(archive, library), item.plate_id, archive_plate_id=archive.plate_index if archive else None
    )


async def require_source_requirements(
    cache: PrintRequirementsCache,
    archive=None,
    library_file=None,
    plate_id: int | None = None,
    *,
    allow_raw_gcode: bool = False,
    product_plate_id: int | None = None,
) -> PrintRequirements | None:
    source = archive or library_file
    path = resolve_source_path(archive, library_file)
    # Only a server-identified raw G-code source keeps the existing explicit
    # per-printer workflow. A broken 3MF never acquires this exemption.
    if allow_raw_gcode and path is not None and path.suffix.lower() == ".gcode":
        return None
    req = await cache.read(path, plate_id, archive_plate_id=archive.plate_index if archive else None)
    if req.status != "ok":
        raise HTTPException(
            422,
            routing_detail(
                req.reason or "source_unreadable",
                source_id=source.id if source else None,
                plate_id=plate_id,
                product_plate_id=product_plate_id,
            ),
        )
    return req
