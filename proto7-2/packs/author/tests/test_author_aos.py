"""三關可抽換、固定候選與 git plumbing 的整體驗收。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

A = Path(__file__).resolve().parents[1]
CLI = A / 'checkers/aos_three_gates.py'
USAGE = A / 'examples/aos-tool-usage'
DIAG = A / 'examples/aos-module-diag'
REPO = Path(subprocess.check_output(['git','-C',str(A),'rev-parse','--show-toplevel']).decode().strip())
HEAD = subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD']).decode().strip()
PREFIX = A.parents[1].relative_to(REPO).as_posix()


def dump(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')


def snap(path):
    return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}


class TestAuthorAos(unittest.TestCase):
    def cli(self, candidate='valid.json', folder=USAGE, cmd='check', extra=(), disabled=None):
        argv = [cmd,str(folder/'request.json'),str(folder/candidate),'--reviewer','rules','--no-scope',*map(str,extra)]
        if disabled:
            script = "import sys;sys.path.insert(0,sys.argv.pop(1));import aos_three_gates as g;g.GATES[%d]=lambda ctx:{'ok':True,'issues':[]};raise SystemExit(g.main(sys.argv[1:]))" % disabled
            args = [sys.executable,'-c',script,str(CLI.parent),*argv]
        else:
            args = [sys.executable,str(CLI),*argv]
        p = subprocess.run(args,capture_output=True,timeout=120)
        self.assertTrue(p.stdout, p.stderr.decode())
        return p.returncode,json.loads(p.stdout)

    def test_aos_fixed_candidates(self):
        cases = [('valid.json',None,None),('bad-territory.json',1,'territory'),('bad-notest.json',1,'tests'),('bad-size.json',1,'size'),('bad-link.json',1,'lint'),('bad-red.json',2,'test'),('bad-review.json',3,'review')]
        for folder, rows in [(USAGE,cases),(DIAG,[('valid.json',None,None),('bad-contract.json',1,'readme')])]:
            for filename, gate, rule in rows:
                with self.subTest(folder=folder.name,candidate=filename):
                    code,out = self.cli(filename,folder)
                    self.assertEqual(code,0 if gate is None else 2,out)
                    self.assertEqual(out['failed_gate'],gate)
                    self.assertEqual(out['ok'],gate is None)
                    if gate:
                        self.assertEqual({x['rule'] for x in out['gates'][str(gate)]['issues']},{rule},out)
                        for n in range(1,gate):
                            self.assertIs(out['gates'][str(n)]['ok'],True)
                        for n in range(gate+1,4):
                            self.assertEqual(out['gates'][str(n)],{'ok':None})

    def test_aos_remove_gate_passes(self):
        for gate, filenames in [(1,['bad-territory.json','bad-size.json','bad-link.json']),(2,['bad-red.json']),(3,['bad-review.json'])]:
            for filename in filenames:
                with self.subTest(gate=gate,candidate=filename):
                    code,out = self.cli(filename,disabled=gate)
                    self.assertEqual(code,0,out)
                    self.assertIs(out['ok'],True)

    def test_aos_notest_defense(self):
        code,out = self.cli('bad-notest.json', disabled=1)
        self.assert_failure(code,out,2,'test')

    def test_aos_answer_independent(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        source = 'packs/usage/aos7_usage.py'
        candidate['files'][source] = candidate['files'][source].replace("group['overrun'] += overrun", "group['overrun'] += 0")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'wrong.json'
            dump(path,candidate)
            code,out = self.cli(str(path))
        self.assertEqual(code,2,out)
        self.assertEqual(out['failed_gate'],2)
        self.assertEqual([x['rule'] for x in out['gates']['2']['issues']],['answer'])

    def test_aos_sandbox_blocks_host_writes(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as host, tempfile.TemporaryDirectory() as tmp:
            candidate = json.loads((USAGE/'valid.json').read_text())
            candidate['files']['packs/usage/tests/test_usage_escape.py'] = (
                "import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n"
                "    def test_write(self):\n        Path(%r, 'x').write_text('escaped')\n" % host)
            path = Path(tmp)/'escape.json'
            dump(path,candidate)
            code,out = self.cli(str(path))
            self.assertFalse((Path(host)/'x').exists())
        self.assert_failure(code,out,2,'test')

    def test_aos_territory_variants(self):
        # 索引列與路徑的變形都由第一關 territory 擋下。
        base = json.loads((USAGE/'valid.json').read_text())
        rows = {'row': base['row'] + '\n| `packs/llmcall/` | 改別人的列 |', 'prefix': '| `packs/x/` |' + base['row'].split('|', 2)[2]}
        for label, mutate in [('row', lambda c: c.update(row=rows['row'])), ('prefix', lambda c: c.update(row=rows['prefix'])),
                              ('dotdot', lambda c: c['files'].update({'packs/usage/../llmcall/x.py': 'x = 1\n'}))]:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                candidate = json.loads(json.dumps(base))
                mutate(candidate)
                path = Path(tmp)/'c.json'
                dump(path,candidate)
                code,out = self.cli(str(path))
                self.assertEqual(code,2,out)
                self.assertIn('territory',{x['rule'] for x in out['gates']['1']['issues']},out)

    def test_aos_publish(self):
        def git(repo,*args):
            return subprocess.check_output(['git','-C',str(repo),*args])
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)/'repo'
            subprocess.run(['git','clone','-q','--shared','--no-checkout',str(REPO),str(repo)],check=True,capture_output=True)
            head = git(repo,'rev-parse','HEAD')
            refs = git(repo,'show-ref')
            worktree = sorted(p.name for p in repo.iterdir())
            index = repo/'.git/index'
            index_before = index.read_bytes() if index.exists() else None
            opts = ['--repo',repo,'--ref',HEAD]
            code,out = self.cli(cmd='publish',extra=opts)
            self.assertEqual(code,0,out)
            branch = out['branch']
            self.assertEqual(branch,'apprentice/'+out['job'])
            self.assertEqual(git(repo,'rev-parse',branch).decode().strip(),out['commit'])
            entry = PREFIX+'/packs/usage/bin/aos7-usage'
            self.assertTrue(git(repo,'ls-tree',branch,'--',entry).startswith(b'100755 blob'))
            candidate = json.loads((USAGE/'valid.json').read_text())
            for path,text in candidate['files'].items():
                self.assertEqual(git(repo,'show',branch+':'+PREFIX+'/'+path),text.encode())
            original = git(repo,'show',HEAD+':'+PREFIX+'/INDEX.md')
            expected = original + (b'' if original.endswith(b'\n') else b'\n') + candidate['row'].encode()+b'\n'
            self.assertEqual(git(repo,'show',branch+':'+PREFIX+'/INDEX.md'),expected)
            self.assertIn(b'candidate_sha: '+out['candidate_sha'].encode(),git(repo,'show','-s','--format=%B',branch))
            self.assertEqual(git(repo,'show','-s','--format=%an <%ae>|%cn <%ce>',branch).strip(),b'aos-apprentice <apprentice@aos.local>|aos-apprentice <apprentice@aos.local>')
            code,dup = self.cli(cmd='publish',extra=opts)
            self.assertEqual(code,0,dup)
            self.assertIs(dup['dup'],True)
            self.assertEqual(dup['commit'],out['commit'])
            code,bad = self.cli('bad-red.json',cmd='publish',extra=opts)
            self.assertEqual(code,2,bad)
            self.assertNotEqual(subprocess.run(['git','-C',str(repo),'show-ref','--verify','refs/heads/apprentice/'+bad['job']],capture_output=True).returncode,0)
            changed = Path(tmp)/'changed.json'
            candidate['report'] += '新'
            dump(changed,candidate)
            code,other = self.cli(str(changed),cmd='publish',extra=opts)
            self.assertEqual(code,0,other)
            self.assertNotEqual(other['job'],out['job'])
            self.assertEqual(git(repo,'rev-parse','HEAD'),head)
            current = b'\n'.join(line for line in git(repo,'show-ref').splitlines() if b'refs/heads/apprentice/' not in line)+b'\n'
            self.assertEqual(current,refs)
            self.assertEqual(sorted(p.name for p in repo.iterdir()),worktree)
            self.assertEqual(index.read_bytes() if index.exists() else None,index_before)
            # 同名已有分支但樹不同，禁止覆蓋。
            git(repo,'update-ref','refs/heads/'+branch,HEAD)
            code,conflict = self.cli(cmd='publish',extra=opts)
            self.assertEqual(code,3,conflict)
            self.assertIs(conflict['dup'],False)
            self.assertEqual(git(repo,'rev-parse',branch).decode().strip(),HEAD)

    def test_aos_brief(self):
        for folder in (USAGE,DIAG):
            p = subprocess.run([sys.executable,str(CLI),'brief',str(folder/'request.json')],capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            text = p.stdout.decode()
            for heading in ['# 任務：','## 背景與唯一目標','## 範圍（排除法寫死）','## 必用工具','## 工作','## 交付','## 驗收（固定']:
                self.assertIn(heading,text)
            count = len(json.loads((folder/'request.json').read_text())['accept'])
            lines = text.split('## 驗收（固定')[1].splitlines()[1:]
            self.assertEqual(len([line for line in lines if line[:1].isdigit()]),count)

    def test_aos_answer_readonly(self):
        for folder in (USAGE,DIAG):
            before = snap(folder/'fixture')
            with tempfile.TemporaryDirectory() as tmp:
                top = Path(tmp)
                candidate = json.loads((folder/'valid.json').read_text())
                for path,text in candidate['files'].items():
                    p = top/path
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_text(text,encoding='utf-8')
                answer = subprocess.run([sys.executable,str(folder/'check_answer.py'),str(top),str(folder/'fixture')],capture_output=True)
                self.assertEqual(answer.returncode,0,answer.stdout+answer.stderr)
                self.assertIs(json.loads(answer.stdout)['ok'],True)
            self.assertEqual(snap(folder/'fixture'),before)

    def test_aos_strict_json_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.json'
            for data in [b'{"v":1,"v":1}',b'{"v":NaN}',b'\xff']:
                path.write_bytes(data)
                code,out = self.cli(str(path))
                self.assertEqual(code,2,out)
                self.assertEqual(out['gates']['1']['issues'][0]['rule'],'json')
            review = Path(tmp)/'review.json'
            reviews = [
                ('前文 {"verdict":"accept","reasons":[]}',False),
                ('{"verdict":"reject","reasons":[]}\n{"verdict":"accept","reasons":[]}',False),
                ('{"verdict":"reject","verdict":"accept","reasons":[]}',False),
                ('{"verdict":"accept","reasons":[{}]}',False),
                ('{"verdict":"accept","reasons":[],"extra":1}',False),
                ('{"verdict":"accept","reasons":[]}',True),
                ('```json\n{"verdict":"accept","reasons":[]}\n```',True),
                ('{"verdict":"reject","reasons":["拒絕"]}',False),
            ]
            for content,accepted in reviews:
                with self.subTest(review=content):
                    review.write_text(content,encoding='utf-8')
                    code,out = self.cli(extra=['--reviewer','file:'+str(review)])
                    self.assertEqual(code,0 if accepted else 2,out)
                    self.assertEqual(out['failed_gate'],None if accepted else 3)
                    if not accepted and content != reviews[-1][0]:
                        self.assertIn('審查回覆格式不合',out['gates']['3']['issues'][0]['why'])
            code,out = self.cli(extra=['--ref','does-not-exist'])
            self.assertEqual(code,4,out)

    def assert_failure(self, code, out, gate, rule):
        self.assertEqual(code,2,out)
        self.assertEqual(out['failed_gate'],gate,out)
        self.assertEqual({x['rule'] for x in out['gates'][str(gate)]['issues']},{rule},out)

    def candidate_check(self, candidate, folder=USAGE, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'candidate.json'
            dump(path,candidate)
            return self.cli(str(path),folder,**kwargs)

    def test_aos_sandbox_hides_run(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        candidate['files']['packs/usage/tests/test_usage_isolation.py'] = (
            "import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n"
            "    def test_run(self):\n        self.assertFalse(Path('/run/user').exists())\n")
        code,out = self.candidate_check(candidate)
        self.assertEqual(code,0,out)

    def test_aos_sandbox_hides_home_and_env(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        with tempfile.TemporaryDirectory(dir=Path.home()) as home:
            secret = Path(home)/'a4-secret'
            secret.write_text('private')
            candidate['files']['packs/usage/tests/test_usage_secrets.py'] = (
                "import os, unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n"
                "    def test_secrets(self):\n        self.assertNotIn('A4_SECRET', os.environ)\n"
                "        self.assertFalse(Path('/home').exists())\n"
                "        self.assertFalse(Path(%r).exists())\n"
                "        self.assertEqual(Path.home(), Path('/tmp/home'))\n" % str(secret))
            previous = os.environ.get('A4_SECRET')
            os.environ['A4_SECRET'] = 'private'
            try:
                code,out = self.candidate_check(candidate)
            finally:
                if previous is None:
                    del os.environ['A4_SECRET']
                else:
                    os.environ['A4_SECRET'] = previous
        self.assertEqual(code,0,out)

    def test_aos_answer_detects_fixture_writes(self):
        for folder,root,func in [(USAGE,'packs/usage','summarize(node, by=\'day\')'),(DIAG,'modules/llmdiag','diagnose(node)')]:
            source = root+'/aos7_'+('usage' if folder == USAGE else 'llmdiag')+'.py'
            actions = ["(node/'SIDE_EFFECT').write_text('x')", "(node/'EMPTY_SIDE_EFFECT').mkdir()",
                       "next(node.glob('llmcall/*/*/request.json')).chmod(0o600)",
                       "next(node.glob('llmcall/*/*/request.json')).unlink()"]
            for action in actions:
                with self.subTest(folder=folder.name,action=action):
                    candidate = json.loads((folder/'valid.json').read_text())
                    old = 'def '+func+':\n'
                    self.assertIn(old,candidate['files'][source])
                    injected = old + "    if (node/'llmcall/llm').exists():\n        try:\n            " + action + "\n        except OSError:\n            pass\n"
                    candidate['files'][source] = candidate['files'][source].replace(old,injected)
                    code,out = self.candidate_check(candidate,folder)
                    self.assert_failure(code,out,2,'answer')

    def test_aos_tests_are_direct_children(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        test = candidate['files'].pop('packs/usage/tests/test_usage.py')
        candidate['files']['packs/usage/nested/tests/test_usage.py'] = test
        candidate['files']['packs/usage/README.md'] = candidate['files']['packs/usage/README.md'].replace('tests/test_usage.py','nested/tests/test_usage.py')
        code,out = self.candidate_check(candidate)
        self.assert_failure(code,out,1,'tests')

    def test_aos_tests_need_actual_cases(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        candidate['files']['packs/usage/tests/test_usage.py'] = '# zero tests\n'
        code,out = self.candidate_check(candidate)
        self.assert_failure(code,out,2,'test')
        self.assertIn('沒有實際測試',out['gates']['2']['issues'][0]['why'])

    def test_aos_readme_fences_are_not_sections(self):
        for folder,root in [(USAGE,'packs/usage'),(DIAG,'modules/llmdiag')]:
            candidate = json.loads((folder/'valid.json').read_text())
            path = root+'/README.md'
            readme = candidate['files'][path]
            required = ['## 第一次跑'] if folder == USAGE else ['**職責**', '**前置條件**', '**保證**', '**明確不管**']
            lines = readme.splitlines()
            fenced = [line for line in lines if any(line.startswith(must) for must in required)]
            visible = [line for line in lines if line not in fenced]
            candidate['files'][path] = '\n'.join(visible)+'\n```markdown\n'+'\n'.join(fenced)+'\n```\n'
            code,out = self.candidate_check(candidate,folder)
            self.assert_failure(code,out,1,'readme')

    def test_aos_readme_requires_line_start(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        path = 'packs/usage/README.md'
        candidate['files'][path] = candidate['files'][path].replace('## 第一次跑','假標題 ## 第一次跑')
        code,out = self.candidate_check(candidate)
        self.assert_failure(code,out,1,'readme')

    def test_aos_review_scans_entry(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        entry = 'packs/usage/bin/aos7-usage'
        candidate['files'][entry] = candidate['files'][entry].replace('import sys\n','import sys\nimport os\nos.system("true")\n')
        code,out = self.candidate_check(candidate)
        self.assert_failure(code,out,3,'review')

    def test_aos_publish_ignores_materialized_tamper(self):
        candidate = json.loads((USAGE/'valid.json').read_text())
        candidate['files']['packs/usage/tests/test_usage_tamper.py'] = (
            "import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n"
            "    def test_tamper(self):\n        path = Path(__file__).resolve().parents[3]/'INDEX.md'\n"
            "        path.write_text(path.read_text()+'TAMPER\\n')\n")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)/'repo'
            subprocess.run(['git','clone','-q','--shared','--no-checkout',str(REPO),str(repo)],check=True,capture_output=True)
            code,out = self.candidate_check(candidate,cmd='publish',extra=['--repo',repo,'--ref',HEAD])
            self.assertEqual(code,0,out)
            original = subprocess.check_output(['git','-C',str(repo),'show',HEAD+':'+PREFIX+'/INDEX.md'])
            actual = subprocess.check_output(['git','-C',str(repo),'show',out['branch']+':'+PREFIX+'/INDEX.md'])
            expected = original+(b'' if original.endswith(b'\n') else b'\n')+candidate['row'].encode()+b'\n'
            self.assertEqual(actual,expected)
            self.assertNotIn(b'TAMPER',actual)
            self.assertEqual(len(actual.splitlines()),len(original.splitlines())+1)

    def test_aos_publish_rejects_symbolic_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)/'repo'
            subprocess.run(['git','clone','-q','--shared','--no-checkout',str(REPO),str(repo)],check=True,capture_output=True)
            data = (USAGE/'valid.json').read_bytes()
            job = 'usage1_'+hashlib.sha256(data).hexdigest()[:8]
            subprocess.run(['git','-C',str(repo),'symbolic-ref','refs/heads/apprentice/'+job,'refs/heads/zzz'],check=True)
            code,out = self.cli(cmd='publish',extra=['--repo',repo,'--ref',HEAD])
            self.assertEqual(code,3,out)
            self.assertNotEqual(subprocess.run(['git','-C',str(repo),'show-ref','--verify','refs/heads/zzz'],capture_output=True).returncode,0)
            target = subprocess.check_output(['git','-C',str(repo),'symbolic-ref','refs/heads/apprentice/'+job]).decode().strip()
            self.assertEqual(target,'refs/heads/zzz')

    def test_aos_usage_extended_fixture(self):
        mutations = [
            ("used = receipt.get('used') or 0", "used = receipt.get('used')"),
            ("group['calls'] += 1", "group['calls'] = 1"),
            ("group['used'] += used", "group['used'] = used"),
            ("if by == 'day' else '%Y-%m-%dT%H'", "if True else '%Y-%m-%dT%H'"),
            ("default='day'", "default='hour'"),
            ("if type(used) is int:", "if isinstance(used, int):"),
            ("if type(used) is int:", "if used is not None:"),
            ("account['diff'] = used - account['receipts_used']", "account['diff'] = max(0, used - account['receipts_used'])"),
            ("req = load(reqpath)", "req = load(reqpath) if call_id != 'c10' else dict(request=dict(model='chatgpt-gpt-6-sol'),holder='author',endpoint='fake')"),
            ("raw = load(call / 'raw.json') if", "raw = dict(at=1791454320) if call_id == 'c11' else load(call / 'raw.json') if"),
            ("return dict(v=1,", "return dict(v=True,"),
        ]
        for old,new in mutations:
            with self.subTest(mutation=old):
                candidate = json.loads((USAGE/'valid.json').read_text())
                source = 'packs/usage/aos7_usage.py'
                self.assertIn(old,candidate['files'][source])
                candidate['files'][source] = candidate['files'][source].replace(old,new)
                # Deliberately retain only green smoke tests: the answer checker must catch this.
                candidate['files']['packs/usage/tests/test_usage.py'] = 'import unittest\nclass T(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n'
                code,out = self.candidate_check(candidate)
                self.assert_failure(code,out,2,'answer')

    def test_aos_diag_extended_fixture(self):
        mutations = [
            ('author_halted=halted', 'author_halted=list(reversed(halted))'),
            ('budget_inflight=inflight', 'budget_inflight=list(reversed(inflight))'),
            ("r'(.+)_[0-9a-fA-F]{8}'", "r'(.+)_.+'"),
            ("raw = path.parent / 'raw.json'", "raw = path.parent / 'raw.json'\n            if raw.exists() and load(raw) is None:\n                continue"),
            ('return dict(v=1,', 'return dict(v=True,'),
        ]
        for old,new in mutations:
            with self.subTest(mutation=old):
                candidate = json.loads((DIAG/'valid.json').read_text())
                source = 'modules/llmdiag/aos7_llmdiag.py'
                self.assertIn(old,candidate['files'][source])
                candidate['files'][source] = candidate['files'][source].replace(old,new)
                candidate['files']['modules/llmdiag/tests/test_llmdiag.py'] = 'import unittest\nclass T(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n'
                code,out = self.candidate_check(candidate,DIAG)
                self.assert_failure(code,out,2,'answer')

    def test_aos_requests_include_precise_contract(self):
        request = json.loads((USAGE/'request.json').read_text())
        work = '\n'.join(request['work'])
        accept = '\n'.join(request['accept'])
        for text in [work,accept]:
            for required in ['raw.json', 'epoch 秒', 'UTC', 'YYYY-MM-DD', 'YYYY-MM-DDTHH', 'day', 'hour', '"-"']:
                self.assertIn(required,text)
            self.assertRegex(text,r'預設.{0,3}day')
        request = json.loads((DIAG/'request.json').read_text())
        work = '\n'.join(request['work'])
        for required in ['8', 'hex', 'phase', 'halted', 'raw', 'request', 'receipt.json', 'inflight', '排序']:
            self.assertIn(required,work)
        self.assertIn('壞 raw',work)
