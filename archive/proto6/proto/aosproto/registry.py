import os
import time
from pathlib import Path
from .common import Fault, fields, integer, loads, node_id, read_inst, uid, within
from .config import grants, registration


def authorize(peer_uid, method, target, registry):
    """Only trusted registration ancestry, never path prefixes or claimed uid."""
    if method in ('daemon.info', 'node.ls'):
        return True
    seen = set()
    while target is not None and target not in seen:
        seen.add(target)
        entry = registry.get(target)
        if entry is None:
            return False
        if entry['owner_uid'] == peer_uid:
            return True
        target = entry['parent_id']
    return False


def new_entry(params, common_uid, registry, top=False):
    try:
        registration(params, top)
        node = params['node_id']
        once = params.get('once', False)
        if not once and not Path(node).is_dir():
            raise ValueError('普通 node 必須為資料夾')
        raw, source, _ = read_inst(node)
        obj = loads(raw)
        if not isinstance(obj, dict):
            raise ValueError('inst 必須為物件')
        parent = None if top else registry.get(params['parent_id'])
        if not top and (parent is None or not parent['registered']):
            raise Fault('not_registered', '父 node 未登記')
        if parent and parent['once']:
            raise Fault('registration_conflict', 'once 不可有成員')
        allowed = grants(params['identity_grant'])
        if parent and not set(allowed) <= set(parent['_grant']):
            raise Fault('user_not_granted', '子額度超過父額度')
        if parent and 'provision' in params:
            given = params['provision']
            upper = parent.get('provision', {'actions': [], 'paths': []})
            if (not set(given['actions']) <= set(upper['actions']) or
                    not all(any(within(p, q) for q in upper['paths']) for p in given['paths'])):
                raise Fault('path_not_granted', '佈建授權超過父額度')
        inherited = common_uid if parent is None else parent['owner_uid']
        if 'user' in obj and obj['user'] is None:
            raise Fault('UserInvalid', 'user 不接受 null')
        try:
            owner = uid(obj.get('user'), inherited)
        except Fault:
            if not isinstance(obj.get('user'), str):
                raise
            # P-104（第十六批 G-11）：登記時帳號就要存在，once 也一樣。
            raise Fault('user_invalid', '帳號不存在: ' + obj['user'])
        if owner not in allowed:
            raise Fault('user_not_granted', 'inst user 不在額度內')
        entry = dict(params)
        entry.update(parent_id=None if top else params['parent_id'], owner_uid=owner, once=once,
                     registered=True, paused=False, running=False, pending=top, stopping=False,
                     last_tick=None, _grant=allowed, _source=str(source), _raw=raw,
                     _due=time.monotonic() + params.get('interval_ms', 0) / 1000,
                     _process=None, _frame=None, _leaf=None, _status=None, _report_bytes=b'')
        return entry
    except (OSError, ValueError, Fault) as exc:
        if isinstance(exc, Fault) and exc.code in ('not_registered', 'registration_conflict',
                                                  'user_not_granted', 'path_not_granted', 'user_invalid'):
            raise
        raise Fault('invalid_params', str(exc), 2, -32602)


def validate_params(method, params):
    try:
        if method == 'daemon.info':
            fields(params, ())
        elif method == 'node.ls':
            fields(params, ('limit', 'after_node_id'))
            if 'limit' in params and not integer(params['limit'], 1, 64):
                raise ValueError('limit 必須為 1..64')
            if 'after_node_id' in params and not node_id(params['after_node_id']):
                raise ValueError('after_node_id 格式錯')
        elif method == 'node.register':
            registration(params)
        else:
            fields(params, ('node_id',), ('node_id',))
            if not node_id(params['node_id']):
                raise ValueError('node_id 格式錯')
    except (ValueError, Fault) as exc:
        raise Fault('invalid_params', str(exc), 2, -32602)
