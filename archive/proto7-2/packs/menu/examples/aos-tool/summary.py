"""Bounded author-gate summaries for the apprentice (stdlib only)."""
import json
import re

def one_line(value):
    if isinstance(value, list):
        return '；'.join(one_line(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return ' '.join(str(value).splitlines()).strip()

def answer_summary(value):
    heads, sample = [], ''
    for n, message in enumerate(value if isinstance(value, list) else [value]):
        text = one_line(message)
        marker = '：答案不合'
        if marker in text:
            label, tail = text.split(marker, 1)
            head, detail = label + marker, tail.lstrip('：')
        else:
            label, colon, tail = text.partition('：')
            conclusion, _, detail = tail.partition('：')
            head = label + colon + conclusion
        heads.append(head)
        if n == 0:
            sample = detail
    return '；'.join(heads), sample

def compact_sample(text, budget):
    # Decode JSON values rather than removing whitespace inside string values.
    def compact(match):
        try:
            value = json.loads(match.group())
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        except ValueError:
            return match.group()
    parts = [re.sub(r'[\[{].*[\]}]', compact, x) for x in text.split('；')]
    share = max(0, (budget - len(parts) + 1) // len(parts))
    return '；'.join(x if len(x) <= share else x[:max(0, share - 1)] + '…' for x in parts)

def test_failures(value):
    """Keep each unittest failure's identity and final exception, not its frames."""
    trace = re.sub(r'\n-{3,}\nRan \d+ tests?[^\n]*[\s\S]*$', '', str(value))
    blocks = re.split(r'(?m)^={6,}[ \t]*$|(?=^(?:FAIL|ERROR):)', trace)
    failures = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines and re.match(r'^(?:FAIL|ERROR):', lines[0]):
            failures.append((lines[0], lines[-1] if len(lines) > 1 else ''))
    return failures or [(one_line(trace.strip().splitlines()[-3:]), '')]

def clipped(text, budget):
    return text if len(text) <= budget else text[:max(0, budget - 1)] + '…'

def clip_test(prefix, head, error, budget):
    # Long test names must not consume the exception's entire allowance.
    if not error:
        return clipped(prefix + head, budget)
    available = max(0, budget - len(prefix) - 1)
    head_share = min(len(head), available // 2)
    error_share = min(len(error), available - head_share)
    head_share += min(len(head) - head_share, available - head_share - error_share)
    if not head_share or not error_share:
        return clipped(prefix + head + '；' + error, budget)
    return prefix + clipped(head, head_share) + '；' + clipped(error, error_share)

def summary(check, fallback='', gate=None):
    gate = gate or check.get('failed_gate') or 1
    issues = check.get('gates', {}).get(str(gate), {}).get('issues', check.get('issues', []))
    parts, sample = [], ''
    for item in issues:
        item = item if isinstance(item, dict) else {'why': item}
        rule = one_line(item.get('rule', 'check'))
        value = item.get('why', item.get('message', '未通過'))
        values = value if rule in ('review', 'test') and isinstance(value, list) else [value]
        entries = []
        for value in values:
            if rule == 'test' and '\n' in str(value):
                entries.extend((head + ('；' + error if error else ''), (head, error))
                               for head, error in test_failures(value))
            else:
                entries.append((value, None))
        for value, failure in entries:
            why = one_line(value)
            if rule == 'answer':
                why, detail = answer_summary(value)
                sample = sample or detail
            found = re.search(r'packs/[^\s：；，,\)]+', why)
            filename = item.get('file', item.get('path')) or (found.group() if found else {
                'answer': 'check_answer.py', 'test': 'tests/', 'review': '審查'
            }.get(rule, 'candidate.txt'))
            priority = 0 if rule == 'answer' or (gate == 3 and not why.startswith('建議：')) else 1
            prefix = rule + ' ' + one_line(filename) + '：'
            parts.append((priority, prefix + why, (prefix, *failure) if failure else None))
    parts = [(text, failure) for _, text, failure in sorted(parts, key=lambda pair: pair[0])]
    if not parts:
        parts = [(one_line(fallback or check.get('error', '候選未通過')), None)]
    # Reserve each issue's beginning, then spend remaining space in priority order.
    budget = 580 - len('第%d關：' % gate) - len(parts) + 1
    quotas = [min(len(part), 140, max(0, budget // len(parts))) for part, _ in parts]
    spare = budget - sum(quotas)
    for i, (part, _) in enumerate(parts):
        more = min(spare, len(part) - quotas[i])
        quotas[i] += more
        spare -= more
    pieces = [clip_test(*failure, q) if failure else clipped(part, q)
              for (part, failure), q in zip(parts, quotas) if q > 0]
    text = '第%d關：' % gate + '；'.join(pieces)
    if sample and len(text) < 560:
        text += '；主樣本：' + compact_sample(sample, 580 - len(text) - 5)
    return text if len(text) <= 580 else text[:579] + '…'
