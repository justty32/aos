import os
import re
import subprocess
import sys
from .common import Fault, fields, integer, node_id, read_json, uid, within


def versions_ok(kernel, python, git):
    """Pure, injectable minimum-version comparison (release suffixes allowed)."""
    def pair(value):
        if isinstance(value, (list, tuple)):
            return tuple(value[:2])
        match = re.search(r'(\d+)\.(\d+)', value)
        return tuple(map(int, match.groups())) if match else (0, 0)
    failures = []
    for name, value, minimum in [('Linux kernel', kernel, (5, 14)),
                                  ('Python', python, (3, 9)), ('git', git, (2, 35))]:
        if pair(value) < minimum:
            failures.append('%s 需要 >= %d.%d' % (name, *minimum))
    return failures


def self_check(fake=False):
    try:
        git = subprocess.check_output(['git', '--version'], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Fault('dependency_failed', str(exc))
    failures = versions_ok(os.uname().release, sys.version_info, git)
    if os.uname().sysname != 'Linux':
        failures.append('需要 Linux')
    if not fake and not any(line.split()[2] == 'cgroup2' for line in open('/proc/self/mounts')):
        failures.append('需要 cgroup v2 掛載點')
    if failures:
        raise Fault('dependency_failed', '; '.join(failures))


def grants(values):
    if not isinstance(values, list) or not values:
        raise ValueError('identity_grant 必須為非空陣列')
    resolved = []
    for value in values:
        if not (integer(value) or isinstance(value, str) and value):
            raise ValueError('身分額度格式錯')
        item = uid(value)
        if item == 0 or item in resolved:
            raise ValueError('額度不能有 root 或重複 UID 別名')
        resolved.append(item)
    return resolved


def provision(value):
    fields(value, ('actions', 'paths'), ('actions', 'paths'))
    actions, paths = value['actions'], value['paths']
    if (not isinstance(actions, list) or not all(isinstance(a, str) for a in actions)
            or len(set(actions)) != len(actions)
            or set(actions) - {'account_create', 'chown', 'cgroup_create', 'cgroup_limits', 'quota'}):
        raise ValueError('provision.actions 不合法')
    if not isinstance(paths, list) or not all(node_id(p) for p in paths) or len(set(paths)) != len(paths):
        raise ValueError('provision.paths 不合法')


def registration(value, top=False):
    allowed = {'node_id', 'identity_grant', 'interval_ms', 'provision'}
    required = {'node_id', 'identity_grant'}
    if not top:
        allowed |= {'parent_id', 'once'}
        required.add('parent_id')
    fields(value, allowed, required)
    if not node_id(value['node_id']) or (not top and not node_id(value['parent_id'])):
        raise ValueError('node_id / parent_id 必須是正規化絕對路徑')
    grants(value['identity_grant'])
    if 'interval_ms' in value and not integer(value['interval_ms'], 1):
        raise ValueError('interval_ms 必須是正整數')
    if 'once' in value and type(value['once']) is not bool:
        raise ValueError('once 必須是布林')
    if value.get('once') and 'interval_ms' in value:
        raise ValueError('once 不可有 interval_ms')
    if 'provision' in value:
        provision(value['provision'])


def load_config(path, create=False):
    try:
        obj = read_json(path)
        fields(obj, ('version', 'common_user', 'socket_path', 'state_dir', 'roots',
                     'pause_save_interval_ms', 'shutdown_grace_ms', 'cgroup_root', 'create_cgroup', 'disable'),
               ('version', 'socket_path', 'state_dir', 'roots'))
        if type(obj['version']) is not int or obj['version'] != 1:
            raise ValueError('version 只支援整數 1')
        for name in ('socket_path', 'state_dir', 'cgroup_root'):
            if name in obj and not node_id(obj[name]):
                raise ValueError(name + ' 必須是正規化絕對路徑')
        if 'create_cgroup' in obj and type(obj['create_cgroup']) is not bool:
            raise ValueError('create_cgroup 必須是布林')
        if create:
            obj['create_cgroup'] = True
        if obj.get('create_cgroup') and 'cgroup_root' not in obj:
            raise ValueError('create_cgroup 需要 cgroup_root')
        for name, minimum in [('pause_save_interval_ms', 1), ('shutdown_grace_ms', 0)]:
            if name in obj and not integer(obj[name], minimum):
                raise ValueError(name + ' 數值不合法')
        disabled = obj.get('disable', [])
        if not isinstance(disabled, list) or disabled not in ([], ['quota']):
            raise ValueError('disable 只接受不重複的 quota')
        if 'common_user' in obj:
            if obj['common_user'] == '' or obj['common_user'] is None:
                raise ValueError('common_user 不可為空')
            if uid(obj['common_user']) != os.getuid():
                raise ValueError('無 helper 時 common_user 必須是目前 UID')
        if not isinstance(obj['roots'], list):
            raise ValueError('roots 必須是陣列')
        seen = set()
        for root in obj['roots']:
            registration(root, top=True)
            if root['node_id'] in seen:
                raise ValueError('roots 重複 node_id')
            seen.add(root['node_id'])
        return obj
    except (OSError, ValueError, Fault) as exc:
        raise Fault('invalid_config', str(exc), 2)
