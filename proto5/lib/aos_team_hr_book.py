"""HR 家：等級與規模常數、預設政策、HR 家與鎖、policy.json、薪資表 salary.json、試用紀錄 trials.jsonl。"""
import contextlib
import datetime
import fcntl
import json
import os
from pathlib import Path

from aos_team_format import TeamError, read_json, write_json


TIERS = ('程式', '笨', '中', '強')          # 由便宜到貴；「程式」＝這個位子已經不用模型
STAGES = {                 # 董事 09-25：先當新創（小），擴張後才用大的；policy.json 寫 stage 選一組，寫了數字就蓋過
    'startup': {'regular_max': 10, 'cpu_max': 20, 'llm_cpu_max': 5},
    'grown': {'regular_max': 100, 'cpu_max': 200, 'llm_cpu_max': 25},   # 董事 09-25 14:20：llm cpu 總額 20→25
}
DEFAULT_POLICY = {
    '_metainfo': {'_type': 'aos_hr_policy', '_version': 1},
    'stage': 'startup',        # startup＝新創（預設）、grown＝擴張後
    'regular_max': 10,         # 正式員工（employment=regular）人頭上限，跨所有登記的團隊
    'cpu_max': 20,             # 全公司 kernel 開著的 cpu（不含 llm 池）
    'llm_cpu_max': 5,          # 全公司 llm 池的 cpu
    'margin': 5,               # 調薪：試用分數 ≥ 強模型基準 − margin（滿分 100）
    'expand': {'backlog_min': 3, 'qc_below': 80},   # 擴編理由的門檻（spec/team/hr.md〈擴編規則〉）
}
DEFAULT_TIERS = {'chatgpt-gpt-6-astra': '強', 'claude-opus-5': '強', 'claude-fable-5-1': '強',
                 'chatgpt-gpt-5.6-sol': '中', 'claude-sonnet-5': '中',
                 'deepseek-chat': '笨', 'chatgpt-gpt-5.6-luna-nothink': '笨'}
TERMINAL = ('done', 'failed', 'cancelled')
CLI = Path(__file__).resolve().parent.parent / 'cli' / 'aos-team'


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


# --------------------------------------------------------------- HR 家 ----

def hr_home(given=None, env=None):
    env = os.environ if env is None else env
    if given:
        return Path(os.path.abspath(os.path.expanduser(given)))
    if env.get('AOS_HR_HOME'):
        return Path(os.path.abspath(os.path.expanduser(env['AOS_HR_HOME'])))
    k = env.get('AOS_KERNEL_HOME')
    if k and os.path.isabs(k):
        return Path(k) / 'hr'
    raise TeamError('Usage', '找不到 HR 家：給 --hr DIR，或設 AOS_HR_HOME，或設 AOS_KERNEL_HOME（用 $AOS_KERNEL_HOME/hr）')


@contextlib.contextmanager
def hr_lock(hr):
    hr.mkdir(parents=True, exist_ok=True)
    with open(hr / '.hr.lock', 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_policy(hr):
    p = Path(hr) / 'policy.json'
    out = json.loads(json.dumps(DEFAULT_POLICY))
    if not p.exists():
        return out
    raw = read_json(p)
    if not isinstance(raw, dict):
        raise TeamError('FormatInvalid', '%s 要是物件' % p)
    stage = raw.get('stage', 'startup')
    if stage not in STAGES:
        raise TeamError('FormatInvalid', '%s.stage 要是 %s 之一' % (p, '／'.join(STAGES)))
    out['stage'] = stage
    out.update(STAGES[stage])
    for k, v in raw.items():
        if k in ('_metainfo', 'stage'):
            continue
        if k not in DEFAULT_POLICY:
            raise TeamError('FormatInvalid', '%s：不認得的欄位 %s（可用：%s）' % (p, k, '、'.join(
                x for x in DEFAULT_POLICY if x != '_metainfo')))
        if k == 'expand':
            if not isinstance(v, dict):
                raise TeamError('FormatInvalid', '%s.expand 要是物件' % p)
            out['expand'].update(v)
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            raise TeamError('FormatInvalid', '%s.%s 要是不小於 0 的數字' % (p, k))
        else:
            out[k] = v
    return out


def empty_salary():
    return {'_metainfo': {'_type': 'aos_hr_salary', '_version': 1}, 'tiers': dict(DEFAULT_TIERS), 'positions': {}}


def load_salary(hr):
    p = Path(hr) / 'salary.json'
    if not p.exists():
        return empty_salary()
    raw = read_json(p)
    if not isinstance(raw, dict) or not isinstance(raw.get('positions', {}), dict) \
            or not isinstance(raw.get('tiers', {}), dict):
        raise TeamError('FormatInvalid', '%s：要有 tiers（模型代號→等級）與 positions（位子→一列）兩個物件' % p)
    for code, t in raw.get('tiers', {}).items():
        if t not in TIERS:
            raise TeamError('FormatInvalid', '%s.tiers.%s：等級要是 %s 之一' % (p, code, '／'.join(TIERS)))
    raw.setdefault('tiers', {})
    raw.setdefault('positions', {})
    return raw


def save_salary(hr, sal):
    Path(hr).mkdir(parents=True, exist_ok=True)
    write_json(Path(hr) / 'salary.json', sal, indent=2)


def tier_of(sal, model):
    if model is None:
        return '程式'
    return sal.get('tiers', {}).get(model)


def cheaper(a, b):
    """等級 a 比 b 便宜？（不明＝False）"""
    return a in TIERS and b in TIERS and TIERS.index(a) < TIERS.index(b)


def read_trials(hr):
    p = Path(hr) / 'trials.jsonl'
    out = []
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and 'id' in rec:
                out.append(rec)
    return out


def append_trial(hr, rec):
    with open(Path(hr) / 'trials.jsonl', 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')


def next_trial_id(hr):
    nums = [int(r['id'][3:]) for r in read_trials(hr) if str(r['id']).startswith('tr-') and r['id'][3:].isdigit()]
    d = Path(hr) / 'trials'
    if d.is_dir():
        nums += [int(p.name[3:]) for p in d.iterdir() if p.name.startswith('tr-') and p.name[3:].isdigit()]
    return 'tr-%04d' % (max(nums, default=0) + 1)
