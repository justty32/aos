#!/usr/bin/env python3
"""scan: check files that will be published for private values and secrets.

Usage: scan.py [--private FILE] PATH...
  PATH = files or folders (walked). --private FILE = one value per line ('#' = comment), kept
  outside the repo; each is matched case-insensitively on word boundaries, also URL-encoded.
  Built-in rules (no private data in this file): key shapes (sk-, ghp_, github_pat_, xox?-,
  AKIA, private key headers, Bearer tokens), any /home/<name>/ path, e-mail addresses,
  private IPv4 ranges, SVG editor metadata (sodipodi, inkscape:export-filename, <metadata>),
  PNG text chunks / JPEG EXIF, and any other file that is not UTF-8 text.
Output: one line per hit 'FILE:LINE: RULE: TEXT'; last line 'scan: N hits in M files'.
Exit: 0 no hits, 1 hits, 2 bad arguments.
"""
import os
import re
import sys
import urllib.parse

RULES = [
    ('key-openai', re.compile(r'\bsk-[A-Za-z0-9_-]{16,}')),
    ('key-github', re.compile(r'\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}')),
    ('key-slack', re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}')),
    ('key-aws', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('key-private', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('bearer', re.compile(r'Bearer\s+[A-Za-z0-9._~+/-]{20,}')),
    ('home-path', re.compile(r'/home/[A-Za-z0-9_.-]+')),
    ('email', re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')),
    ('private-ip', re.compile(r'\b(10\.\d{1,3}|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b')),
    ('svg-meta', re.compile(r'sodipodi:|inkscape:export-filename|<metadata[\s>]')),
]
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def load_private(path):
    vals = []
    for line in open(path, encoding='utf-8'):
        v = line.strip()
        if v and not v.startswith('#'):
            vals.append(v)
    pats = []
    for v in vals:
        forms = {v, urllib.parse.quote(v, safe='')}
        for f in forms:
            pats.append(('private', re.compile(r'(?<![A-Za-z0-9])' + re.escape(f) + r'(?![A-Za-z0-9])', re.I)))
    return pats


def image_hits(path, data):
    hits = []
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        for chunk in (b'tEXt', b'iTXt', b'zTXt', b'eXIf'):
            if chunk in data:
                hits.append('png-chunk %s' % chunk.decode())
    elif data[:2] == b'\xff\xd8' and b'Exif' in data[:65536]:
        hits.append('jpeg-exif')
    return hits


def scan_file(path, rules, report):
    ext = os.path.splitext(path)[1].lower()
    data = open(path, 'rb').read()
    if ext in IMAGE_EXT:
        for h in image_hits(path, data):
            report(path, 0, 'image-meta', h)
        return
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = None
    if text is None or b'\x00' in data[:8192]:
        report(path, 0, 'binary', 'not a text file (%d bytes)' % len(data))
        return
    for n, line in enumerate(text.split('\n'), 1):
        for name, rx in rules:
            m = rx.search(line)
            if m:
                report(path, n, name, line.strip()[:160])


def main(argv):
    rules = list(RULES)
    paths = []
    i = 0
    while i < len(argv):
        if argv[i] == '--private':
            if i + 1 >= len(argv) or not os.path.isfile(argv[i + 1]):
                print('scan: error: ArgumentsBad --private needs a file', file=sys.stderr)
                return 2
            rules += load_private(argv[i + 1])
            i += 2
        else:
            paths.append(argv[i])
            i += 1
    if not paths:
        print('scan: error: ArgumentsBad usage: scan.py [--private FILE] PATH...', file=sys.stderr)
        return 2
    hits, files_hit = [0], set()

    def report(path, line, rule, text):
        hits[0] += 1
        files_hit.add(path)
        print('%s:%d: %s: %s' % (path, line, rule, text))

    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
                for f in sorted(files):
                    scan_file(os.path.join(root, f), rules, report)
        elif os.path.isfile(p):
            scan_file(p, rules, report)
        else:
            print('scan: error: ArgumentsBad %s does not exist' % p, file=sys.stderr)
            return 2
    print('scan: %d hits in %d files' % (hits[0], len(files_hit)))
    return 1 if hits[0] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
