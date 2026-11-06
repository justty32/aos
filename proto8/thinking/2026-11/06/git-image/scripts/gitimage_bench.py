#!/usr/bin/env python3
"""Benchmark synthetic frozen aos images with bounded disk, time, and cleanup."""
import argparse
import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
import zlib

ROOT = Path('/tmp/i-team')
IGNORE = '''**/tmp/
**/archive/
**/.*.tmp
**/.*.[0-9]*
**/stderr.txt
**/live.jsonl
**/turns.jsonl
**/think/request.json
**/queue.json
**/mailbox_warning.txt
**/transcripts/
**/*.sock
**/lock
**/.flock
**/sender.flock
**/.reply.lock
**/mcp.json
**/tmux.conf
**/busy.txt
.trash/
'''
GIT = ['nice', '-n', '19', 'git', '-c', 'core.fsmonitor=false',
       '-c', 'gc.auto=0', '-c', 'pack.threads=1']
CAP = 2 * 1024 ** 3


class Limit(Exception):
    pass


class Bench:
    def __init__(self, args, rounds, attempt):
        self.a, self.n, self.attempt = args, rounds, attempt
        self.start = time.monotonic()
        self.deadline = self.start + args.max_seconds
        self.repo = ROOT / 'run' / args.mode
        self.temp = ROOT / 'run' / 'transfer'
        self.rng = random.Random(args.seed)
        self.allocated_estimate = 0
        self.peak_sampled_allocated = 0
        self.commits = 0
        self.first_auto = None
        self.id = f'{args.mode}{"+archive" if args.archive else ""}-M{args.agents}-N{args.rounds}-K{args.commit_every}'
        if args.packing:
            self.id += f'-h{args.history_bytes}-{args.packing}'
        words = set()
        for p in sorted(Path(sysconfig.get_path('stdlib')).glob('*.py')):
            words.update(w.lower() for w in re.findall(r'\b[A-Za-z]{4,14}\b', p.read_text(errors='ignore')))
        self.words = sorted(w for w in words if len(w) >= 5)
        random.Random(17).shuffle(self.words)
        self.words = self.words[:4096]
        self.vocab_hash = hashlib.sha256(' '.join(self.words).encode()).hexdigest()
        self.prose_rng = random.Random(args.seed + 100)
        sample = self.prose(200000).encode()
        self.compression = len(sample) / len(zlib.compress(sample))

    def emit(self, kind, **data):
        item = dict(kind=kind, scenario=self.id, mode=self.a.mode,
                    archive=self.a.archive, agents=self.a.agents,
                    requested_rounds=self.a.rounds, rounds=self.n,
                    commit_every=self.a.commit_every, attempt=self.attempt, **data)
        with self.a.out.open('a') as f:
            f.write(json.dumps(item, separators=(',', ':')) + '\n')
        if kind != 'commit':
            print(json.dumps(item), flush=True)

    def check(self, reserve=0, exact=False):
        if time.monotonic() >= self.deadline:
            raise Limit('600-second scenario deadline' if self.a.max_seconds == 600 else 'scenario deadline')
        if exact:
            self.allocated_estimate = int(self.command(['nice', '-n', '19', 'du', '-s', '-B1', str(ROOT)], cwd=ROOT)[0].split()[0])
        self.peak_sampled_allocated = max(self.peak_sampled_allocated, self.allocated_estimate)
        # Leave 64 MiB for logs, directory growth, and command metadata.
        if self.allocated_estimate + reserve > CAP - 64 * 1024 ** 2:
            raise Limit(f'disk budget: allocated={self.allocated_estimate}, reserve={reserve}, limit={CAP}')

    def command(self, cmd, cwd=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Limit('scenario deadline')
        t = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=cwd or self.repo, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
        try:
            out, err = proc.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)  # Only this benchmark's own child group.
            proc.communicate()
            raise Limit('scenario deadline during ' + ' '.join(cmd))
        if proc.returncode:
            raise RuntimeError(f'{cmd}: {err.decode(errors="replace")[-2000:]}')
        return out.decode(), time.monotonic() - t

    def git(self, *args, cwd=None):
        return self.command(GIT + list(args), cwd)

    def prose(self, size):
        parts, length = [], 0
        frames = [
            'The {} service checks {} and records {} with {} before the next {} operation. ',
            'We inspect {} {} {} while the {} {} result is available for {} review. ',
            'After {} {} the worker resolves {} {} and returns {} {} to the caller. ',
        ]
        while length < size:
            frame = self.prose_rng.choice(frames)
            text = frame.format(*(self.prose_rng.choice(self.words) for _ in range(frame.count('{}'))))
            parts.append(text)
            length += len(text)
        return ''.join(parts)[:size]

    def record(self, size, **fields):
        fields['text'] = ''
        overhead = len(json.dumps(fields, separators=(',', ':')).encode()) + 1
        fields['text'] = self.prose(max(0, size - overhead))
        return (json.dumps(fields, separators=(',', ':')) + '\n').encode()

    def write(self, p, data, append=False):
        if not p.parent.exists():
            missing, parent = 0, p.parent
            while not parent.exists():
                missing += 1
                parent = parent.parent
            p.parent.mkdir(parents=True)
            self.allocated_estimate += 4096 * missing
        exists = p.exists()
        before = p.stat().st_size if exists else 0
        with p.open('ab' if append else 'wb') as f:
            f.write(data)
        after = before + len(data) if append else len(data)
        self.allocated_estimate += (math.ceil(after / 4096) - math.ceil(before / 4096)) * 4096
        if not exists:
            self.allocated_estimate += 512

    def du(self, path):
        return int(self.command(['nice', '-n', '19', 'du', '-sb', str(path)])[0].split()[0])

    def counts(self):
        return {k: int(v) for k, v in (line.split(': ') for line in self.git('count-objects', '-v')[0].splitlines())}

    def tree_stats(self):
        count = size = 0
        for base, dirs, files in os.walk(self.repo):
            if Path(base) == self.repo:
                dirs[:] = [d for d in dirs if d != '.git']
            for name in files:
                count += 1
                size += (Path(base) / name).stat().st_size
        return count, size

    def setup(self):
        self.repo.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Image Benchmark')
        self.git('config', 'user.email', 'bench@example.invalid')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'core.fsmonitor', 'false')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', '/dev/null')
        if self.a.mode != 'A':
            ignore = IGNORE
            if self.a.mode in ('E', 'F'):
                ignore = ignore.replace('**/think/request.json\n', '')
            if self.a.mode == 'C':
                ignore += '**/history.old/\nws/.stack/procs/t-*/\n'
            # Root .trash/ does not match ws/.trash; preserve the requested list and add the real path.
            ignore += 'ws/.trash/\n'
            self.write(self.repo / '.gitignore', ignore.encode())
        self.histories = [bytearray() for _ in range(self.a.agents)]
        self.tails = [collections.deque() for _ in self.histories]
        self.segment = [1] * self.a.agents
        self.segment_bytes = [0] * self.a.agents
        for i in range(self.a.agents):
            for j in range(10):
                self.write(self.repo / f'definitions/agent-{i:03d}/config-{j}.json', self.record(2048, agent=i, key=j))
            p = self.repo / f'ws/.stack/procs/agent-{i:03d}'
            for path in ['tmp/cache.json', '.cache.tmp', '.cache.123', 'turns.jsonl',
                         'mailbox_warning.txt', 'transcripts/session.jsonl', 'worker.sock',
                         'lock', '.flock', 'sender.flock', '.reply.lock', 'mcp.json',
                         'tmux.conf', 'busy.txt']:
                self.write(p / path, self.record(128, temporary=True))
            self.write(p / 'loop.json', b'{"enabled":true,"interval_ms":1000}\n')
            self.write(p / 'stderr.txt', b'')
        self.system = self.record(2048, role='system').strip()
        self.tools = self.record(4096, role='tools').strip()

    def turn(self, n):
        for i in range(self.a.agents):
            p = self.repo / f'ws/.stack/procs/agent-{i:03d}'
            sizes = [200, 400, (self.a.history_bytes - 600) // 2,
                     self.a.history_bytes - 600 - (self.a.history_bytes - 600) // 2]
            lines = [self.record(size, role=role, round=n) for size, role in
                     zip(sizes, ['user', 'assistant', 'tool', 'tool'])]
            addition = b''.join(lines)
            self.histories[i].extend(addition)
            if self.a.mode == 'C':
                tail = self.tails[i]
                for line in lines:
                    tail.append(line)
                    if len(tail) > 64:
                        self.write(p / 'history.old/older.jsonl', tail.popleft(), True)
                self.write(p / 'history.jsonl', b''.join(tail))
            elif self.a.mode in ('D', 'F'):
                for line in lines:
                    if self.segment_bytes[i] + len(line) > self.a.segment_bytes:
                        self.segment[i] += 1
                        self.segment_bytes[i] = 0
                    self.write(p / f'history/{self.segment[i]:06d}.jsonl', line, True)
                    self.segment_bytes[i] += len(line)
            else:
                self.write(p / 'history.jsonl', addition, True)
            request = (b'{"system":' + self.system + b',"tools":' + self.tools +
                       b',"history":[' + b','.join(self.histories[i].splitlines()) + b']}\n')
            self.write(p / 'think/request.json', request)
            self.write(p / 'state.json', self.record(400, updated_at=1700000000+n*60, turns=n, agent=i))
            self.write(p / 'stage.txt', b'idle\n')
            self.write(p / 'loop.json', b'{"enabled":true,"interval_ms":1000}\n')
            if self.rng.random() < .1:
                self.write(p / 'stderr.txt', self.record(200, level='warning', round=n), True)
            if i < self.a.agents // 5:
                self.write(p / 'claude/live.jsonl', self.record(self.a.live_bytes, type='stream', round=n), True)
            if self.rng.random() < .01:
                child = self.repo / f'ws/.stack/procs/t-{i}-{1700000000000+n*60000}-{self.rng.randrange(65536):04x}'
                k = self.rng.randint(3, 10)
                self.write(child / 'history.jsonl', self.record(k*self.a.history_bytes, role='assistant', turns=k))
                self.write(child / 'state.json', self.record(400, kept=True, turns=k))
                self.write(child / 'stderr.txt', self.record(200, level='info'))
            if self.rng.random() < .01:
                stamp = datetime.datetime.fromtimestamp(1700000000+n*60, datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
                self.write(self.repo / f'ws/.trash/{stamp}/agent-{i}.json', self.record(2048, deleted=True))
            if self.a.archive:
                for j, size in enumerate([300, 0, 1024, 500, 500]):
                    letter = (b'{"body":' + request.strip() + b',"kind":"kernel_request"}\n') if j == 1 else self.record(size, kind=['say', '', 'reply', 'procs_ctl', 'procs_ctl'][j], round=n)
                    box = p if j < 3 else self.repo / 'ws/.stack/procs_ctl'
                    name = f'{1700000000000000000+n*60000000000+i*10+j:020d}.{1000+i}.{n*5+j}'
                    self.write(box / f'archive/{name}/letter.json', letter)
        for name in ['used', 'queue']:
            self.write(self.repo / f'ws/.stack/kernel/{name}.json', self.record(200, round=n, name=name))
        self.check(reserve=32*1024**2)

    def freeze(self, n):
        self.write(self.repo / 'ws/.stack/procs_state.json',
                   b'[' + b','.join(self.record(400, agent=i, round=n).strip() for i in range(self.a.agents)) + b']\n')
        self.check(exact=True, reserve=32*1024**2)
        files, size = self.tree_stats()
        add_reserve = min(size, sum(map(len, self.histories))*2 + 16*1024**2) if self.a.packing else size
        self.check(reserve=add_reserve + 32*1024**2)
        _, status = self.git('status', '--porcelain')
        _, add = self.git('add', '-A')
        _, commit = self.git('commit', '-q', '-m', f'Frozen at round {n}')
        self.commits += 1
        counts = self.counts()
        # Git 2.43 samples objects/17: >ceil(6700/256)=27, so >=28 triggers.
        bucket = self.repo / '.git/objects/17'
        sample_count = sum(1 for p in bucket.iterdir() if p.is_file() and len(p.name) == 38) if bucket.exists() else 0
        packs = len(list((self.repo / '.git/objects/pack').glob('*.pack')))
        trigger = sample_count > (6700 + 255) // 256 or packs > 50
        if trigger and self.first_auto is None:
            self.first_auto = dict(commit=self.commits, round=n, sample_17=sample_count,
                                   loose=counts['count'], packs=packs)
        self.emit('commit', workspace_allocated_bytes=self.allocated_estimate, round=n, commit_index=self.commits, worktree_files=files,
                  worktree_bytes=size, status_s=status, add_s=add, commit_s=commit,
                  git_bytes=self.du(self.repo / '.git'), objects=counts,
                  auto_sample_17=sample_count, auto_would_trigger=trigger)
        self.check(exact=True)

    def measure_packing(self, before, loose):
        commands = {
            'a': ['gc', '--prune=now'],
            'b': ['repack', '-adf', '--window=250', '--depth=50'],
            'c': ['repack', '-adf', '--window=1000', '--depth=250'],
            'config250': ['-c', 'pack.window=250', 'gc', '--prune=now'],
        }
        self.emit('packing_start', packing=self.a.packing, git_before_bytes=before,
                  loose_before=loose, build_s=time.monotonic()-self.start)
        _, elapsed = self.git(*commands[self.a.packing])
        after = self.du(self.repo / '.git')
        self.emit('packing_done', packing=self.a.packing, gc_s=elapsed,
                  git_before_bytes=before, git_after_bytes=after, packed_after=self.counts())
        depths = []
        types = collections.Counter()
        for idx in (self.repo / '.git/objects/pack').glob('*.idx'):
            raw, _ = self.git('verify-pack', '-v', str(idx))
            for line in raw.splitlines():
                parts = line.split()
                if len(parts) >= 5 and len(parts[0]) in (40, 64) and parts[1] in ('blob','tree','commit','tag'):
                    types[parts[1]] += 1
                    if len(parts) == 7:
                        depths.append(int(parts[5]))
        # Record final tracked content as the capacity floor for extrapolation.
        tracked = self.git('ls-files', '-z')[0].split('\0')
        self.emit('measurement', status='ok', packing=self.a.packing,
                  git_before_bytes=before, git_after_bytes=after, loose_before=loose,
                  packed_after=self.counts(), gc_s=elapsed,
                  verify_objects=sum(types.values()), verify_types=dict(types),
                  delta_objects=len(depths), delta_depth_sum=sum(depths),
                  delta_mean_depth=sum(depths)/len(depths) if depths else 0,
                  delta_max_depth=max(depths, default=0),
                  tracked_bytes=sum((self.repo/p).stat().st_size for p in tracked if p),
                  tracked_request_files=sum(p.endswith('/think/request.json') for p in tracked),
                  tracked_history_segments=sum('/history/' in p for p in tracked),
                  tracked_archive_files=sum('/archive/' in p for p in tracked),
                  peak_sampled_allocated_bytes=self.peak_sampled_allocated,
                  elapsed_s=time.monotonic()-self.start)
        # Parentless final tree measures the content floor; recorded separately from the trial.
        tree = self.git('rev-parse', 'HEAD^{tree}')[0].strip()
        orphan = self.git('commit-tree', tree, '-m', 'Squashed final image')[0].strip()
        branch = self.git('symbolic-ref', 'HEAD')[0].strip()
        self.git('update-ref', branch, orphan)
        self.git('reflog', 'expire', '--expire=now', '--all')
        self.check(exact=True, reserve=after + 32*1024**2)
        _, squash_gc_s = self.git('gc', '--prune=now')
        self.emit('image', squash_bytes=self.du(self.repo / '.git'), squash_gc_s=squash_gc_s)

    def run(self):
        self.emit('start', git_version=self.command(GIT + ['--version'], cwd=ROOT)[0].strip(),
                  seed=self.a.seed, configured_pack_threads=int(next(x.split('=')[1] for x in GIT if x.startswith('pack.threads='))), configured_nice_argument=int(GIT[2]), effective_nice=os.getpriority(os.PRIO_PROCESS, 0), vocabulary_words=len(self.words), vocabulary_sha256=self.vocab_hash,
                  prose_zlib_ratio=self.compression, history_bytes=self.a.history_bytes,
                  live_bytes=self.a.live_bytes, segment_bytes=self.a.segment_bytes,
                  note='Warm filesystem cache; sequential scenarios; all git commands nice 19, pack threads 1.')
        self.setup()
        for n in range(1, self.n + 1):
            self.turn(n)
            if n % self.a.commit_every == 0 or n == self.n:
                self.freeze(n)
        before, loose = self.du(self.repo / '.git'), self.counts()
        # Packing may temporarily coexist with all loose objects.
        self.check(exact=True, reserve=before + 32*1024**2)
        if self.a.packing:
            self.measure_packing(before, loose)
            return
        _, gc_s = self.git('gc', '--prune=now')
        after, packed = self.du(self.repo / '.git'), self.counts()
        self.emit('phase', phase='post_gc', git_after_bytes=after, packed_after=packed, gc_s=gc_s)
        tracked_bytes = sum((self.repo / p).stat().st_size for p in self.git('ls-files', '-z')[0].split('\0') if p)
        self.check(exact=True, reserve=after + tracked_bytes + self.tree_stats()[0]*12288 + 64*1024**2)
        _, clone_s = self.git('clone', '-q', '--no-local', str(self.repo), str(self.temp))
        clone_bytes, clone_git = self.du(self.temp), self.du(self.temp / '.git')
        self.emit('phase', phase='clone', clone_bytes=clone_bytes, clone_git_bytes=clone_git, clone_s=clone_s)
        shutil.rmtree(self.temp)
        self.check(exact=True, reserve=after + tracked_bytes + self.tree_stats()[0]*12288 + 64*1024**2)
        _, depth_s = self.git('clone', '-q', '--depth', '1', self.repo.as_uri(), str(self.temp))
        depth_bytes, depth_git = self.du(self.temp), self.du(self.temp / '.git')
        self.emit('phase', phase='depth1', depth1_bytes=depth_bytes, depth1_git_bytes=depth_git, depth1_s=depth_s)
        shutil.rmtree(self.temp)
        # Same final tree, a genuinely parentless commit, no old refs or reflogs.
        tree = self.git('rev-parse', 'HEAD^{tree}')[0].strip()
        orphan = self.git('commit-tree', tree, '-m', 'Squashed final image')[0].strip()
        branch = self.git('symbolic-ref', 'HEAD')[0].strip()
        self.git('update-ref', branch, orphan)
        self.git('reflog', 'expire', '--expire=now', '--all')
        self.check(exact=True, reserve=after + 32*1024**2)
        _, squash_gc_s = self.git('gc', '--prune=now')
        squash = self.du(self.repo / '.git')
        self.emit('result', status='ok', commits=self.commits, git_before_bytes=before,
                  git_after_bytes=after, loose_before=loose, packed_after=packed,
                  peak_sampled_allocated_bytes=self.peak_sampled_allocated, gc_s=gc_s, clone_s=clone_s, clone_bytes=clone_bytes, clone_git_bytes=clone_git,
                  depth1_s=depth_s, depth1_bytes=depth_bytes, depth1_git_bytes=depth_git,
                  squash_bytes=squash, squash_gc_s=squash_gc_s,
                  tracked_bytes=tracked_bytes, auto_first_trigger=self.first_auto,
                  elapsed_s=time.monotonic()-self.start)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agents', type=int, required=True)
    p.add_argument('--rounds', type=int, required=True)
    p.add_argument('--commit-every', type=int, required=True)
    p.add_argument('--mode', choices=list('ABCDEF'), required=True)
    p.add_argument('--packing', choices=['a','b','c','config250'], help='Task 2: measure packing and verify-pack only; no scale retries.')
    p.add_argument('--archive', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--history-bytes', type=int, default=3072)
    p.add_argument('--live-bytes', type=int, default=20480)
    p.add_argument('--segment-bytes', type=int, default=65536)
    p.add_argument('--seed', type=int, default=20261106)
    p.add_argument('--max-seconds', type=int, default=600)
    a = p.parse_args()
    if min(a.agents, a.rounds, a.commit_every) < 1 or a.history_bytes < 1000:
        p.error('Agents, rounds, and commit interval must be positive; history must be >=1000 bytes.')
    a.out = a.out.resolve()
    if not a.out.is_relative_to(ROOT):
        p.error('Output must be inside /tmp/i-team.')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'run').mkdir(exist_ok=True)
    # Respect the requested low priority even when called without the shell wrapper.
    if os.getpriority(os.PRIO_PROCESS, 0) < 19:
        os.nice(19 - os.getpriority(os.PRIO_PROCESS, 0))
    n, attempt = a.rounds, 1
    while n >= 1:
        b = Bench(a, n, attempt)
        if b.repo.exists() or b.temp.exists():
            raise RuntimeError('Existing benchmark data found; refuse to delete unowned previous work.')
        try:
            b.run()
            break
        except Limit as e:
            b.emit('attempt_end', status='limited' if a.packing else 'reduced', reason=str(e), peak_sampled_allocated_bytes=b.peak_sampled_allocated, completed_commits=b.commits,
                   elapsed_s=time.monotonic()-b.start, retry_rounds=None if a.packing else n//2)
            if a.packing:
                break
            n //= 2
            attempt += 1
        except Exception as e:
            b.emit('attempt_end', status='error', reason=str(e), elapsed_s=time.monotonic()-b.start)
            raise
        finally:
            t = time.monotonic()
            for path in [b.temp, b.repo]:
                if path.exists():
                    shutil.rmtree(path)
            b.emit('cleanup', cleanup_s=time.monotonic()-t, total_attempt_s=time.monotonic()-b.start)
    else:
        raise RuntimeError('No feasible scale remained.')


if __name__ == '__main__':
    main()
