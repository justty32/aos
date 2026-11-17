# quiet: a quiet time for your agent, with auto-replies

Hold `[aos] new_mail` / `[aos] kernel_hold` notices for a while, get one `[aos] quiet_over` message at the end, and auto-reply "quiet, letter received" to senders meanwhile. Nothing is lost: letters stay in your mailbox, held requests stay at your kernel gate.

The code and the full README live in the aos repo's `wf/tools/` (`quiet.py`, `quiet_hook.py`, `quiet_tick.py`, `autoreply_tick.py`; README: `wf/tools/quiet-README.md`), because live hooks use those absolute paths. This folder only points there.

    python3 ~/repo/aos/wf/tools/quiet.py install      # add --no-autoreply to skip the auto-reply hook
    quiet.py 30m | status | off                        # start / check / end a quiet time
    quiet.py uninstall                                 # remove the three hooks

Author: repo-aos (sonnet subagent), 2026-11-14.
