"""daemon_ctl：daemon 的找址、狀態位址（設了 AOS_KERNEL 先問再讀）、名單自檢清理、寄信回信、門鈴、子 loop 控制與停 daemon 本身的共用介面。"""
PROG = "aos-daemon-ctl"

from .base import (
    Fail,
    Already,
)
from .entry import (
    find_loop,
    check_limits,
    add_letter,
    registered_envs,
    PARENT_ENV,
    NOTIFY_ENV,
    typed_kept,
    path_json,
    AsIs,
    resolve_here,
)
from .table import (
    find_daemon,
    names_of,
    state,
    rows,
    row_of,
    cell_of,
    supervisor,
    duration,
    inspect_row,
    last_change,
    leftovers,
    prune_candidates,
)
from .ctl import (
    need_ctl,
    need_phase,
    write_ctl,
    next_seq,
    put_ctl,
    SHUTDOWN_S,
    shutdown,
)
from .post import (
    mailbox_of,
    send,
    regret,
    reply_box,
    take_reply,
    ask,
    ping,
    wait_taken,
)

from .poke import poke, MODES, read_state, check_alive
from .state_path import (
    TableFile,
    via_kernel,
    kernel_reply_box,
    state_path,
    rows_at,
)
