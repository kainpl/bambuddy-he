"""Optional ffmpeg hardware acceleration flags for camera streams."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_DISABLED_VALUES = {"", "0", "false", "no", "none", "off"}
_SUPPORTED_MODES = {"vaapi"}
_DEFAULT_VAAPI_DEVICE = "/dev/dri/renderD128"


def rtsp_hwaccel_mode() -> str | None:
    """Return the requested RTSP hwaccel mode, or ``None`` when disabled.

    The switch is intentionally opt-in. Most installs do not mount GPU devices
    into the container, so silently keeping software decode as the default is
    the least surprising behaviour.
    """
    mode = os.environ.get("BAMDUDE_RTSP_HWACCEL", "").strip().lower()
    if mode in _DISABLED_VALUES:
        return None
    if mode in _SUPPORTED_MODES:
        return mode
    logger.warning("Unsupported BAMDUDE_RTSP_HWACCEL=%r; using software decode", mode)
    return None


def rtsp_hwaccel_input_args(mode: str | None = None) -> tuple[str, ...]:
    """ffmpeg input-side args for the selected RTSP hwaccel mode."""
    selected = rtsp_hwaccel_mode() if mode is None else mode
    if selected != "vaapi":
        return ()
    device = os.environ.get("BAMDUDE_VAAPI_DEVICE", _DEFAULT_VAAPI_DEVICE).strip() or _DEFAULT_VAAPI_DEVICE
    return (
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        device,
        "-hwaccel_output_format",
        "vaapi",
    )


def rtsp_hwaccel_filter_args(mode: str | None = None) -> tuple[str, ...]:
    """ffmpeg output-side filter args required after VAAPI decode.

    BamDude still emits MJPEG on stdout for the frontend/API contract. VAAPI
    decoded frames therefore have to be downloaded back to software frames
    before ffmpeg's MJPEG encoder sees them.
    """
    selected = rtsp_hwaccel_mode() if mode is None else mode
    if selected != "vaapi":
        return ()
    return ("-vf", "hwdownload,format=nv12")


__all__ = ["rtsp_hwaccel_filter_args", "rtsp_hwaccel_input_args", "rtsp_hwaccel_mode"]
