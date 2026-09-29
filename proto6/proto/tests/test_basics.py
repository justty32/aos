import copy
import json
import os
from pathlib import Path
from support import Case, PROTO, write_json
from aosproto.common import Fault, loads
from aosproto.config import load_config, versions_ok
from aosproto.cgroup import FakeCgroup
from aosproto.registry import authorize


class Versions(Case):
    def test_kernel_513_fails(self):
        self.assertTrue(versions_ok('5.13.99-x', '3.9.1', 'git version 2.35.0'))

    def test_kernel_514_passes(self):
        self.assertEqual(versions_ok('5.14.0-arch', (3, 9), 'git version 2.35.0'), [])

    def test_git_234_fails(self):
        self.assertTrue(versions_ok('6.1', (3, 9), 'git version 2.34'))

    def test_python_38_fails(self):
        self.assertTrue(versions_ok('6.1', (3, 8), '2.35'))


class Configuration(Case):
    def config(self):
        return {'version': 1, 'roots': [], 'socket_path': str(self.path / 'sock'), 'state_dir': str(self.path / 'state')}

    def test_spec_valid_examples(self):
        for name in ('config.minimal.valid.json', 'config.create-cgroup.valid.json'):
            obj = json.loads((PROTO.parent / 'spec/protocol/examples/daemon' / name).read_text())
            obj.update(socket_path=str(self.path / 'sock'), state_dir=str(self.path / 'state'))
            obj['roots'][0].update(node_id=str(self.path / 'R'), identity_grant=[os.getuid()])
            if 'cgroup_root' in obj:
                obj['cgroup_root'] = str(self.path / 'cg')
            file = self.path / 'config.json'
            write_json(file, obj)
            self.assertEqual(load_config(file), obj)

    def test_invalid_config_cli(self):
        cases = []
        for name in ('config.version.invalid.json', 'config.create-cgroup-no-root.invalid.json'):
            cases.append((PROTO.parent / 'spec/protocol/examples/daemon' / name).read_text())
        obj = self.config()
        cases += [json.dumps(dict(obj, unknown=1)), json.dumps(obj)[:-1] + ',"version":1}',
                  json.dumps(dict(obj, version=True)), json.dumps(dict(obj, shutdown_grace_ms=True)),
                  json.dumps(dict(obj, create_cgroup=True)), json.dumps(dict(obj, common_user=False))]
        for raw in cases:
            with self.subTest(raw=raw):
                file = self.path / 'bad.json'
                file.write_text(raw)
                self.cli('daemon', '--config', file, code=2)

    def test_cli_create_requires_root(self):
        file = self.path / 'config.json'
        write_json(file, self.config())
        self.cli('daemon', 'start', '--config', file, '--create-cgroup', code=2)

    def test_strict_json(self):
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":1e999}', '\ufeff{}', '{}{}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                loads(raw)


class Cgroups(Case):
    def test_missing_without_create(self):
        cg = FakeCgroup(self.path)
        with self.assertRaises(Fault) as caught:
            cg.prepare(self.path / 'absent')
        self.assertEqual(caught.exception.exit_code, 125)

    def test_missing_create_moves_inside(self):
        cg = FakeCgroup(self.path)
        root = cg.prepare(self.path / 'new', True)
        self.assertTrue((root / 'cgroup.threads').exists())
        self.assertEqual(cg.own, root)

    def test_existing_outside_uses_components(self):
        cg = FakeCgroup(self.path, self.path / 'foobar')
        cg.create(self.path / 'foo')
        with self.assertRaises(Fault):
            cg.prepare(self.path / 'foo')


class Authorization(Case):
    def test_owner_and_ancestor(self):
        registry = {'/R': {'owner_uid': 10, 'parent_id': None},
                    '/C': {'owner_uid': 20, 'parent_id': '/R'}}
        self.assertTrue(authorize(20, 'node.wake', '/C', registry))
        self.assertTrue(authorize(10, 'node.show', '/C', registry))
        self.assertFalse(authorize(30, 'node.show', '/C', registry))
        self.assertFalse(authorize(20, 'node.pause', '/R', registry))
        for method in ('daemon.info', 'node.ls'):
            self.assertTrue(authorize(30, method, None, registry))


class RunnerEvidence(Case):
    def test_snapshot_is_readonly_and_sealed(self):
        import fcntl
        from aosproto.runner import snapshot_fd
        fd = snapshot_fd(b'{"argv":["true"]}')
        try:
            self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
            with self.assertRaises(OSError):
                os.write(fd, b'x')
            self.assertTrue(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & fcntl.F_SEAL_WRITE)
        finally:
            os.close(fd)

    def test_report_requires_trusted_shape_and_wait(self):
        from aosproto.launch import trusted_report
        from aosproto.common import encode
        self.assertIsNone(trusted_report(encode({'started': True, 'exit_code': 0}), 9))
        self.assertIsNone(trusted_report(encode({'started': False, 'exit_code': 0}), 0))
        self.assertIsNone(trusted_report(encode({'started': True, 'exit_code': True}), 0))
        self.assertIsNone(trusted_report(encode({'started': True, 'exit_code': 143, 'signal': 9}), 143 << 8))
        self.assertIsNone(trusted_report(b'{}\n{}\n', 0))
        self.assertEqual(trusted_report(encode({'started': True, 'exit_code': 125}), 125 << 8)['exit_code'], 125)
