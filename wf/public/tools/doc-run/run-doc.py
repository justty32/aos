#!/usr/bin/env python3
"""run-doc: pull every ```bash / ```sh block out of a Markdown page, in order, into one script, so the page
itself is what gets tested. <REPO_URL> is replaced by the given URL.
Usage: run-doc.py PAGE.md REPO_URL OUT.sh
"""
import re
import sys

page, url, out = sys.argv[1:4]
md = open(page, encoding='utf-8').read()
blocks = re.findall(r'```(?:bash|sh)\n(.*?)```', md, re.S)
body = '\n'.join(b.replace('<REPO_URL>', url) for b in blocks)
open(out, 'w').write('#!/usr/bin/env bash\nset -x\n' + body)
print('run-doc: %d blocks -> %s' % (len(blocks), out))
