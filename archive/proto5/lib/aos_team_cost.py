"""財務部（2026-09-25）：記帳、查帳、擋預算。規格 spec/team/cost.md。

- 帳本放 $AOS_COST_HOME/ledger.jsonl（一台機器一本）；同一夾有 prices.json（價格表）、budget.json（全公司預算）。
  沒設 AOS_COST_HOME＝不記帳（跟 AOS_HOPS 一樣：一次 dict 查詢就回，測試不會寫進真帳本）。
- 記帳：aos_llm_call.call（agent 思考）與 aos_llm_ask.ask（工具、壓縮、結晶、評審…）拿到端點回的 usage 就叫 record()。
  **寫失敗絕不擋呼叫**：任何例外都吞掉。
- 查帳：`aos-team cost [--by team|member|model|family|task] [--since 今天|本週|全部|YYYY-MM-DD] [--team] [--json]`。
  金額用**現在的**價格表重算（改了價格表，舊帳的估值跟著改）；價格表沒有的模型只記 token、不算錢，另印警告。
- 預算：全公司 budget.json＋團隊 team.json 的 budget。超了：郵差把新的 handoff／spawn 申請退件（FAILED「財務擋單：超支」
  回寄件人；09-25 五家真跑前是留在 outbox），每天每種超額寄一封給 human；aos-team ls 第一行印超額。已在跑的單不砍。
- 回填：`aos-team cost import 資料夾…` 把找得到的 members/<名>/log/usage*.jsonl 撈進帳本（重跑不重記）。
這個檔留命令列 cmd_cost；實作分在 aos_team_cost_ledger／budget／account，這裡匯出外部用到的名字。
"""
import argparse
import json
import os
import sys

from aos_team_cost_ledger import (
    append, BUDGET, BY, CostError, DEFAULT_FAMILIES, ENV, family, HOLD_KINDS, home, import_usage,
    LEDGER, load_prices, make_row, PRICES, read_ledger, record, select, since_time, summarize, usd
)
from aos_team_cost_account import (
    account_grant, account_of, account_open, account_transfer, balances, load_accounts
)
from aos_team_cost_budget import (
    _fmt_amount, budget_status, check_budget, cpu_limits, cpu_line, hold_reason, ls_line,
    SCOPE_NAMES, usage_against
)


# ------------------------------------------------------------------ 命令列 ----

def _table(groups, by):
    head = {'family': '家族', 'model': '模型', 'team': '團隊', 'member': '成員', 'task': '單號', 'source': '來源'}[by]
    lines = ['%-34s %6s %13s %11s %10s' % (head, '次', 'prompt', 'completion', '估美元')]
    for g in groups:
        key = str(g['key'])
        if by == 'team' and key.startswith('/'):
            key = os.path.join(*key.rstrip('/').split('/')[-2:])     # 末兩段（團隊資料夾常叫 team）
        money = ('$%.4f' % g['usd']) + ('＋?' if g['unpriced_tokens'] else '')
        lines.append('%-34s %6d %13s %11s %10s' % (key[:34], g['calls'], format(g['prompt_tokens'], ','),
                                                    format(g['completion_tokens'], ','), money))
    return lines


def _cmd_account(base, prices, args):
    from aos_team_format import TeamError
    act = args.dirs[0] if args.dirs else 'ls'
    if act == 'open' and len(args.dirs) == 3:
        a = account_open(base, args.dirs[1], args.dirs[2])
        print('帳戶 %s 綁 %s' % (args.dirs[1], a['root']))
        return 0
    if act == 'grant' and len(args.dirs) == 2:
        g = account_grant(base, args.dirs[1], usd=args.usd, tokens=args.tokens, note=args.note)
        print('撥給 %s：%s' % (args.dirs[1], json.dumps(g, ensure_ascii=False)))
        return 0
    if act != 'ls' or len(args.dirs) > 1:
        raise TeamError('Usage', 'aos-team cost account ls｜open 名 公司資料夾｜grant 名 [--usd X] [--tokens N] [--note …]')
    b = balances(base, prices)
    broke = 1 if any(x['broke'] for x in b.values()) else 0
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=1))
        return broke
    if not b:
        print('還沒有帳戶（aos-team cost account open 名 公司資料夾）')
    for name, x in sorted(b.items()):
        def one(k):
            if x['quota'][k] is None:
                return '%s 已花 %s（沒配額）' % (k, _fmt_amount(k, x['spent'][k]))
            return '%s 餘 %s／配 %s' % (k, _fmt_amount(k, x['balance'][k]), _fmt_amount(k, x['quota'][k]))
        print('%-12s %s  %s；%s  %d 次%s' % (name, '倒閉' if x['broke'] else '營業', one('usd'), one('tokens'),
                                          x['calls'], '' if not x['broke'] else '  ← 餘額歸零，郵差不派新單'))
    return broke


def cmd_cost(team_dir, argv):
    from aos_team_format import TeamError
    ap = argparse.ArgumentParser(prog='aos-team cost', description='財務：模型用量與估算花費（帳本 $AOS_COST_HOME）')
    ap.add_argument('what', nargs='?', default='report', choices=('report', 'budget', 'import', 'account'),
                    help='report（預設）＝一張表；budget＝預算用了幾成；import 資料夾…＝回填舊的 usage.jsonl；'
                         'account ls／open 名 公司資料夾／grant 名 --usd X --tokens N＝一家公司一個帳戶')
    ap.add_argument('dirs', nargs='*', help='import 要掃的資料夾；account 的動作與參數')
    ap.add_argument('--usd', type=float)
    ap.add_argument('--tokens', type=int)
    ap.add_argument('--note', default='')
    ap.add_argument('--by', choices=BY, default='family')
    ap.add_argument('--since', default='今天', help='今天（預設）、本週、全部、YYYY-MM-DD')
    ap.add_argument('--team', action='store_true', help='只看這個團隊（--target 那個）的帳')
    ap.add_argument('--dry-run', action='store_true', help='import 只算不寫')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    env = os.environ
    base = home(env)
    if base is None:
        raise TeamError('NotConfigured', '沒設 %s（帳本資料夾的絕對路徑，例：export %s=~/.aos/cost 展開後的絕對路徑）'
                        % (ENV, ENV))
    try:
        prices = load_prices(base)
        if args.what == 'import':
            if not args.dirs:
                raise TeamError('Usage', 'aos-team cost import 資料夾…')
            new, skipped, files = import_usage(base, args.dirs, prices, dry_run=args.dry_run)
            out = {'files': files, 'imported': len(new), 'skipped': skipped, 'dry_run': args.dry_run}
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            else:
                print('%s %d 筆、略過 %d 筆（已記過／壞行），來自 %d 個 usage 檔' % (
                    '會記' if args.dry_run else '記了', len(new), skipped, len(files)))
            return 0
        if args.what == 'account':
            return _cmd_account(base, prices, args)
        team = os.path.realpath(team_dir) if args.team else None
        if args.what == 'budget':
            lines, over = budget_status(env, team_dir)
            if args.json:
                print(json.dumps({'lines': lines, 'over': over}, ensure_ascii=False, indent=1))
                return 0
            if not lines:
                print('沒設預算（%s/%s，或 team.json 的 budget）' % (base, BUDGET))
            for x in lines:
                print('%-4s %-9s %-6s %5.0f%%  %s／%s（%s 起）%s' % (
                    SCOPE_NAMES[x['scope']], x['family'], x['kind'], x['ratio'] * 100,
                    _fmt_amount(x['kind'], x['used']), _fmt_amount(x['kind'], x['limit']), x['since'],
                    '  ← 超了' if x['used'] >= x['limit'] else ''))
            return 1 if over else 0
        since = since_time(args.since)
        rows, bad = read_ledger(base)
        rows = select(rows, since, team)
        groups, unpriced = summarize(rows, args.by, prices)
        if args.json:
            print(json.dumps({'since': since.isoformat() if since else None, 'by': args.by, 'groups': groups,
                              'unpriced': unpriced, 'bad_lines': bad}, ensure_ascii=False, indent=1))
            return 0
        tot_t = sum(g['tokens'] for g in groups)
        tot_u = sum(g['usd'] for g in groups)
        print('帳本 %s：%s %d 次呼叫、%s token、估 $%.4f%s' % (
            os.path.join(base, LEDGER), ('%s 起' % since.strftime('%Y-%m-%d %H:%M')) if since else '有帳以來',
            sum(g['calls'] for g in groups), format(tot_t, ','), tot_u, '（只看本團隊）' if team else ''))
        for line in _table(groups, args.by):
            print(line)
        if unpriced:
            print('警告：價格表 %s 沒有這些模型，只記 token、不算錢：%s' % (
                os.path.join(base, PRICES), '、'.join('%s（%s token）' % (m, format(n, ',')) for m, n in unpriced.items())))
        if bad:
            print('警告：帳本有 %d 行讀不了，略過' % bad)
        print(cpu_line(env))
        return 0
    except CostError as e:
        raise TeamError(e.code, e.msg)


if __name__ == '__main__':
    import aos_team_cli
    sys.exit(aos_team_cli.main(['cost'] + sys.argv[1:]))
