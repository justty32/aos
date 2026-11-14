#!/usr/bin/env python3
"""check-cmds: every command line in the copies must also be in the master page (the page you run literally
with run-doc.py), so README / landing-page quickstarts cannot drift from it.
Usage: check-cmds.py MASTER.md COPY [COPY...]   (COPY = .md or .html; reads ```bash/```sh blocks or <pre> blocks)
Normalizes: quotes around $AOS_HOME/$HOME paths, $HOME/ -> ~/, trailing comments, ' && ' chains, whitespace; only lines that start with a command word count (so outputs inside <pre> are skipped). Lines only in the copy are printed.
Exit: 0 all found, 1 some missing, 2 bad arguments."""
import html, re, sys

def lines_of(path):
    t = open(path, encoding='utf-8').read()
    if path.endswith('.html'):
        blocks = [html.unescape(re.sub(r'<[^>]+>', '', b)) for b in re.findall(r'<pre[^>]*>(.*?)</pre>', t, re.S)]
    else:
        blocks = re.findall(r'```(?:bash|sh)\n(.*?)```', t, re.S)
    out = []
    cmd = re.compile(r'^(aos-|cd |cp |mkdir |nohup |export |git |cmake |tail |ls |timeout |sleep |echo |chmod |cat |for )')
    for b in blocks:
        for ln in b.splitlines():
            ln = ln.strip().removeprefix('$ ')
            ln = re.sub(r'\s+#.*$', '', ln).strip()
            ln = re.sub(r'"(\$(?:AOS_HOME|HOME)[^"]*)"', r'\1', ln).replace('$HOME/', '~/')
            for part in ln.split(' && '):
                part = re.sub(r'\s+', ' ', part).strip()
                if cmd.match(part):
                    out.append(part)
    return out

def main(a):
    if len(a) < 2:
        print(__doc__, file=sys.stderr); return 2
    master = set(lines_of(a[0]))
    bad = 0
    for c in a[1:]:
        for ln in lines_of(c):
            if ln not in master:
                print('%s: not in master: %s' % (c, ln)); bad += 1
    print('check-cmds: %d lines not in master' % bad)
    return 1 if bad else 0

sys.exit(main(sys.argv[1:]))
