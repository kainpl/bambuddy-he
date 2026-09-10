"""Server-owned, versioned routing intent. Telemetry and paths never persist here."""

import json
from dataclasses import asdict

from backend.app.services.filament_routing import RoutingPolicy

VERSION = 1
FEED_POLICIES = {"auto", "ams_only", "external_only"}
CHOICE_FIELDS = {"feed_policy", "force_color_match", "filament_overrides"}


def decode(value, fallback=None):
    if value is None:
        return fallback
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return fallback


def feed_policy(explicit=None, use_ams=True):
    return explicit if explicit in FEED_POLICIES else ("auto" if use_ams is not False else "external_only")


def valid_overrides(overrides):
    if not isinstance(overrides, list):
        return False
    seen = set()
    for override in overrides:
        if not isinstance(override, dict):
            return False
        slot = override.get("slot_id")
        if type(slot) is not int or slot < 1 or slot in seen:
            return False
        seen.add(slot)
        if any(
            override.get(k) is not None and not isinstance(override[k], str) for k in ("type", "color", "tray_info_idx")
        ):
            return False
        if "force_color_match" in override and type(override["force_color_match"]) is not bool:
            return False
    return True


def auto_policy(item):
    overrides = decode(item.filament_overrides, [])
    if not valid_overrides(overrides):
        return RoutingPolicy(review_required=True)
    return RoutingPolicy(
        feed_policy=feed_policy(getattr(item, "feed_policy", None), item.use_ams),
        force_color_match=bool(item.force_color_match),
        filament_overrides=tuple(overrides),
    )


def choices_policy(choices, snapshot=None):
    mapping = decode(choices.get("ams_mapping"))
    pins = {}
    if isinstance(mapping, list):
        sources = {source.id: source for source in snapshot.sources} if snapshot else {}
        for slot, source_id in enumerate(mapping, 1):
            if isinstance(source_id, int) and source_id >= 0:
                source = sources.get(source_id)
                pins[slot] = {"source_id": source_id}
                if source:
                    pins[slot].update(
                        type=source.material,
                        color=source.color,
                        tray_info_idx=source.variant,
                        nozzles=list(source.nozzles),
                    )
    # Explicit physical selections outrank the old boolean (including stale
    # use_ams=False accompanying real AMS pins).
    explicit = choices.get("feed_policy")
    policy = "auto" if pins and explicit is None else feed_policy(explicit, choices.get("use_ams", True))
    return RoutingPolicy(
        mode="pinned" if mapping is not None else "auto",
        feed_policy=policy,
        force_color_match=bool(choices.get("force_color_match", False)),
        filament_overrides=tuple(decode(choices.get("filament_overrides"), []) or []),
        physical_pins=pins,
    )


def source_scope(archive_id=None, library_file_id=None):
    return {"kind": "archive" if archive_id else "library", "id": archive_id or library_file_id}


def serialize_policy(
    policy,
    *,
    archive_id=None,
    library_file_id=None,
    requirements=None,
    plate_id=None,
    printer_id=None,
    exact_model=False,
):
    identity = source_scope(archive_id, library_file_id)
    if requirements and requirements.source_identity:
        identity["revision"] = {
            "size": requirements.source_identity.size,
            "mtime_ns": requirements.source_identity.mtime_ns,
        }
        plate_id = requirements.resolved_plate_id
    return json.dumps(
        {
            "version": VERSION,
            **asdict(policy),
            "source_identity": identity,
            "resolved_plate_id": plate_id,
            "printer_id": printer_id,
            "exact_model": exact_model,
        },
        separators=(",", ":"),
    )


def deserialize_policy(value):
    data = decode(value)
    if not isinstance(data, dict) or type(data.get("version")) is not int or data.get("version") != VERSION:
        return RoutingPolicy(review_required=True)
    if data.get("mode") not in {"auto", "pinned"} or data.get("feed_policy") not in FEED_POLICIES:
        return RoutingPolicy(review_required=True)
    try:
        overrides = data.get("filament_overrides") or []
        if not valid_overrides(overrides):
            raise ValueError("Invalid overrides")
        pins = {int(k): dict(v) for k, v in (data.get("physical_pins") or {}).items()}
        if any(
            slot < 1
            or type(pin.get("source_id")) is not int
            or pin["source_id"] < 0
            or any(pin.get(k) is not None and not isinstance(pin[k], str) for k in ("type", "color", "tray_info_idx"))
            or (
                "nozzles" in pin
                and (
                    not isinstance(pin["nozzles"], list)
                    or any(type(n) is not int or n not in (0, 1) for n in pin["nozzles"])
                )
            )
            for slot, pin in pins.items()
        ):
            raise ValueError("Invalid pins")
        if any(
            k in data and type(data[k]) is not bool for k in ("force_color_match", "review_required", "exact_model")
        ):
            raise ValueError("Invalid policy flags")
        return RoutingPolicy(
            mode=data["mode"],
            feed_policy=data["feed_policy"],
            force_color_match=bool(data.get("force_color_match", False)),
            filament_overrides=tuple(overrides),
            physical_pins=pins,
            review_required=bool(data.get("review_required", False)),
        )
    except (ValueError, TypeError, AttributeError):
        return RoutingPolicy(review_required=True)


def queue_policy(item):
    if item.filament_routing is not None:
        return deserialize_policy(item.filament_routing)
    # Old producers/rows have physical intent. No best-effort remapping here.
    policy = choices_policy({"ams_mapping": item.ams_mapping, "use_ams": item.use_ams})
    if policy.mode == "auto":
        return RoutingPolicy(mode="pinned", review_required=True)
    return policy


def restore_routing_source(item):
    """Repeat/copy keeps the source the intent describes, even after an execution archive was linked."""
    snapshot = decode(item.filament_routing)
    if not isinstance(snapshot, dict) or snapshot.get("version") != VERSION:
        return
    source = snapshot.get("source_identity", {})
    if not isinstance(source, dict):
        return
    if source.get("kind") == "library" and source.get("id"):
        item.library_file_id, item.archive_id = source["id"], None
    elif source.get("kind") == "archive" and source.get("id"):
        item.archive_id, item.library_file_id = source["id"], None
    snapshot.pop("runtime", None)
    item.filament_routing = json.dumps(snapshot)
