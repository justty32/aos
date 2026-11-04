"""固化建議（spec/team/crystal.md，第三波 W3-2）：aos-team crystal。

讀 team/route.log＋任務表＋投遞紀錄，找「門房沒中、領隊每次都開同一種單」的句型，
機械地產 routes.json 的**候選**規則，寫成一份完整的規則檔提案給人批（不自動生效）：
  aos-team crystal [--min N] [--json] [--out FILE]
  aos-team crystal --suggest-with-llm [--model ALIAS]   # 改叫模型歸納一次，一樣機械檢查兜底、只寫提案
批法：aos-team route test --file 提案 → aos-team route save 提案。
這個檔留主體 crystal、印法與命令列；實作分在 aos_team_crystal_stats／rules／llm，這裡匯出外部用到的名字。
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import time

import aos_team_format as fmt
from aos_team_format import Layout, TeamError

from aos_team_crystal_stats import classes, collect, make_pattern, REASONS, skeleton, SLOT_PATTERN
from aos_team_crystal_rules import (
    _failures, _templ, assemble, backtest, check_candidate_request, mechanical_candidates,
    probe_rule, screen_probes
)
from aos_team_crystal_llm import llm_candidates, screen_llm


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def out_path(lay, out, force=False):
    """提案寫到哪（審查 M2）：不准是正式的 team/routes.json（別名、符號連結、硬連結都算）；
    沒給＝team/crystal/proposal-<時間>-<奈秒>-<pid>.json（唯一）；給了而且已經在＝要 --force。"""
    if out is None:
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        out = lay.team / 'crystal' / ('proposal-%s-%09d-%d.json' % (stamp, time.time_ns() % 10 ** 9, os.getpid()))
    out = Path(os.path.abspath(out))
    if os.path.realpath(out) == os.path.realpath(lay.routes) or _same_file(out, lay.routes):
        raise TeamError('Refused', '--out %s 就是生效中的規則檔 %s；提案要另存，批准走 aos-team route save' % (out, lay.routes))
    if out.is_dir():
        raise TeamError('Usage', '--out %s 是資料夾，要給檔名' % out)
    if out.exists() and not force:
        raise TeamError('AlreadyExists', '%s 已經在，不覆蓋（換個檔名，或加 --force）' % out)
    return out


# ------------------------------------------------------------------ 主體 ----

def crystal(team_dir, min_count=2, out=None, use_llm=False, model=None, asker=None, force=False):
    lay, rows, stats, falls = collect(team_dir)
    out = out_path(lay, out, force)          # 先檢查，免得叫完模型才發現寫不了
    base_obj = fmt.read_json(lay.routes) if lay.routes.exists() else {}
    base_obj = dict(base_obj)
    base_obj.setdefault('_metainfo', {'_type': fmt.ROUTES_TYPE, '_version': 1})
    taken = {r.get('name') for r in base_obj.get('routes', [])}
    cls = classes(falls)
    res = {'stats': stats, 'fallthrough': falls, 'classes': cls, 'min': min_count,
           'source': 'llm' if use_llm else 'mechanical', 'candidates': [], 'skipped': [], 'dropped': [],
           'proposal': None, 'llm': None}
    if use_llm:
        rules, got, err = llm_candidates(falls, base_obj, min_count, model, asker)
        res['llm'] = {'usage': got.get('usage'), 'ms': got.get('ms'), 'alias': got.get('alias'),
                      'model': got.get('model'), 'error': err, 'raw_count': len(rules)}
        screened, res['dropped'] = screen_llm(rules, falls, cls, min_count, taken)
        own = {r['name']: sk for r, sk in screened}
        cands = [r for r, _ in screened]
    else:
        pairs, res['skipped'] = mechanical_candidates(cls, falls, min_count, taken)
        cands = []
        own = {}
        for c, r in pairs:
            err = check_candidate_request(r)
            if err:
                res['dropped'].append({'name': r['name'], 'why': err})
                continue
            cands.append(r)
            own[r['name']] = {c['skeleton']}
    cands = screen_probes(cands, res['dropped'])
    obj, dropped = assemble(base_obj, cands)
    res['dropped'] += dropped
    names = [r['name'] for r in obj['routes'] if r['name'] in own]
    bt = backtest(obj, names, rows, own) if names else {}
    if use_llm:                              # 模型版：回測誤觸別類的丟掉（再組一次）
        bad = [n for n in names if any(e['misfire'] for e in bt[n]['eats'])]
        if bad:
            for n in bad:
                res['dropped'].append({'name': n, 'why': '回測誤觸別類：' + '、'.join(
                    '「%s」' % e['text'] for e in bt[n]['eats'] if e['misfire'])})
            obj, more = assemble(base_obj, [r for r in obj['routes'] if r['name'] in names and r['name'] not in bad])
            res['dropped'] += more
            names = [r['name'] for r in obj['routes'] if r['name'] in own]
            bt = backtest(obj, names, rows, own) if names else {}
    for r in obj['routes']:
        if r['name'] in names:
            res['candidates'].append({'rule': r, 'backtest': bt[r['name']]})
    if names:
        meta = dict(obj.get('_metainfo') or {})
        meta['crystal'] = {'candidates': names, 'source': res['source'], 'made_at': fmt.now_iso(),
                           'note': '候選不會自動生效：aos-team route test --file 這個檔 → aos-team route save 這個檔'}
        obj['_metainfo'] = meta
        left = _failures(obj)                # 寫檔前整份再跑一次（審查 M3）
        if left:
            raise TeamError('RoutesFailed', '提案整份例句沒全過（%s），沒寫檔' % '、'.join(sorted(left)))
        out = out_path(lay, out, force)      # 叫模型那段時間裡可能有人建了同名檔
        out.parent.mkdir(parents=True, exist_ok=True)
        if force:
            fmt.write_json(out, obj, indent=2)
        elif not fmt.write_new(out, obj, indent=2):
            raise TeamError('AlreadyExists', '%s 已經在，不覆蓋（換個檔名，或加 --force）' % out)
        res['proposal'] = str(out)
    return res


def _cut(text, n=50):
    text = ' '.join(str(text or '').split())
    return text[:n] + ('…' if len(text) > n else '')


def render(res):
    s = res['stats']
    lines = ['route.log：%d 句%s' % (s['lines'], '（另有 %d 行讀不懂，略過）' % s['bad_lines'] if s['bad_lines'] else '')]
    if s['by_rule']:
        lines.append('命中規則：' + '、'.join('%s %d 次' % kv for kv in sorted(s['by_rule'].items())))
    ft = s['fallthrough']
    lines.append('落穿 %d 次：%s' % (sum(ft.values()), '、'.join('%s %d' % (label, ft.get(k, 0)) for k, label in REASONS)))
    lines.append('')
    lines.append('沒命中的句型（%d 類；只看「沒命中」的，否定詞、命中兩條的加規則也沒用）：' % len(res['classes']))
    for c in sorted(res['classes'], key=lambda c: -c['count']):
        mark = '  ← 領隊每次開同一種單' if c['same_kind'] and c['count'] >= 2 else ''
        lines.append('- %s  ×%d%s%s' % (c['skeleton'], c['count'], mark,
                                        '（其中 %d 句配信有歧義，不拿來產候選）' % c['doubtful'] if c['doubtful'] else ''))
        for it in c['items'][:3]:
            if it['tickets']:
                t = it['tickets'][0]
                k = t['kind']
                tk = '%s 開單給 %s，工作流 %s，驗收 %s：%s' % (t['id'], k['assignee'], k['workflow'],
                                                       '、'.join(k['done_when']) or '無', _cut(t['goal'], 40))
            else:
                tk = '沒對到領隊開的單' if it['letter'] else '對不上信（舊 log）'
            lines.append('    「%s」→ %s' % (_cut(it['text'], 40), tk))
        if len(c['items']) > 3:
            lines.append('    …另 %d 句' % (len(c['items']) - 3))
    lines.append('')
    if res['llm']:
        u = res['llm']
        lines.append('模型 %s（%s）：prompt %s、completion %s token，%s ms；回了 %d 條%s'
                     % (u['alias'], u['model'], (u['usage'] or {}).get('prompt_tokens', '?'),
                        (u['usage'] or {}).get('completion_tokens', '?'), u['ms'], u['raw_count'],
                        '；讀不懂：' + u['error'] if u['error'] else ''))
    for x in res['skipped']:
        lines.append('沒提：%s（%s）' % (x['skeleton'], x['why']))
    for x in res['dropped']:
        lines.append('丟掉：%s（%s）' % (x['name'], x['why']))
    if not res['candidates']:
        lines.append('沒有候選規則（出現 ≥ %d 次、領隊開的單一致的句型才會提）；沒寫提案檔。' % res['min'])
        return '\n'.join(lines)
    lines.append('候選規則 %d 條（%s；不會自動生效）：' % (len(res['candidates']),
                                             '模型歸納、機械檢查過' if res['source'] == 'llm' else '機械產生'))
    for c in res['candidates']:
        r, bt = c['rule'], c['backtest']
        lines.append('- %s：%s%s' % (r['name'], r['pattern'], '' if re.compile(r['pattern']).groupindex
                                      else '（整句照抄：只有同一句重複說，推不出哪裡會變）'))
        lines.append('    → 開單給 %s：%s' % (r['handoff']['assignee'], _cut(r['handoff']['goal'], 60)))
        lines.append('    例句 hit %d、miss %d，全過；回測 %d 句舊句子，新吃到 %d 句%s'
                     % (len(r['tests']['hit']), len(r['tests']['miss']), bt['checked'], len(bt['eats']),
                        '' if not bt['eats'] else '：' + '、'.join('「%s」%s' % (_cut(e['text'], 30),
                                                                     '（疑似誤觸）' if e['misfire'] else '')
                                                            for e in bt['eats'])))
    lines.append('')
    lines.append('提案（現有規則＋候選）：%s' % res['proposal'])
    lines.append('怎麼批：先看一眼，再')
    lines.append('  aos-team route test --file %s' % res['proposal'])
    lines.append('  aos-team route save %s' % res['proposal'])
    lines.append('不要的候選，從檔裡刪掉那條再批。')
    return '\n'.join(lines)


def cmd_crystal(team_dir, argv):
    ap = _Parser(prog='aos-team crystal',
                 description='固化建議：從 route.log＋領隊開的單找常落穿的句型，產候選規則提案（不自動生效）')
    ap.add_argument('--min', type=int, default=2, help='句型至少出現幾次才提候選（預設 2）')
    ap.add_argument('--json', action='store_true', help='印 JSON')
    ap.add_argument('--out', help='提案寫到哪（預設 team/crystal/proposal-<時間>-<奈秒>-<pid>.json；不准是 team/routes.json）')
    ap.add_argument('--force', action='store_true', help='--out 的檔已經在也覆蓋（team/routes.json 永遠不行）')
    ap.add_argument('--suggest-with-llm', action='store_true', help='改叫模型歸納一次（預設關；一樣機械檢查、只寫提案）')
    ap.add_argument('--model', help='模型代號（--suggest-with-llm 用；預設 default）')
    args = ap.parse_args(argv)
    if args.min < 1:
        raise TeamError('Usage', '--min 至少 1')
    if args.model and not args.suggest_with_llm:
        raise TeamError('Usage', '--model 要跟 --suggest-with-llm 一起用')
    lay = Layout(team_dir)
    if not lay.team.is_dir():
        raise TeamError('NotFound', '%s 不是團隊資料夾（沒有 team/）' % team_dir)
    from aos_agent_home import AgentError
    try:
        res = crystal(team_dir, args.min, args.out, args.suggest_with_llm, args.model, force=args.force)
    except AgentError as e:                  # 叫模型失敗（設定錯、端點不通、逾時）：照 aos-llm call 的代號
        raise TeamError(e.code, e.msg)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(render(res))
    return 0
