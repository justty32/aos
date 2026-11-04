"""收集實際存在的證據，未走到的階段留 null；不從成功退出推測答案。"""
import json
from pathlib import Path
import shutil
import sys


def load(path):
    try:
        doc = json.loads(path.read_bytes())
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def collect(out, root):
    proposal = load(out / 'propose.json')
    call_id = proposal.get('llm', {}).get('call_id')
    if call_id:
        for name in ('receipt.json', 'raw.json', 'request.json'):
            source = root / 'llm/llmcall/llm' / call_id / name
            if source.is_file():
                shutil.copyfile(source, out / name)
    for name in ('candidate.json', 'verdict.json'):
        source = root / 'work/author/req/csv1' / name
        if source.is_file():
            shutil.copyfile(source, out / name)
    job = proposal.get('job')
    if job:
        source = root / 'work/jobs' / job / 'out/report.json'
        if source.is_file():
            target = out / 'jobs' / job / 'out/report.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def summarize(out, model, seconds):
    propose = load(out / 'propose.json')
    llm = propose.get('llm') or {}
    usage = llm.get('usage') or {}
    if not isinstance(usage, dict):
        usage = {}
    publish, step, answer, close = [load(out / name) for name in
                                   ('publish.json', 'step-status.json', 'answer.json', 'close.json')]
    return dict(model=model, call_id=llm.get('call_id'),
                prompt_tokens=usage.get('prompt_tokens'), completion_tokens=usage.get('completion_tokens'),
                total_tokens=usage.get('total_tokens'), llm_seconds=float(seconds) if seconds else None,
                propose_ok=propose.get('ok'), issues_rules=sorted({i['rule'] for i in propose.get('issues', [])}),
                published=publish.get('ok'), step_end=step.get('end'), answer_ok=answer.get('ok'),
                closed=close.get('ok'))


if __name__ == '__main__':
    out, model, seconds, root = sys.argv[1:5]
    out, root = Path(out), Path(root)
    collect(out, root)
    if '--collect-only' not in sys.argv[5:]:
        raw = json.dumps(summarize(out, model, seconds), ensure_ascii=False, indent=2) + '\n'
        (out / 'summary.json').write_text(raw, encoding='utf-8')
        print(raw, end='')
