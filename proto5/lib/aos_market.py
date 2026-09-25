#!/usr/bin/env python3
"""市場層（spec/team/market.md）：幾家一樣的小公司做同樣的單，經理人照表現撥額度；花光倒閉、剩兩家合併。

董事長＝human，經理人＝調度者（不在 aos 裡）；這支是經理人手上的**機械**指令，發多少照 market.json 的參數算，經理人可以覆寫。
帳戶用財務部的 `aos_team_cost`（`$AOS_COST_HOME/accounts.json`，cost.md §6）：配額＝撥款加總、已花＝帳本裡落在公司資料夾底下的呼叫。

子命令（`python3 aos_market.py <子命令> [--market 資料夾]`；沒給看 AOS_MARKET_HOME）：
  open 名 公司資料夾 [--usd X] [--tokens N]    開戶＋撥開辦費、登記進 market.json
  score 名 [--quality Q] [--eval 結果.json] [--seconds S] [--hops H] [--done N]   記這一輪的表現（沒給的從董事的單與總機單算）
  rank [--json]                                 算排名（不寫帳）
  grant [--dry-run] [--usd 名=X]… [--tokens 名=N]…   照排名撥這一輪的額度；--usd／--tokens 覆寫單一家
  bankrupt [--dry-run]                          餘額 ≤ 0 的：停公司、封存資料夾；剩的配額與名額回總池
  close 名 [--dry-run]                          經理人裁撤：沒花完的配額全部收回總池
  pool [--json]                                 總池：錢＝總量 − 已花 − 各家手上沒花的；名額＝機器 − 各家 limits
  slots 名 [--regular N] [--cpu N] [--llm-cpu N]    從總池撥名額（只收 ≥ 0）
  merge [A B] [--into A] [--dry-run] [--force]  剩兩家時合併（§5 of market.md）；上次合到一半＝接著做

改東西的子命令都拿 `<市場>/.market.lock`；grant／bankrupt／close／merge 先把要做的記進 market.json 再動手，
崩了重跑同一個指令接著做（帳戶照操作 ID 去重，不會重撥）。
  ls [--json]                                   每家：狀態、配額、已花、餘額、最近分數
這個檔留命令列（main 與印表）；實作分在 aos_market_book／review／score／grant／close／merge，這裡匯出外部用到的名字。
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import aos_team_cost as cost                                               # noqa: E402
from aos_team_format import TeamError                                      # noqa: E402

from aos_market_book import (
    cost_base, DEFAULT_PARAMS, load, market_dir, market_lock, MarketError, now, operating,
    pool_status, save
)
from aos_market_review import review_factor
from aos_market_score import board_from_company, quality_from_eval, record_score
from aos_market_grant import do_grant, grant_slots, open_company, rank
from aos_market_close import bankrupt, close
from aos_market_merge import apply_merge, plan_merge


# ------------------------------------------------------------------ 指令 ----

def _pairs(items, cast):
    out = {}
    for it in items or []:
        if '=' not in it:
            raise MarketError('Usage', '要寫成 名=數字：%r' % it)
        k, v = it.split('=', 1)
        out[k] = cast(v)
    return out


def _no_neg_zero(d):
    """印餘額用：浮點的 -0.0 印成 0.0（五家真跑 §7 第 7 條：倒閉後 ls 印 "usd": -0.0）。"""
    if not isinstance(d, dict):
        return d
    return {k: (0.0 if isinstance(v, float) and v == 0 else v) for k, v in d.items()}


def _pool_kinds(recycled, total):
    """印「收回總池」用：只印總池有管的那幾種（params.total 有設的）；沒設 total.usd＝美元不印
    （五家真跑 §7 第 7 條：總池不管美元，印「收回 usd 1.0」看起來像收回了什麼）。帳照樣記，只是不印。"""
    return {k: v for k, v in (recycled or {}).items() if total.get(k) is not None}


def _print_rank(rows):
    print('名次  公司    排名分   品質   原品質 成功率 審查  快    省    成功 失敗  董事等秒  跳數  這輪花 token   餘額')
    for r in rows:
        extra = []
        if r.get('scored') is False:
            extra.append('這輪沒 score')
        elif not r['done']:
            extra.append('這輪沒有成功結案：全項 0（原品質 %s）' % r.get('raw_quality'))
        if r.get('note'):
            extra.append(r['note'])
        rf = r.get('review_factor')
        print('%-4d  %-6s  %6.2f  %5.1f  %6s  %5.2f  %4s  %5.1f  %5.1f  %3d  %3d  %8s  %5s  %11d   %s%s' % (
            r['rank'], r['name'], r['score'], r['quality'],
            '-' if r.get('raw_quality') is None else '%.1f' % r['raw_quality'], r.get('success_rate') or 0.0,
            '-' if rf is None else '%.2f' % rf, r['speed'], r['cost'], r['done'], r.get('failed') or 0,
            r['seconds'] if r['seconds'] is not None else '-', r['hops'] if r['hops'] is not None else '-',
            r['spent_tokens'], json.dumps(r['balance'], ensure_ascii=False),
            '  ← ' + '；'.join(extra) if extra else ''))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='market.py', description='市場層：排名、撥額度、倒閉、合併（spec/team/market.md）')
    ap.add_argument('--market', '-M', help='市場資料夾（market.json、archive/）；沒給看 AOS_MARKET_HOME')
    sub = ap.add_subparsers(dest='cmd', required=True)
    DRY = '只算給你看，不寫帳、不動檔'
    p = sub.add_parser('open', help='開戶＋撥開辦費、登記進市場（從總池出）')
    p.add_argument('name', help='帳戶名（例 c1；收掉的名字不能再用）')
    p.add_argument('dir', help='公司資料夾（company.py new 生的）；不能跟別家的重疊')
    p.add_argument('--usd', type=float, help='開辦費美元（預設 params.seed.usd）')
    p.add_argument('--tokens', type=int, help='開辦費 token（預設 params.seed.tokens）')
    p = sub.add_parser('score', help='記這一輪的表現（grant 之後就換下一輪、要重記）')
    p.add_argument('name', help='公司')
    p.add_argument('--quality', type=float, help='品質分 0～100（經理人直接給）')
    p.add_argument('--eval', dest='eval_path', help='arknights 評分器的結果檔（算品質分，取代 --quality）')
    p.add_argument('--seconds', type=float, help='董事平均等幾秒（不給＝從董事的單到總裁結案信算；給了＝算一張成功）')
    p.add_argument('--hops', type=float, help='平均跳數（只記、不算分；不給＝從總機單算）')
    p.add_argument('--done', type=int, help='這輪成功結案幾張（經理人覆寫；不給＝品管合格＋總裁結案信的張數）')
    p = sub.add_parser('rank', help='算這一輪的排名（品質、快、省加權；不寫帳）')
    p.add_argument('--json', action='store_true', help='印 JSON')
    p = sub.add_parser('grant', help='照排名撥這一輪的額度（花光的不撥，先跑 bankrupt）')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p.add_argument('--usd', action='append', help='名=美元：覆寫這一家這輪撥多少（≥ 0；要收回用 close）')
    p.add_argument('--tokens', action='append', help='名=token：同上')
    p = sub.add_parser('bankrupt', help='花光的（某一種餘額 ≤ 0）倒閉：停、剩的收回總池、封存')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p = sub.add_parser('close', help='經理人裁撤一家：沒花完的配額收回總池')
    p.add_argument('name', help='公司')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p = sub.add_parser('pool', help='總池：錢還剩多少、名額還剩多少')
    p.add_argument('--json', action='store_true', help='印 JSON')
    p = sub.add_parser('slots', help='從總池撥名額給一家（只加不減；下次 company.py up 生效）')
    p.add_argument('name', help='公司')
    p.add_argument('--regular', type=int, default=0, help='正式員工名額 +N')
    p.add_argument('--cpu', type=int, default=0, help='cpu（default 池）+N')
    p.add_argument('--llm-cpu', type=int, default=0, help='llm cpu（llm 池）+N')
    p = sub.add_parser('merge', help='剩 merge_at 家時合併：排名高的併掉低的；上次合到一半＝接著做')
    p.add_argument('names', nargs='*', help='兩家（不給＝營業中那兩家）')
    p.add_argument('--into', help='指定併入方（不給＝排名高的）')
    p.add_argument('--dry-run', action='store_true', help='只印計畫（誰轉入、誰裁掉、正式或臨時）')
    p.add_argument('--force', action='store_true', help='營業中還多於 merge_at 家也硬合')
    p = sub.add_parser('ls', help='每家：狀態、餘額、已花、這輪品質')
    p.add_argument('--json', action='store_true', help='印 JSON')
    a = ap.parse_args(argv)
    try:
        mdir = market_dir(a.market)
        if a.cmd == 'open':
            c = open_company(mdir, a.name, a.dir, a.usd, a.tokens)
            print('開了 %s：%s' % (a.name, c['dir']))
            return 0
        if a.cmd == 'score':
            s = record_score(mdir, a.name, a.quality, a.eval_path, a.seconds, a.hops, a.done)
            print(json.dumps(s, ensure_ascii=False))
            for n in s.get('notes') or []:
                print('說明：' + n)
            asked = s['done'] + (s['failed'] or 0)
            print('成功率 %d/%d、審查輪數 %s → 審查係數 %s（排名時品質＝原始品質 %s × 成功率 × 審查係數）' % (
                s['done'], asked, json.dumps(s.get('review_rounds'), ensure_ascii=False),
                s['review_factor'] if s.get('review_factor') is not None else '沒紀錄當 1.0', s['quality']))
            if s.get('timeout'):
                print('注意：%s 這輪有 %d 張董事的單還沒結案，算逾時失敗（之後才來的結案信不再算）' % (a.name, s['timeout']))
            if not s['done']:
                print('注意：%s 這輪沒有成功結案（失敗 %d 張），排名時品質、快、省都算 0' % (a.name, s['failed']))
            return 0
        if a.cmd in ('rank', 'ls'):
            m = load(mdir)
            bal = cost.balances(cost_base())
            if a.cmd == 'rank':
                rows = rank(m, bal)
                if a.json:
                    print(json.dumps(rows, ensure_ascii=False, indent=1))
                else:
                    _print_rank(rows)
                return 0
            out = {n: dict(c, account=bal.get(n), score=m['scores'].get(n)) for n, c in m['companies'].items()}
            if a.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            else:
                for n, c in out.items():
                    acc = c['account'] or {}
                    print('%-6s %-9s 餘額 %s  已花 %s  品質 %s' % (n, c['status'], json.dumps(_no_neg_zero(acc.get('balance'))),
                                                         json.dumps(acc.get('spent')), (c['score'] or {}).get('quality')))
            return 0
        if a.cmd == 'grant':
            rnd, rows, grants = do_grant(mdir, _pairs(a.usd, float), _pairs(a.tokens, int), a.dry_run)
            _print_rank(rows)
            if not any(r['done'] for r in rows):
                print('這輪沒有公司成功結案：照公式全部撥 0')
            for n, g in grants.items():
                print('第 %d 輪撥給 %s：usd %s、tokens %s（%s）' % (rnd, n, g['usd'], g['tokens'],
                                                           '經理人覆寫' if g['override'] else '%.0f%%' % (100 * g['share'])))
            print('（只是試算，沒寫帳）' if a.dry_run else '已記帳')
            return 0
        if a.cmd in ('bankrupt', 'close'):
            out = bankrupt(mdir, a.dry_run) if a.cmd == 'bankrupt' else [close(mdir, a.name, a.dry_run)]
            total = load(mdir)['params'].get('total') or {}
            for o in out:
                shown = _pool_kinds(o['recycled'], total)
                print('%s %s：餘額 %s；收回總池 %s；名額回總池 %s；放出 %d 個名字；封存到 %s%s' % (
                    o['name'], '倒閉' if o['reason'] == 'bankrupt' else '裁撤', json.dumps(_no_neg_zero(o['balance'])),
                    json.dumps(shown or '（沒有剩）', ensure_ascii=False), json.dumps(o['slots']),
                    len(o['freed']), o['archive'], '（只是試算）' if a.dry_run else ''))
            if not out:
                print('沒有公司倒閉')
            return 0
        if a.cmd == 'pool':
            m = load(mdir)
            p = pool_status(m, cost.balances(cost_base()))
            if a.json:
                print(json.dumps(p, ensure_ascii=False, indent=1))
            else:
                print('總池 錢：%s（董事給的總量 %s；沒設＝不管）' % (json.dumps(p['money']), json.dumps(m['params']['total'])))
                print('總池 名額：%s（機器 %s，營業中各家用掉 %s）' % (json.dumps(p['slots']), json.dumps(m['params']['machine']),
                                                           json.dumps(p['slots_used'])))
            return 0
        if a.cmd == 'slots':
            lim = grant_slots(mdir, a.name, a.regular, a.cpu, a.llm_cpu)
            print('%s 的上限變成 %s（kernel 開著要 aos-kernel cpu add 或下次 up 才多開）' % (a.name, json.dumps(lim)))
            return 0
        if a.cmd == 'merge':
            m = load(mdir)
            pend = m.get('pending') or {}
            if pend.get('kind') == 'merge' and not a.dry_run:          # 上次合到一半：接著做
                res = apply_merge(mdir, pend['into'], pend['from'])
                print('接著做完：%s 併進 %s；餘額轉 %s' % (pend['from'], pend['into'], json.dumps(res['balance_moved'])))
                return 0
            ops = operating(m)
            names = a.names or ops
            if len(names) != 2:
                raise MarketError('Usage', '合併要剛好兩家（營業中：%s）' % '、'.join(ops))
            if len(ops) > m['params']['merge_at'] and not a.force:
                raise MarketError('TooEarly', '營業中還有 %d 家，剩 %d 家才合併（--force 硬來）' % (len(ops), m['params']['merge_at']))
            if a.into:
                into = a.into
            else:
                rows = rank(m, cost.balances(cost_base()))
                into = next(r['name'] for r in rows if r['name'] in names)
            other = [n for n in names if n != into][0]
            plan = plan_merge(m['companies'][into]['dir'], m['companies'][other]['dir'], other,
                              m['params']['dept_order'])
            for mv in plan['moves']:
                print('%-4s %-22s → %s' % (mv['dept'], mv['from'], ('%s（%s）' % (mv['to'], '正式' if mv['employment'] == 'regular' else '臨時工'))
                                           if mv['action'] == 'join' else '裁掉：%s' % mv['why']))
            if a.dry_run:
                print('（只是計畫，%s 併進 %s；沒動任何檔）' % (other, into))
                return 0
            res = apply_merge(mdir, into, other, plan)
            print('%s 併進 %s：%d 人轉入、%d 人裁掉；餘額轉 %s' % (other, into, len(res['moved']), len(res['laid_off']),
                                                          json.dumps(res['balance_moved'])))
            return 0
    except (TeamError, cost.CostError) as e:
        print('market.py: %s: %s' % (getattr(e, 'code', 'Error'), getattr(e, 'msg', e)), file=sys.stderr)
        return 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
