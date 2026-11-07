"""daemon_ctl：daemon 的找址、名單自檢清理、寄信回信與子 loop 控制共用介面。"""
PROG = "aos-daemon-ctl"

from .base import (
    STATE,
    PATHS,
    NAMES,
    Fail,
)
from .entry import (
    abs_target,
    read_loop,
    read_entry_json,
    pointer,
    find_loop,
    loop_spec,
    LIMIT_INTS,
    check_limits,
    add_letter,
)
from .table import (
    find_daemon,
    names_of,
    table,
    resolve,
    state,
    rows,
    row_of,
    cell_of,
    supervisor,
    duration,
    inspect_row,
    last_change,
    prune_candidates,
)
from .ctl import (
    need_ctl,
    PHASE_OK,
    PHASE_HINT,
    need_phase,
    write_ctl,
    APPLY_S,
    wait_applied,
)
from .post import (
    _post,
    mailbox_of,
    send,
    regret,
    _letter,
    _letters,
    _claim,
    _reply_lock,
    reply_box,
    take_reply,
    ask,
    ping,
    wait_taken,
)
