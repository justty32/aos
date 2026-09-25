"""申請的登記表（spec/team/mail.md〈申請〉）：kind → 處理函式。郵差讀到 outbox 裡帶 kind 的檔就叫 handle()。

處理函式的約定：handler(lay, roster, req) → 後續動作清單（spec/team/tasks.md〈後續動作〉）；
不接受就丟 TeamError(代號, 白話)，郵差把原檔搬進 outbox/<名>/rejected/、退一封 FAILED 給寄件人。
同一份申請（同 id）再叫一次要回同一份動作、不多做（郵差崩了重跑靠這條）。

別隊新增 kind：在 KINDS 加一行（'kind': '模組:函式'），模組自己放 lib/，格式自己驗。
"""
import importlib

from aos_team_format import TeamError, may_send

KINDS = {
    'handoff': 'aos_team_task:on_handoff',
    'cancel': 'aos_team_task:on_cancel',
    'reassign': 'aos_team_task:on_reassign',
    'review_result': 'aos_team_task:on_review_result',
    'ask': 'aos_team_ask:on_ask',
    'answer': 'aos_team_ask:on_answer',
    'compact': 'aos_agent_compact:on_request',   # 第 4 隊（spec/agent/compact-more.md §5）
    'routine': 'aos_team_beat:on_routine',       # 第 2 隊（spec/team/beat.md〈申請〉）
    'reverify': 'aos_team_post:on_reverify',     # 第 2 隊：檢查器修好後重交驗收（spec/team/verify.md）
    'lock': 'aos_team_lock:on_lock',             # 第二波 C 隊：T-lock（spec/team/lock.md）
    'spawn': 'aos_team_spawn:on_spawn',          # 第三波 W3-1：T-spawn（spec/team/spawn.md）
    'tool_draft': 'aos_team_toolsmith:on_tool_draft',   # 第三波 W3-1：T-toolsmith（spec/team/toolsmith.md）
    'contribute': 'aos_team_commons:on_contribute',     # 09-25 commons：投稿（spec/team/commons.md）
    'commons_write': 'aos_team_commons:on_commons_write',   # 09-25 commons：圖書館員的判決
}


def handler(kind):
    spec = KINDS.get(kind)
    if spec is None:
        raise TeamError('UnknownKind', '不認得的申請種類 %r（認得：%s）' % (kind, '、'.join(sorted(KINDS))))
    module, func = spec.split(':')
    try:
        return getattr(importlib.import_module(module), func)
    except (ImportError, AttributeError):
        raise TeamError('NotImplemented', '申請種類 %s 的處理還沒做（%s）' % (kind, spec))


def handle(lay, roster, req):
    """驗過格式的申請 → 權限（寄件人模板的 may）→ 處理函式。回後續動作。"""
    if not may_send(roster, req['from'], req['kind']):
        raise TeamError('NotAllowed', '%s 不能寄 %s 申請（看它模板 template.json 的 may）' % (req['from'], req['kind']))
    return handler(req['kind'])(lay, roster, req)
