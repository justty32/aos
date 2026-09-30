"""aos_inst：proto6 inst 第 1 版的找檔、身分先行、指示詞展開與（可選的）開程序。

對應 spec：proto6/spec/base/inst.md；指示詞沿用 proto5/spec/directives/。
解析（target／identity／directives／plan）與開程序（spawn）分開，spawn 可以整個不用。
用法與公開 API 見同資料夾 README.md。
"""
from .errors import EXIT_REFUSED, EXIT_USAGE, InstError
from .identity import (Authorizer, Snapshot, check_resolved_user, check_unchanged, grant_only,
                       lookup_uid, raw_user, read_snapshot, snapshot_from_bytes,
                       snapshot_from_obj)
from .plan import KNOWN_KEYS, OPTIONS, Plan, Stream, load_plan, load_plan_obj, resolve_plan
from .target import Source, find_inst, node_dir

__all__ = [
    "InstError", "EXIT_REFUSED", "EXIT_USAGE",
    "Source", "find_inst", "node_dir",
    "Snapshot", "read_snapshot", "snapshot_from_bytes", "snapshot_from_obj", "raw_user", "lookup_uid",
    "check_resolved_user", "check_unchanged", "Authorizer", "grant_only",
    "Plan", "Stream", "OPTIONS", "KNOWN_KEYS", "resolve_plan", "load_plan", "load_plan_obj",
]
