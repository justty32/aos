# Stopping yourself: self_ctl

Tool `self_ctl` stops, pauses, puts to sleep or removes you, the agent calling it. To do this to another agent use `agents_ctl` (see `aos/agents.json#/agents_ctl`). Every op returns as soon as the request is sent.

- `{"op": "stop"}`: you stop at the end of this step, maybe before you answer. Your stack is kept. Someone runs `aos-agent ctl start` and you carry on from there.
- `{"op": "pause"}`: you hold still after this step. Only someone else's `aos-agent ctl resume` lets you go on.
- `{"op": "sleep"}`: you stop right away, even in the middle of this turn. `aos-agent ctl wake` or a daemon restart brings you back.
- `{"op": "rm"}`: you leave the daemon table right away; your stack is kept. Only `aos-agent ctl add` brings you back.
- `{"op": "rm", "purge": true}`: also deletes your stack (your history and everything in it). This cannot be undone.

Use it when your work is done or you must not go on. Errors: ArgumentsBad, OpUnknown, PhaseBad, CtlRejected, DaemonMissing, InstanceMissing.
