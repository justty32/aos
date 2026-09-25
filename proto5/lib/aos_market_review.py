"""市場的審查係數（第 75 題，經理人 09-25 晚）：製造部那張單子第幾次審查才過 → 品質要乘的係數。"""
import aos_team_format as fmt
from aos_team_format import TeamError


def _review_rounds(teams, o):
    """製造總機單 o 那張部門單子的審查輪數（第 75 題，經理人 09-25 晚）：郵差開的審查子單結果記在單子的 `review`
    （每次一筆 pass）。回第幾次審查才過（1、2、3…）；單子 failed＝'FAILED'；找不到單子或沒有審查紀錄＝None。"""
    tdir = teams.get((o.get('to') or {}).get('team') or (o.get('to') or {}).get('dept'))
    if tdir is None or not o.get('task'):
        return None
    try:
        ticket = fmt.read_json(fmt.Layout(tdir).task(o['task']))
    except (TeamError, OSError, ValueError):
        return None
    if ticket.get('status') == 'failed':
        return 'FAILED'
    for i, r in enumerate(ticket.get('review') or [], 1):
        if isinstance(r, dict) and r.get('pass'):
            return i
    return None


def review_factor(rounds, factors):
    """審查輪數 → 係數：第 n 次過＝factors[n-1]（超過就用最後一個）；'FAILED'＝0；None＝None（沒紀錄）。"""
    if rounds is None:
        return None
    if rounds == 'FAILED':
        return 0.0
    return float(factors[min(int(rounds), len(factors)) - 1])
