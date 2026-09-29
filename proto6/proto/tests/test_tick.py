import fcntl
import os
from support import Case, task, table, write_json


class Tick(Case):
    def test_group_failure_rolls_back_and_needs_skips(self):
        tasks = [task('a', 'echo a > a', group='g'), task('b', 'echo b > b; exit 1', group='g'),
                 task('c', 'echo c > c', needs=['a']), task('d', 'echo d > d')]
        node = self.new_node(tasks=tasks)
        self.cli('tick', node, code=1)
        self.assertFalse((node / 'a').exists())
        self.assertFalse((node / 'b').exists())
        self.assertFalse((node / 'c').exists())
        self.assertEqual(self.git(node, 'show', 'HEAD:d'), 'd')
        self.assertEqual(self.git(node, 'rev-list', '--count', 'HEAD'), '2')

    def test_bad_table_rejected_before_any_task(self):
        for tasks in ([task('a', 'touch ran'), task('a')],
                      [task('a', 'touch ran'), task('b', needs=['absent'])],
                      [task('a', group='g'), task('b'), task('c', group='g')],
                      [task('a'), dict(task('b'), kind='system')],
                      [dict(task('a'), user=os.getuid())]):
            # new must itself validate; construct and commit invalid candidate intentionally.
            node = self.new_node(name='R' + str(len(list(self.path.glob('R*')))))
            write_json(node / '.aos/tasks.json', table(tasks))
            self.git(node, 'add', '-A')
            self.git(node, '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'invalid fixture')
            self.cli('tick', node, code=2)
            self.assertFalse((node / 'ran').exists())

    def test_lock_busy(self):
        node = self.new_node()
        lock = node / '.git/aos/tick.lock'
        lock.parent.mkdir()
        with lock.open('w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.cli('tick', node, code=75)

    def test_blocked_preserves_dirty(self):
        node = self.new_node()
        (node / '.git/aos').mkdir()
        (node / '.git/aos/tick-blocked').write_text('blocked')
        (node / 'dirty').write_text('keep')
        self.cli('tick', node, code=125)
        self.assertTrue((node / 'dirty').exists())

    def test_empty_no_commit_and_restores_head(self):
        node = self.new_node()
        (node / 'dirty').write_text('discard')
        (node / 'work').mkdir()
        (node / 'work/ignored').write_text('keep')
        self.cli('tick', node)
        self.assertFalse((node / 'dirty').exists())
        self.assertTrue((node / 'work/ignored').exists())
        self.assertEqual(self.git(node, 'rev-list', '--count', 'HEAD'), '1')

    def test_success_same_group_needs_and_lock_fd(self):
        script = 'test -n "$AOS_NODE_DIR"; test -e /proc/self/fd/$AOS_TICK_LOCK_FD; echo yes > result'
        node = self.new_node(tasks=[task('a', script, group='g'), task('b', 'test -f result', group='g', needs=['a'])])
        self.cli('tick', node)
        self.assertEqual(self.git(node, 'log', '-1', '--format=%s'), 'aos-tick group a..b')

    def test_head_change_blocks(self):
        node = self.new_node(tasks=[task('a', 'git checkout -qb different')])
        self.cli('tick', node, code=3)
        self.assertTrue((node / '.git/aos/tick-blocked').exists())

    def test_commit_failure_blocks(self):
        node = self.new_node(tasks=[task('a', 'echo a > a; touch .git/index.lock')])
        self.cli('tick', node, code=3)
        self.assertTrue((node / '.git/aos/tick-blocked').exists())

    def test_ignore_change_does_not_escape_rollback(self):
        node = self.new_node(tasks=[task('a', 'echo escaped >> .gitignore; echo hi > escaped; exit 1')])
        self.cli('tick', node, code=1)
        self.assertFalse((node / 'escaped').exists())

    def test_new_ignore_applies_next_group(self):
        node = self.new_node(tasks=[task('a', 'echo result >> .gitignore; echo tracked > result')])
        self.cli('tick', node)
        self.assertEqual(self.git(node, 'show', 'HEAD:result'), 'tracked')

    def test_removed_ignore_does_not_adopt_existing_work_this_group(self):
        node = self.new_node(tasks=[task('a', 'sed -i "\\|^/work/|d" .gitignore; echo new > managed')])
        (node / 'work').mkdir()
        (node / 'work/keep').write_text('ignored')
        self.cli('tick', node)
        self.assertNotIn('work/keep', self.git(node, 'ls-files'))
        self.assertEqual((node / 'work/keep').read_text(), 'ignored')

    def test_new_nested_ignore_cannot_hide_failed_group_output(self):
        node = self.new_node(tasks=[task('a', 'mkdir -p sub; echo hidden > sub/.gitignore; echo hi > sub/hidden; exit 1')])
        self.cli('tick', node, code=1)
        self.assertFalse((node / 'sub/hidden').exists())

    def test_git_magic_filename_is_literal(self):
        node = self.new_node(tasks=[task('a', 'echo hi > ":(exclude)literal"')])
        self.cli('tick', node)
        self.assertIn(':(exclude)literal', self.git(node, 'ls-files'))
