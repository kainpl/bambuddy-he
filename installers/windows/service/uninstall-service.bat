@echo off
REM Stop and deregister the BamDude services.
REM
REM Called from Inno Setup's [UninstallRun] section. Argument:
REM   %1 = install dir (e.g. C:\Program Files\BamDude)
REM
REM Removes the BamDude service and, if it was registered, the bundled
REM PostgreSQL service (BamDudePostgres). The data directory is NOT touched
REM here - the uninstaller asks about that separately.

setlocal

set "INSTALL_DIR=%~1"
set "NSSM=%INSTALL_DIR%\bin\nssm.exe"
set "PG_SERVICE=BamDudePostgres"

REM Stop BamDude first (it depends on the PostgreSQL service when embedded).
REM Best-effort: an already-stopped or missing service returns non-zero.
"%NSSM%" stop BamDude 2>nul
"%NSSM%" remove BamDude confirm 2>nul

REM Stop and delete the bundled PostgreSQL service if this install registered
REM one. A clean stop lets it checkpoint; sc delete removes the registration.
REM Both no-op quietly when there is no such service (SQLite / external / child
REM installs never created it). Uses sc so it does not depend on the wheel,
REM which the file-removal step may already be deleting.
net stop %PG_SERVICE% 2>nul
sc delete %PG_SERVICE% 2>nul

echo [uninstall-service] BamDude services deregistered
endlocal
exit /b 0
