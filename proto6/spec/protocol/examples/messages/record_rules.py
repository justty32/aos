"""tick 紀錄的跨欄位規則（schema 表達不了的）。validate.py 驗範例、tests/_tick_util.py 驗實際輸出，共用這一份。

只用標準函式庫。回錯誤訊息清單，空清單＝通過。位置上界只在 ended:true 才驗：
格中 before_kind 先於任務跑（ran 還沒加），skipped 又收尾才寫，進行中的位置可以超過 ran。
"""


def _ints_increasing(values, strict=True):
    if any(not isinstance(i, int) or isinstance(i, bool) for i in values):
        return False
    return values == (sorted(set(values)) if strict else sorted(values))


def record_errors(rec):
    """rec：展開後的完整紀錄（tick-record.schema.json 的根）。"""
    if not isinstance(rec, dict):
        return []
    errors = []
    tasks = [t for t in rec.get('tasks') or [] if isinstance(t, dict)]
    skipped = [t for t in rec.get('skipped') or [] if isinstance(t, dict)]
    hooks = rec.get('hooks') if isinstance(rec.get('hooks'), dict) else {}
    idx = [t.get('index') for t in tasks]
    sidx = [t.get('index') for t in skipped]
    if not _ints_increasing(idx):
        errors.append('task index not strictly increasing')
    if not _ints_increasing(sidx):
        errors.append('skipped index not strictly increasing')
    if set(map(repr, idx)) & set(map(repr, sidx)):
        errors.append('task both ran and skipped')
    for point in ('before_all', 'after_all'):
        hidx = [h.get('index') for h in hooks.get(point) or [] if isinstance(h, dict)]
        if not _ints_increasing(hidx):
            errors.append(f'{point} index not strictly increasing')
    tidx_all = []
    for point in ('before_kind', 'after_task', 'after_kind', 'after_every_task'):
        tidx = [h.get('task_index') for h in hooks.get(point) or [] if isinstance(h, dict)]
        if not _ints_increasing(tidx, strict=False):
            errors.append(f'{point} task_index decreasing')
        else:
            tidx_all += tidx
    ran = rec.get('ran')
    if rec.get('ended') is True and isinstance(ran, int) and not errors:
        seen = ran + len(skipped)           # 收尾時看得到的位置：跑過的＋被 kinds 擋掉的
        if idx and idx[-1] >= seen:
            errors.append('task index not below ran + skipped')
        if sidx and sidx[-1] >= seen:
            errors.append('skipped index not below ran + skipped')
        if tidx_all and max(tidx_all) >= seen:
            errors.append('hook task_index not below ran + skipped')
    return errors
