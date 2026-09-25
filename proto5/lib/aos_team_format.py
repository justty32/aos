"""團隊共用格式（spec/team/）：資料夾佈局、名冊 team.json、信、申請、任務單、問題的讀驗，以及 id、時間、寫檔。

這支只管「長怎樣、對不對」，不管誰什麼時候做什麼：
- 郵差（第 2 隊）讀 outbox 用 read_outbox_file()、投信用 mail_message()；
- 申請的處理在 aos_team_requests（登記表）＋各 kind 的模組；
- 任務狀態機在 aos_team_task。
純標準庫；不叫模型。
這個檔留命令列驗檔（detect／main）；實作分在 aos_team_format_base／io／cmd／roster／letter／template，
這裡把外部用到的名字全部匯出（別的模組一律 `import aos_team_format as fmt` 用）。
"""

from aos_team_format_base import (
    _int, _metainfo, _opt_str, _str, ANY_ID, bad, BEAT, check_name, HUMAN, Layout, LIMIT_DEFAULTS,
    NAME, OUTBOX_ID, POST, QUESTION_TYPE, RESERVED, ROSTER_TYPE, ROUTES_TYPE, TASK_ID, TASK_TYPE,
    TeamError, TEMPLATE_TYPE, TEXT_LIMIT
)
from aos_team_format_io import (
    _zone, json_files, new_id, now_iso, parse_iso, read_json, short_time, write_json, write_new
)
from aos_team_format_cmd import cmd_allowed, RESERVED_MOUNTS
from aos_team_format_roster import (
    load_roster, members_by_template, project_dir, roster_lock, validate_roster
)
from aos_team_format_letter import (
    already_delivered, LETTER_KEYS, mail_filename, mail_message, next_number, read_outbox_file,
    render_header, REQUEST_COMMON, TERMINAL, validate_done_when, validate_letter,
    validate_question, validate_request, validate_ticket
)
from aos_team_format_template import (
    DEFAULT_NEGATIONS, load_template, may_send, member_may, ROUTE_RUN_FORBIDDEN, spawn_policy,
    template_dir, template_may, validate_routes, validate_template
)


# ------------------------------------------------------------ 命令列驗檔 ----

def detect(obj):
    """看檔的樣子決定用哪一種驗：_metainfo._type，或有 kind（申請）、有 status＋to（信）。"""
    meta = obj.get('_metainfo') if isinstance(obj, dict) else None
    kind = meta.get('_type') if isinstance(meta, dict) else None
    table = {ROSTER_TYPE: ('roster', validate_roster), TASK_TYPE: ('task', validate_ticket),
             QUESTION_TYPE: ('question', validate_question), TEMPLATE_TYPE: ('template', validate_template),
             ROUTES_TYPE: ('routes', validate_routes)}
    if kind in table:
        return table[kind]
    if isinstance(obj, dict) and 'kind' in obj:
        return 'request', validate_request
    if isinstance(obj, dict) and 'status' in obj and 'to' in obj:
        return 'letter', validate_letter
    return None, None


def main(argv=None):
    import sys
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        print('用法：python3 aos_team_format.py 檔…  （驗名冊、信、申請、任務單、問題、模板、門房規則）')
        return 2
    failed = 0
    for p in paths:
        try:
            obj = read_json(p)
            name, fn = detect(obj)
            if fn is None:
                raise TeamError('Unknown', '%s 看不出是哪種檔（沒有 _metainfo._type，也不像信或申請）' % p)
            fn(obj, str(p))
            print('ok  %-8s %s' % (name, p))
        except TeamError as e:
            failed += 1
            print('bad %s: %s' % (e.code, e.msg))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
