# Verify the code map dependency tables (wf/knowledge/code-map/deps/{cpp,py,bin}.json): who links whom from cpp/Makefile, who imports which aos modules, which source each bin/ command runs; wf-table/1 shape readable by tabledb.
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import codemap_deps  # noqa: E402
import index_gen  # noqa: E402
import tabledb  # noqa: E402

DEPS = 'wf/knowledge/code-map/deps'
MAKEFILE = """# Builds a toy family.
LIBS := util post daemon
BINS := post daemon
DEPS_util      :=
DEPS_post      := util
DEPS_daemon    := post util \\
                  inst
$(LIBDIR)/libaos-inst.a: $(inst_obj)
\tar rcs $@ $^
$(LIBDIR)/libaos-inst.so: $(inst_obj)
\t$(CC) -shared -o $@ $^
define cxx_project
$(1)_src := $$(shell find aos-$(1)/src)
endef
"""


class CodemapDepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        files = [('proto8/cpp/Makefile', MAKEFILE),
                 ('proto8/cpp/aos-inst/src/inst.c', '// inst.c - the C library.\n'),
                 ('proto8/cpp/aos-util/src/io.cpp', '// io.cpp - io.\n'),
                 ('proto8/cpp/aos-post/src/main.cpp', '// main.cpp - post cli.\n'),
                 ('proto8/cpp/aos-daemon/src/main.cpp', '// main.cpp - daemon cli.\n'),
                 ('proto8/py/entries.json', json.dumps({'description': 'cmds', 'commands': {'aos-hello': 'aos.apps.hello.main',
                                                                                            'aos-gone': 'aos.apps.gone.main'}})),
                 ('proto8/py/aos/__init__.py', '"""aos - the package."""\n'),
                 ('proto8/py/aos/flags.py', '"""flags - flags."""\nfrom aos import tool_io\n'),
                 ('proto8/py/aos/tool_io.py', '"""tool_io - io."""\nimport os\n'),
                 ('proto8/py/aos/agentlib/__init__.py', '"""agentlib - agent layer."""\n'),
                 ('proto8/py/aos/agentlib/hooks.py', '"""hooks - hooks."""\nfrom aos import tool_io\nfrom aos.agentlib import cooldown\n'),
                 ('proto8/py/aos/agentlib/cooldown.py', '"""cooldown - wait."""\n'),
                 ('proto8/py/aos/apps/__init__.py', '"""apps."""\n'),
                 ('proto8/py/aos/apps/hello/__init__.py', '"""hello."""\n'),
                 ('proto8/py/aos/apps/hello/main.py', '"""hello - says hello."""\nfrom aos import flags as aos_flags, tool_io  # two\n'
                                                      'from . import part\n'
                                                      'def f():\n    from aos.agentlib import (hooks,\n        cooldown)\n'
                                                      '    from aos.apps.hello import part\n    import aos.ws, json\n'),
                 ('proto8/py/aos/apps/hello/part.py', '"""part - a part."""\n'),
                 ('proto8/py/aos/apps/quiet/main.py', '"""quiet - imports nothing from aos."""\nimport os\n'),
                 ('proto8/py/tools/base/echo/_entry', '#!/usr/bin/env python3\n# echo - echo.\nfrom aos.tool_io import Error\n'),
                 ('proto8/py/tools/base/echo/_tooldef.json', '{"description": "echo"}'),
                 ('proto8/py/tools/base/echo/tests/test_echo.py', 'from aos import flags\n'),
                 ('proto8/py/tools/base/plain/_entry', '#!/bin/sh\n# plain - shell.\n'),
                 ('proto8/templates/agents/fsm/act.py', '"""act."""\nfrom aos import tool_io\n'),
                 ('proto8/py/tests/test_x.py', 'from aos import flags\n')]
        for rel, text in files:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_gen(self, *args):
        cfg = dict(index_gen.load('index_gen.json'), scopes=[{'path': 'proto8', 'stage': 1}])
        real = index_gen.load
        index_gen.load = lambda name: cfg if name == 'index_gen.json' else {'desc': {}}
        try:
            return index_gen.main(['--root', str(self.root), '--quiet', *args])
        finally:
            index_gen.load = real

    def rows(self, name, key):
        t = tabledb.load(str(self.root / DEPS / name))
        self.assertEqual(t.meta['contract'], 'wf-table/1')
        self.assertEqual(t.meta['generated_by'], 'wf/tools/index_gen.py')
        for r in t.rows:
            self.assertEqual(sorted(r), sorted(t.columns))                # 每列同一組欄位
        return {r[key]: r for r in t.rows}

    def test_makefile_vars(self):
        v = codemap_deps.makefile_vars(MAKEFILE)
        self.assertEqual(v['DEPS_daemon'].split(), ['post', 'util', 'inst'])   # 接續行接起來
        self.assertEqual(v['DEPS_util'], '')
        self.assertFalse(any(k.endswith('_src') for k in v))                # define 裡的 $(1)_src 不算
        self.assertEqual(v['LIBS'].split(), ['util', 'post', 'daemon'])

    def test_cpp_table(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        cpp = self.rows('cpp.json', 'project')
        self.assertEqual(sorted(cpp), ['aos-daemon', 'aos-inst', 'aos-post', 'aos-util'])
        self.assertEqual(cpp['aos-daemon']['links'], 'aos-post aos-util aos-inst')            # 照 Makefile 的連結順序
        self.assertEqual(cpp['aos-daemon']['products'], 'libaos-daemon.a bin/aos-daemon')
        self.assertEqual(cpp['aos-inst']['products'], 'libaos-inst.a libaos-inst.so')         # 明寫的目標
        self.assertEqual(cpp['aos-inst']['lang'], 'C')
        self.assertEqual(cpp['aos-util']['used_by'], 'aos-daemon aos-post')
        self.assertEqual(cpp['aos-util']['products'], 'libaos-util.a')                         # 不在 BINS：沒有執行檔

    def test_py_table(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        py = self.rows('py.json', 'unit')
        hello = py['proto8/py/aos/apps/hello']
        self.assertEqual(hello['kind'], 'app')
        self.assertEqual(hello['uses'], 'aos.agentlib.cooldown aos.agentlib.hooks aos.flags aos.tool_io aos.ws')  # 括號跨行、縮排、import 都認；自己的不算
        self.assertEqual(py['proto8/py/aos/apps/quiet']['uses'], '')                          # 指令每支都列
        self.assertEqual(py['proto8/py/aos/tool_io.py']['used_by'],
                         'proto8/py/aos/agentlib proto8/py/aos/apps/hello proto8/py/aos/flags.py proto8/py/tools/base/echo proto8/templates/agents/fsm')
        self.assertEqual(py['proto8/py/aos/agentlib']['uses'], 'aos.tool_io')                 # 子套件裡互相 import 不算
        self.assertEqual(py['proto8/py/tools/base/echo']['uses'], 'aos.tool_io')              # `from aos.tool_io import Error`：Error 不是模組
        self.assertNotIn('proto8/py/tools/base/plain', py)                                    # shell 工具、沒用到 aos 的工具不列
        self.assertNotIn('proto8/py/aos/apps', py)                                            # apps/__init__.py 不算單位
        self.assertFalse(any('tests' in u for u in py))                                        # tests 不掃

    def test_bin_table(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        b = self.rows('bin.json', 'command')
        self.assertEqual(sorted(b), ['aos-daemon', 'aos-gone', 'aos-hello', 'aos-post'])
        self.assertEqual(b['aos-hello']['source'], 'proto8/py/aos/apps/hello/main.py')
        self.assertEqual(b['aos-hello']['module'], 'aos.apps.hello.main')
        self.assertEqual(b['aos-gone']['source'], '')                                         # entries.json 指到不存在的模組：source 空
        self.assertEqual(b['aos-daemon'], {'command': 'aos-daemon', 'lang': 'C++', 'source': 'proto8/cpp/aos-daemon/src/main.cpp',
                                           'module': '', 'from': 'proto8/cpp/Makefile'})

    def test_stale_and_dropped(self):
        self.assertEqual(self.run_gen('--apply'), 0)
        self.assertEqual(self.run_gen(), 0)
        mk = self.root / 'proto8/cpp/Makefile'
        mk.write_text(MAKEFILE.replace('DEPS_post      := util', 'DEPS_post      := util inst'), encoding='utf-8')
        self.assertEqual(self.run_gen(), 1)                                                   # Makefile 改了：依賴表 stale
        self.assertEqual(self.run_gen('--apply'), 0)
        self.assertEqual(self.rows('cpp.json', 'project')['aos-post']['links'], 'aos-util aos-inst')
        subprocess.run(['git', '-C', str(self.root), 'rm', '-rqf', 'proto8/cpp'], check=True)
        self.assertEqual(self.run_gen(), 1)                                                   # 沒有 Makefile：cpp.json 該收掉
        self.assertEqual(self.run_gen('--apply'), 0)
        self.assertFalse((self.root / DEPS / 'cpp.json').exists())
        self.assertTrue((self.root / DEPS / 'py.json').exists())

    def test_hand_written_file_untouched(self):
        (self.root / DEPS).mkdir(parents=True)
        (self.root / DEPS / 'notes.json').write_text('{"description": "hand"}\n', encoding='utf-8')
        self.assertEqual(self.run_gen('--apply'), 0)
        self.assertTrue((self.root / DEPS / 'notes.json').exists())                          # 沒有 generated_by 的不碰


class SymlinkModeTests(unittest.TestCase):
    """git 記成捷徑、工作樹卻是內容＝目標的小檔（core.symlinks=false 的 Windows 複本）：逐檔表一樣印「→ 目標」。"""

    def test_link_recorded_by_git(self):
        import codemap_lib
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'proto8/lib').mkdir(parents=True)
            (root / 'proto8/lib/inner').write_text('../tools/shell', encoding='utf-8')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            blob = subprocess.run(['git', '-C', str(root), 'hash-object', '-w', 'proto8/lib/inner'],
                                  capture_output=True, text=True, check=True).stdout.strip()
            subprocess.run(['git', '-C', str(root), 'update-index', '--add', '--cacheinfo', '120000,%s,proto8/lib/inner' % blob], check=True)
            proto = os.path.join(d, 'proto8')
            self.assertEqual(codemap_lib.tracked(proto), ['lib/inner'])
            self.assertEqual(codemap_lib.describe(proto, 'lib/inner'), ('→ `../tools/shell`', False))
            self.assertEqual(codemap_lib.describe(proto, 'lib/inner', follow=True), ('', True))   # 指到樹外：不跟（有沒有裝過都一樣）

    def test_tool_dir_on_any_os(self):
        import codemap_lib
        files = ['t/box/_entry', 't/box/_metainfo.json', 't/box/_tooldef.json', 't/box/x.py']
        self.assertEqual(codemap_lib.units('unused', files),
                         [('t/box/', ['t/box/_entry', 't/box/_tooldef.json', 't/box/_metainfo.json']), ('t/box/x.py', ['t/box/x.py'])])


if __name__ == '__main__':
    unittest.main()
