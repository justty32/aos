"""門房（spec/team/route.md）：aos-team ask 的前濾網，整句句型比對，命中就不叫模型。

- aos-team ask "一句話"：先跑 routes.json 的例句（沒全過＝退 1），再判決：
  tool＝在同一個行程跑 aos-team 子命令，或跑 proto5/tools 裡某包的一支工具；
  handoff＝往 team/outbox/human/ 放一份開單申請；沒命中／命中兩條／有否定詞＝一封 REQUEST 寄給領隊。
- aos-team route test [--file F]／route save F：例句全過才存。
每次判決都往 team/route.log 追加一行 JSON。不叫模型。
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from aos_team_format import (DEFAULT_NEGATIONS, HUMAN, Layout, TeamError, load_roster, members_by_template,
                             new_id, now_iso, project_dir, read_json, validate_letter, validate_request,
                             validate_routes, write_json, write_new)

PACKAGES = Path(__file__).resolve().parent.parent / 'tools'
TOOL_TIMEOUT = 60


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


# ------------------------------------------------------------------ 規則 ----

def load_routes(path):
    """沒有檔＝沒規則（全部落穿）。回 (否定詞, [(規則, 正規式)…])。"""
    path = Path(path)
    if not path.exists():
        return list(DEFAULT_NEGATIONS), []
    return validate_routes(read_json(path), str(path))


def _match(rx, text):
    """整句比；具名群組都要有值才算。回 groups 或 None。"""
    m = rx.fullmatch(text)
    if m is None:
        return None
    groups = m.groupdict()
    if any(v is None or v == '' for v in groups.values()):
        return None
    return groups


def decide(text, neg, routes):
    """回 (結果, 規則或 None, 群組, 理由)。結果：tool／handoff／lead。"""
    text = text.strip()
    hits = []
    for rule, rx in routes:
        groups = _match(rx, text)
        if groups is not None:
            hits.append((rule, groups))
    found = [w for w in neg if w in text]
    if found:
        return 'lead', None, {}, '含否定詞「%s」' % found[0]
    if not hits:
        return 'lead', None, {}, '沒有規則命中'
    if len(hits) > 1:
        return 'lead', None, {}, '命中兩條以上：%s' % '、'.join(r['name'] for r, _ in hits)
    rule, groups = hits[0]
    return rule['do'], rule, groups, '命中 %s' % rule['name']


def run_tests(neg, routes):
    """每條規則跑例句。回 [(規則名, 過了沒, [失敗說明…])]。"""
    out = []
    for rule, rx in routes:
        fails = []
        for s in rule['tests']['hit']:
            result, got, _, why = decide(s, neg, routes)
            if got is None or got['name'] != rule['name']:
                fails.append('hit「%s」沒判給這條（%s）' % (s, why))
        for s in rule['tests']['miss']:
            if _match(rx, s.strip()) is not None:
                fails.append('miss「%s」卻命中這條' % s)
        out.append((rule['name'], not fails, fails))
    return out


def _print_tests(results):
    for name, ok, fails in results:
        print('%s %s' % ('PASS' if ok else 'FAIL', name))
        for f in fails:
            print('  ' + f)
    bad = sum(1 for _, ok, _ in results if not ok)
    print('%d 條規則，%d 條沒過' % (len(results), bad))
    return bad


def fill(value, groups):
    """把字串裡的 {群組名} 換成值（遞迴；名字對不上的原樣留著）。"""
    if isinstance(value, str):
        return re.sub(r'\{(\w+)\}', lambda m: groups.get(m.group(1), m.group(0)), value)
    if isinstance(value, list):
        return [fill(v, groups) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, groups) for k, v in value.items()}
    return value


# ------------------------------------------------------------------ 做事 ----

def _log(lay, text, result, rule, why):
    line = {'at': now_iso(), 'text': text, 'result': result, 'route': rule['name'] if rule else None, 'why': why}
    lay.route_log.parent.mkdir(parents=True, exist_ok=True)
    with open(lay.route_log, 'a', encoding='utf-8') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')


def _put(lay, obj):
    folder = lay.outbox(HUMAN)
    folder.mkdir(parents=True, exist_ok=True)
    if not write_new(folder / (obj['id'] + '.json'), obj):
        raise TeamError('AlreadyExists', '%s 已經在 outbox 裡' % obj['id'])
    return obj['id']


def run_pack_tool(team_dir, roster, spec, args):
    """跑 proto5/tools/<包>/<包>.json 裡的一支；回退出碼（輸出原樣印）。"""
    pack, name = spec.split('/', 1)
    folder = PACKAGES / pack
    tools_file = folder / (pack + '.json')
    if not tools_file.is_file():
        raise TeamError('NotFound', '找不到工具包 %s（%s）' % (pack, tools_file))
    tools = read_json(tools_file)
    found = [t for t in tools if isinstance(t, dict) and t.get('function', {}).get('name') == name] \
        if isinstance(tools, list) else []
    if not found:
        raise TeamError('NotFound', '%s 裡沒有工具 %s' % (tools_file, name))
    argv = list(found[0].get('_meta', {}).get('argv') or [])
    if not argv or not all(isinstance(a, str) for a in argv):
        raise TeamError('NotFound', '%s 的 %s 沒有 _meta.argv' % (tools_file, name))
    prefix = 'tools/%s/' % pack
    if argv[0].startswith(prefix):
        argv[0] = str(folder / argv[0][len(prefix):])
    elif '/' in argv[0] and not os.path.isabs(argv[0]):
        raise TeamError('NotFound', '%s 的 argv[0] %s 不在 tools/%s/ 底下' % (tools_file, argv[0], pack))
    env = dict(os.environ, AOS_TOOL_ROOT=str(project_dir(team_dir, roster)))
    try:
        r = subprocess.run(argv, input=json.dumps(args or {}, ensure_ascii=False), capture_output=True, text=True,
                           cwd=str(team_dir), env=env, timeout=TOOL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise TeamError('Timeout', '%s 跑了 %d 秒沒完，砍掉了' % (spec, TOOL_TIMEOUT))
    except OSError as e:
        raise TeamError('SpawnFailed', '跑不起來 %s：%s' % (argv[0], e))
    sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode


def ask(team_dir, text):
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    text = text.strip()
    if not text:
        raise TeamError('Usage', '要說一句話')
    neg, routes = load_routes(lay.routes)
    bad = [x for x in run_tests(neg, routes) if not x[1]]
    if bad:
        raise TeamError('RoutesFailed', '%s 的例句沒全過（%s）；先修好，跑 aos-team route test 看細節'
                        % (lay.routes, '、'.join(n for n, _, _ in bad)))
    result, rule, groups, why = decide(text, neg, routes)
    if result == 'tool':
        _log(lay, text, 'tool', rule, why)
        if 'run' in rule:
            from aos_team_cli import resolve
            return resolve(rule['run'][0])(str(lay.root), list(rule['run'][1:]))
        return run_pack_tool(lay.root, roster, rule['tool'], rule.get('args'))
    if result == 'handoff':
        req = dict(fill(rule['handoff'], groups))
        req.update(id=new_id(HUMAN), kind='handoff', at=now_iso(roster.get('tz')))
        req['from'] = HUMAN
        validate_request(req, 'routes.json 規則 %s 的 handoff' % rule['name'])
        _put(lay, req)
        _log(lay, text, 'handoff', rule, why)
        print('開單申請已交給郵差：%s（派給 %s）' % (req['id'], req['assignee']))
        return 0
    leads = members_by_template(roster, 'lead')
    if not leads:
        _log(lay, text, 'none', None, why + '；隊裡沒有領隊')
        raise TeamError('NoLead', '%s，隊裡也沒有領隊（template: lead）可以交給' % why)
    ltr = {'id': new_id(HUMAN), 'from': HUMAN, 'to': leads[0], 'status': 'REQUEST', 'reply_to': None,
           'rev': None, 'text': text, 'at': now_iso(roster.get('tz'))}
    validate_letter(ltr)
    _put(lay, ltr)
    _log(lay, text, 'lead', None, why)
    print('%s，已交給領隊 %s：%s' % (why, leads[0], ltr['id']))
    return 0


# ------------------------------------------------------------------ 命令 ----

def cmd_ask(team_dir, argv):
    ap = _Parser(prog='aos-team ask', description='交給門房：命中規則就直接做，沒命中投給領隊')
    ap.add_argument('text', nargs='+', help='一句話（多個字用空白接起來）')
    args = ap.parse_args(argv)
    return ask(team_dir, ' '.join(args.text))


def cmd_route(team_dir, argv):
    ap = _Parser(prog='aos-team route', description='route test [--file F]：跑例句；route save F：全過才存')
    ap.add_argument('action', choices=('test', 'save'))
    ap.add_argument('file', nargs='?')
    ap.add_argument('--file', dest='file_opt')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    path = args.file_opt or args.file
    if args.action == 'save' and not path:
        raise TeamError('Usage', 'route save 要給檔案：aos-team route save FILE')
    path = Path(os.path.abspath(path)) if path else lay.routes
    if args.action == 'test' and not path.exists():
        raise TeamError('NotFound', '%s 不存在' % path)
    obj = read_json(path)
    neg, routes = validate_routes(obj, str(path))
    bad = _print_tests(run_tests(neg, routes))
    if bad:
        if args.action == 'save':
            print('沒存：%s 不動' % lay.routes)
        return 1
    if args.action == 'save':
        lay.routes.parent.mkdir(parents=True, exist_ok=True)
        write_json(lay.routes, obj, indent=2)
        print('存好了：%s' % lay.routes)
    return 0
