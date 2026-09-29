"""Pure inst validation, shared by runner and tick; no directive expansion."""
import os
from .common import Fault, uid


def unsupported(value, options=False):
    if isinstance(value, dict):
        if '$opt' in value:
            if not options:
                raise Fault('UnknownOption', '此位置不接受選項')
            if '$val' in value:
                unsupported(value['$val'])
            return
        if any(key.startswith('$') for key in value):
            raise Fault('DirectiveUnsupported', '此輪未實作取值指示詞')
        for child in value.values():
            unsupported(child)
    elif isinstance(value, list):
        for child in value:
            unsupported(child)


def option(value, field):
    allowed = {'stdin': {'inherit'}, 'stdout': {'inherit', 'append', 'mkdir'},
               'stderr': {'inherit', 'append', 'mkdir', 'merge'}, 'exit': {'append', 'mkdir'},
               'cwd': {'mkdir'}, 'envs': {'clear'}}[field]
    unsupported(value, options=True)
    if not isinstance(value, dict) or '$opt' not in value:
        return set(), value
    names = value['$opt']
    if isinstance(names, str):
        names = [names]
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise Fault('DirectiveValueTypeMismatch', '$opt 必須為名字或非空名字陣列')
    if len(set(names)) != len(names) or set(names) - allowed:
        raise Fault('UnknownOption', '未知、重複或放錯位置的選項')
    names = set(names)
    if len(names) > 1 and names != {'append', 'mkdir'}:
        raise Fault('OptionConflict', '選項互斥')
    if names & {'inherit', 'merge'}:
        if '$val' in value:
            raise Fault('OptionConflict', 'inherit/merge 不可帶值')
        return names, None
    if names == {'clear'}:
        return names, value.get('$val', {})
    if '$val' not in value or value['$val'] == '':
        raise Fault('OptionConflict', '此選項需要非空路徑')
    return names, value['$val']


def validate(inst, inherited_uid=None):
    if not isinstance(inst, dict):
        raise Fault('NotAnObject', 'inst 必須為物件')
    # User is literal and checked before directives or any filesystem changes.
    if 'user' in inst and inst['user'] is None:
        raise Fault('UserInvalid', 'user 不接受 null')
    owner = uid(inst.get('user'), inherited_uid)
    if '$opt' in inst:
        raise Fault('UnknownOption', '頂層不可用選項')
    if any(k.startswith('$') for k in inst):
        raise Fault('DirectiveUnsupported', '此輪未實作取值指示詞')
    if '_metainfo' in inst:
        meta = inst['_metainfo']
        if not isinstance(meta, dict) or not {'_type', '_version'} <= set(meta):
            raise Fault('MetainfoInvalid', '_metainfo 缺少種類或版本')
        if meta['_type'] != 'posix':
            raise Fault('UnsupportedInstType', '只支援 posix')
        if type(meta['_version']) is not int or meta['_version'] != 1:
            raise Fault('UnsupportedInstVersion', '只支援版本 1')
    argv = inst.get('argv')
    unsupported(argv)
    if argv is None or argv == [] or isinstance(argv, list) and argv[0] == '':
        raise Fault('EmptyArgv', 'argv 不可為空')
    if not isinstance(argv, list) or not all(isinstance(a, str) and '\0' not in a for a in argv):
        raise Fault('FieldTypeMismatch', 'argv 必須為字串陣列')
    result = {'user': owner, 'argv': argv}
    for field in ('cwd', 'stdin', 'stdout', 'stderr', 'exit'):
        opts, value = option(inst.get(field, ''), field)
        if not opts & {'inherit', 'merge'} and (not isinstance(value, str) or '\0' in value):
            raise Fault('FieldTypeMismatch', field + ' 必須為路徑字串')
        result[field] = (opts, value)
    opts, envs = option(inst.get('envs', {}), 'envs')
    if not isinstance(envs, dict):
        raise Fault('FieldTypeMismatch', 'envs 必須為物件')
    for key, value in envs.items():
        if not key or '=' in key or '\0' in key:
            raise Fault('EnvKeyInvalid', 'envs 名稱不可為空或含 = / NUL')
        if not isinstance(value, str) or '\0' in value:
            raise Fault('FieldTypeMismatch', 'envs 值必須為字串')
    result['envs'] = (opts, envs)
    return result
