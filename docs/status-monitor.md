# Status monitor

[Українською](status-monitor.uk.md)

Open **Printers → Open monitor** or **Queue → Open monitor**. Move the new window to a second display and select **Full screen**. If the browser blocks popups, use the displayed **Open in a new tab** link. The working page stays available independently.

The monitor only displays information. Select a tile for details; signed-in users can open that printer or queue in the working application. **Show all** removes this temporary printer filter and restores the working page's saved filters.

## Reading the wall

Every tile has the same layout. Green means printing or preparation, red a serious active printer error, yellow a pause or intervention, blue plate clearance or an automatic waiting stage, and neutral idle, maintenance or offline. Text and icons identify the specific state.

**Attention first** puts errors, pauses and required intervention ahead of printing jobs, then orders jobs by remaining time. **ETA (job)** compares the current prints. **ETA (queue)** uses the server's forecast for all scheduled work on each printer. A paused queue can coexist with a running print. An empty queue can also coexist with a running print.

Job time and queue time are separate. Short times use minutes; compact times of an hour or more use `h:mm`. Queue forecasts are approximate (`≈`). `≥` means some jobs have unknown duration; `—` means no usable estimate. A countdown reaching zero waits for a printer update instead of declaring completion.

Location/tag grouping is independent of sorting. A printer with several tags appears in each matching group; counters count unique printers. **Needs attention** temporarily shows just intervention tiles. Press it again to restore the previous search/group settings.

**Auto** fits 50 tiles at 1920×1080 without scrolling, using text of at least 12 px. Smaller screens, larger tiles or grouping may need scrolling; the footer shows how many unique printers are fully visible.

## A TV without a user session

In **Settings → API Keys → Camera and monitor tokens**, create a **Status monitor** token. Creation requires API key creation, printer read and queue read permissions. The token grants read access to operational metadata for the entire non-archived fleet and both views. It does not grant printer control, cameras, filenames, job names, item identifiers, owners or network credentials.

Copy the TV URL when the token is created; the secret is only shown once. Open that URL on the TV. The default lifetime is 90 days, with a maximum of 365. Revoke it in the same panel; the screen clears on its next request. Expiry, revocation, owner deactivation or loss of the owner's read permissions also ends access.

The secret is carried in the URL fragment and a dedicated request header, not query parameters or local storage. Treat the complete TV URL as a credential. Use a separate token per display when independent revocation is useful.

## Freshness

The server snapshot refreshes every five seconds; queue forecasts refresh every thirty seconds while needed. A network failure preserves the last snapshot. After fifteen seconds without a successful snapshot, the wall marks it stale and freezes local estimates. Reconnection resumes updates.

Printer telemetry has its own freshness: a successful HTTP refresh cannot make old MQTT data fresh. Lost communication during known active work is an attention state; an offline idle printer is neutral. No telemetry after a restart means unknown history.

[Specification](specs/status-monitor.md) · [Implementation and validation](plans/status-monitor.md)
