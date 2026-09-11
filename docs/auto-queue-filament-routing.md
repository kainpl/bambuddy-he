# AutoQueue filament routing

AutoQueue reads the selected plate from the sliced 3MF and checks every filament channel used by that plate. Printers of the same model can have different feed configurations. The form shows separate groups for AMS connected, no AMS, and unknown configuration, with compatible and ready counts shown separately.

## Choosing the rules

- **Automatic source** allows any complete supported combination of AMS and external feeds.
- **AMS only** requires AMS sources for every used channel.
- **External only** allows supported external feeds even when the printer has an AMS attached.
- **Require exact colors**, off by default, requires the file's colors. With it off, exact matches are preferred, while another color of the required material may be used. A color pinned on an individual channel remains required.

The number of copies does not change these choices. Different channels always need distinct physical sources. Multicolor jobs remain supported: two channels cannot be assigned to a single external spool. Supported dual-nozzle printers can use separate external feeds or AMS on one nozzle and external on the other when the file and live printer configuration establish the correct nozzle bindings. This applies to the shared model capability registry, including models beyond X2D.

## Files and waiting

A whole-file choice is accepted when the file contains one unambiguous printable plate; its actual plate number is retained. A multi-plate file needs an explicit selection. Missing G-code, incomplete filament usage, or missing nozzle bindings produce a source error before a new job is added. Project quantities and recipe whole-file selections are preserved; queued jobs receive the resolved printable plate.

A valid job can wait when no printer is currently compatible or ready. A temporary failure to obtain live compatibility information does not prevent adding a valid source. The preview is advisory and does not reserve a printer.

The server checks routing again before preparing a print and immediately before publishing its start command. A changed spool, connection, source file, or queue claim can defer the attempt. A queued job returns to waiting with a reason; a direct Print Now refusal does not schedule a future print. An aborted preparation is excluded from print and production counts, and its original source is retained.

## Editing, copying, and existing queues

If a queued source disappears, cannot be read, or times out, that job is marked **File error** and skipped. Other jobs continue; the printer queue is not paused and this does not count as a failed physical print. AutoQueue keeps the failed row visible, and a printer's queue shows it under Issues. Restore access, then use **Retry**. AutoQueue checks the file before returning the same job to pending; restoring the share alone does not restart a failed job. Busy printers and unavailable filament still wait normally.

Files indexed from an external folder remain at their original paths: queueing does not make independent copies. Keep the source available until the pending jobs have been sent. When moving laptop/SMB files to local NAS storage, preserve the path and folder structure inside the container for existing jobs.

Routing choices are stored with each printer-queue job. Removing its original AutoQueue row does not remove its rules. Editing only its schedule, cloning, retrying, and repeating preserve those choices. Explicit physical slot selections remain pinned; moving them to a different printer or plate requires a new mapping answer. File-specific color pins cause each following file in a grouped add to be shown for review.

Existing rows are migrated using their stored data only. Old automatic jobs that explicitly disabled AMS keep the external-only restriction. A physical AMS mapping with an inconsistent old `use_ams` flag remains physical intent. Missing or unrecognized policy evidence requires review instead of silently relaxing the rules.

Raw G-code and server-created calibration jobs keep their separate workflows. Full-slot and unsliced-file previews used for slicing also keep their existing contract.

Validation and the implementation acceptance map are in [the routing test matrix](testing/auto-queue-filament-routing.md). Tests use synthetic files and mocked device transport. Actual firmware behavior and the original farm incident require separate observation on hardware.
