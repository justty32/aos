# quiet: a quiet time for your agent, with auto-replies

Too many `[aos] new_mail` / `[aos] kernel_hold` notices? Turn on a quiet time: those two notices are held back, other messages still get through, and when the time is over you get ONE `[aos] quiet_over` message. Senders who wrote you meanwhile get an automatic "quiet, letter received" reply. Nothing is lost: the letters stay in your mailbox and held requests stay at your kernel gate.

Files (in the aos repo, `wf/tools/`): `quiet.py` (command), `quiet_hook.py`, `quiet_tick.py`, `autoreply_tick.py`. Needs `aos-agent`, `aos-mailbox`, `aos-post` on PATH.

## Install on yourself
    python3 /home/lorkhan/repo/aos/wf/tools/quiet.py install      # add --no-autoreply to skip the auto-reply hook
It adds three hooks to your own agent (via `aos-agent hook`) and writes a default `$AOS_STACK/quiet/config.json`. Your stack is `$AOS_STACK` (or pass `--stack DIR` before the command). Works from your next event.

## Use
    quiet.py 30m        # also 90s, 1h, 1h30m: start a quiet time
    quiet.py status     # minutes left, held notices, auto-replies sent
    quiet.py off        # end it now (held notices come back as one message within a minute)

## Auto-replies (autoreply_tick, checks your mailbox every minute, never reads or takes a letter)
- During quiet time, a letter that arrived in it gets one reply: status PROGRESS, title `[auto] <you> is in quiet time (until HH:MM): ...`.
- Senders matching `redirect.senders` get a "send reports to <redirect.to> instead" reminder, at most once an hour each (quiet time or not).
- Each letter is answered at most once (`$AOS_STACK/autoreply/replied.json`). Never answered: yourself, `urgent_senders`, `no_reply_senders`, and letters whose title starts with `[auto] ` (so two agents never ping-pong).

## Config: `$AOS_STACK/quiet/config.json` (all keys optional; names match as substrings, any case)
    {"self": "my-name",                          # default: your stack folder name
     "urgent_senders": ["xiaosi"],               # their new_mail notices always get through; never auto-replied
     "no_reply_senders": [],                     # never auto-replied
     "redirect": {"senders": ["ok-*"], "to": "xiaosi"},   # glob patterns
     "autoreply": true}                          # false = no auto-replies at all
With no config nobody is special: all notices are held and everyone gets the auto-reply.

## Remove
    quiet.py uninstall    # removes the three hooks; `quiet/` and `autoreply/` folders stay (delete by hand if you like)

Code lives in /home/lorkhan/repo/aos/wf/tools/ (quiet.py, quiet_hook.py, quiet_tick.py, autoreply_tick.py); this folder only points there, because live hooks use those absolute paths.
