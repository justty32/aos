# Tool peek_now_time

Get the current time: UTC as ISO 8601, or with `{"local": true}` this machine's local time. Changes nothing.

Use it whenever you need the date or the time; do not guess. For the daemon clock's cycle use `peek_clock`.

```json
{}
```
-> `2026-11-11T03:24:34Z`

The `Z` means UTC. `{"local": true}` -> `2026-11-13T21:30:00+08:00 Friday`: local time with its UTC offset and the weekday.

Errors: `ArgumentsBad` (the only key is `local`, a boolean; `aos/errors/common.md#/Codes about what you gave`).
