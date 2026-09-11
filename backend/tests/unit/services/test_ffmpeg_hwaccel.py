"""Unit tests for optional ffmpeg hardware acceleration flags."""

from __future__ import annotations

from backend.app.services.ffmpeg_hwaccel import (
    rtsp_hwaccel_filter_args,
    rtsp_hwaccel_input_args,
    rtsp_hwaccel_mode,
)


def test_rtsp_hwaccel_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BAMDUDE_RTSP_HWACCEL", raising=False)

    assert rtsp_hwaccel_mode() is None
    assert rtsp_hwaccel_input_args() == ()
    assert rtsp_hwaccel_filter_args() == ()


def test_rtsp_hwaccel_accepts_common_disabled_values(monkeypatch):
    for value in ("0", "false", "no", "none", "off", " "):
        monkeypatch.setenv("BAMDUDE_RTSP_HWACCEL", value)
        assert rtsp_hwaccel_mode() is None


def test_unknown_rtsp_hwaccel_mode_falls_back_to_software(monkeypatch, caplog):
    monkeypatch.setenv("BAMDUDE_RTSP_HWACCEL", "cuda")

    assert rtsp_hwaccel_mode() is None
    assert "Unsupported BAMDUDE_RTSP_HWACCEL" in caplog.text


def test_vaapi_rtsp_hwaccel_uses_default_render_node(monkeypatch):
    monkeypatch.setenv("BAMDUDE_RTSP_HWACCEL", "vaapi")
    monkeypatch.delenv("BAMDUDE_VAAPI_DEVICE", raising=False)

    assert rtsp_hwaccel_mode() == "vaapi"
    assert rtsp_hwaccel_input_args() == (
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "/dev/dri/renderD128",
        "-hwaccel_output_format",
        "vaapi",
    )
    assert rtsp_hwaccel_filter_args() == ("-vf", "hwdownload,format=nv12")


def test_vaapi_rtsp_hwaccel_allows_custom_render_node(monkeypatch):
    monkeypatch.setenv("BAMDUDE_RTSP_HWACCEL", "VAAPI")
    monkeypatch.setenv("BAMDUDE_VAAPI_DEVICE", "/dev/dri/renderD129")

    assert rtsp_hwaccel_input_args() == (
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "/dev/dri/renderD129",
        "-hwaccel_output_format",
        "vaapi",
    )
