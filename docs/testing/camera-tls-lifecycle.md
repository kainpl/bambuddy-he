# Camera TLS lifecycle validation

Software acceptance, 2026-09-11. Hardware smoke was **not performed**; all peers
were local test listeners, with temporary certificates. No farm camera was
contacted. Tests import the production modules, not extracted copies of them.

## What changed

`backend/app/services/camera_tls.py` owns the listener, accepted connections,
forwarders and writer shutdown tasks. Existing imports from `services/camera.py`
remain supported. State lives outside the server in a weak-key registry, so it
works with uvloop's slotted server objects.

`close_tls_proxy` shares one coordinator between concurrent callers. Writers
close concurrently: a 1-second graceful phase precedes transport abort, within
a single 2-second total proxy deadline. Cancellation waits for that bounded
cleanup, then propagates. An incomplete close raises `TimeoutError`, retains
unfinished resource ownership and never reports CLOSED. These budgets apply to
an event loop that is running, not to an indefinitely blocked event-loop thread.

`CameraAttempt` in `services/camera_cleanup.py` closes the process, stderr drain
and proxy in order. Every built-in stream retry gets a new proxy and input URL,
after the old attempt closes and the existing reconnect delay elapses. A cleanup
failure stops retries. The existing camera janitor also receives explicit
Process owners when exit cannot be confirmed; this covers Windows and external
RTSP usernames that the Linux Bambu-specific `/proc` scan cannot discover.

TLS verification/ciphers, camera profiles, FPS, reconnect limits, single-flight,
fan-out, stream tokens, request-line rewriting and MJPEG payloads are preserved.
TLS exception logs contain the exception type and target/local-port context,
not peer payloads or credentials. Forced abort is logged once per proxy.

## Evidence

Before implementation, a production-import regression for a stalled TLS
handshake failed on **both Windows Proactor and Selector**: listener-only close
did not finish within the test deadline. The same regression passes after the
change; no expected-failure marker hides it.

| Check | Result |
| --- | --- |
| Windows, Python 3.12.10, targeted camera suite below | 247 passed, 1 Linux-only skip |
| Linux container, Python 3.12.13, asyncio **and uvloop 0.22.1**, both new lifecycle files | 77 passed, no skips |
| Linux `test_capture_pid_tracking.py`, including `/proc`/`SIGKILL` regression | 8 passed |
| Full backend Ruff check | Passed |
| Changed-file formatting, diff check and repository pre-commit hooks | Passed |

The Windows skip is the existing `/proc`/`SIGKILL` test in
`test_capture_pid_tracking.py`; it is unrelated to uvloop availability. The new
explicit janitor-handoff test runs on both Windows event loops.

The Linux image was based on the existing local Python 3.12 test image, with
missing Zigbee test-fixture dependencies installed in a separate image. Test
runs disabled Docker networking except loopback, mounted source read-only and
used a temporary `DATA_DIR`. The first old-image run failed during fixture setup
because `zigpy` was missing; that was an environment failure, not a passing run.

## Reproduce

Run from the repository root with the project Python environment. On this
Windows checkout `python` means the main checkout's `venv/Scripts/python.exe`,
including when working from a linked worktree.

```powershell
python -m ruff check backend/
python -m pytest `
  backend/tests/unit/services/test_camera_tls_proxy.py `
  backend/tests/unit/services/test_camera_tls_lifecycle.py `
  backend/tests/unit/services/test_camera_attempt_lifecycle.py `
  backend/tests/unit/test_camera_capture_diagnostics.py `
  backend/tests/unit/test_capture_pid_tracking.py `
  backend/tests/unit/test_camera_single_reader.py `
  backend/tests/unit/test_camera_stderr_summary.py `
  backend/tests/unit/test_camera_stream_id_isolation.py `
  backend/tests/unit/test_log_credential_redaction.py `
  backend/tests/unit/services/test_camera_fanout.py `
  backend/tests/unit/services/test_ffmpeg_stderr_drain.py `
  backend/tests/unit/services/test_external_camera.py `
  backend/tests/unit/services/test_camera_diagnose.py `
  backend/tests/integration/test_camera_api.py -q --tb=short -rs
```

Linux, with the project dependencies, pytest and uvloop installed:

```sh
python -m pytest \
  backend/tests/unit/services/test_camera_tls_lifecycle.py \
  backend/tests/unit/services/test_camera_attempt_lifecycle.py \
  -q --tb=short -p no:cacheprovider
```

The `run` fixture creates fresh Proactor/Selector loops on Windows and fresh
asyncio/uvloop loops on Linux. Missing uvloop produces an explicit skip, which
does **not** satisfy the uvloop acceptance requirement.

## Coverage and limits

| Acceptance | Runtime coverage |
| --- | --- |
| T01–T03 | Empty/repeated close, weak server lifetime, multiple active connections, stalled handshake |
| T04–T06 | Client/server EOF or reset, silent close notification before/after client exit, dead-handle RuntimeError |
| T07–T09 | Pre-start handler cancellation, late accept, shared coordinator/deadline, repeated caller cancellation, sticky deadline failure |
| T10–T11 | DESCRIBE/SETUP/PLAY and untouched Digest header, binary RTP both directions, slotted server and actual uvloop |
| T12 | Spawn failure and cancellation for all four owners; capture timeout, cleanup failure, process/drain error and cancellation; real local subprocess reaping |
| T13–T14 | EOF/timeout retry followed by immediate failure; old transports closed before next spawn; disconnect/cancel during backoff; generator close |
| T15–T16 | Repeated cycles, independent proxies, original single-reader/fan-out/PID/stream-ID regressions, credential-safe logs |

Resource assertions run **before fixture cleanup**. Silent peers speak real TLS
using `SSLObject`/memory BIO and deliberately ignore later TLS records. Barriers
and fake processes isolate races; one test also terminates and reaps a real
local Python subprocess. Deadline fault injection proves failure reporting and
retained ownership when even abort completion cannot be confirmed.

This proves local resource ownership and retry ordering. It does not prove that
printer firmware immediately releases its internal RTSP session, identify the
cause of every `INVALIDDATA` response, or reproduce the farm's exact
`Task was destroyed but it is pending` warning. Hardware-specific TLS and VAAPI
behavior still requires a designated camera and a separate smoke-test record.
