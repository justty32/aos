"""建立單一內建預設的 agent 家，最後才發佈身分檔。"""
import os
from pathlib import Path

import aos_agent_access
import aos_home
from aos_agent_home import AgentError


def init(agent_dir, force=False):
    base = Path(os.path.abspath(agent_dir))
    if os.path.lexists(base / 'info.json'):
        raise AgentError('AlreadyExists', '%s 已經是 agent 家（拒絕覆蓋）' % (base / 'info.json'))
    # fix-r5（aos-agent.md §1.1）：非空、又不是 agent 家的資料夾，要 --force 才生。
    if not force and base.is_dir():
        names = sorted(p.name for p in base.iterdir())
        if names:
            shown = '、'.join(names[:5]) + ('…等 %d 個' % len(names) if len(names) > 5 else '')
            raise AgentError('NotEmpty', '%s 不是空資料夾，也不是 agent 家（已有 %s）；確定要生在這裡就加 --force'
                             % (base, shown))
    for name in ('prompts', 'tools', 'input', 'log'):
        (base / name).mkdir(parents=True, exist_ok=True)
    aos_home.write_json(base / 'prompts/system.json',
                        {'content': '你是繁體中文助理，回答簡短。要知道現在時間就呼叫 date 工具。'})
    aos_home.write_json(base / 'tools/date.json', [{
        'type': 'function', 'function': {'name': 'date', 'description': '取得現在的本機日期與時間',
                                       'parameters': {'type': 'object', 'properties': {}}},
        '_meta': {'argv': ['date', '+%Y-%m-%d %H:%M:%S']}}])
    aos_home.write_json(base / 'state.json', {'input': 'input'})
    # 有工具的家一定要有 access.json（沒有＝工具不送，NoAccess）：date 也關牢，只看得到 workspace/
    (base / 'workspace').mkdir(exist_ok=True)
    aos_agent_access.write_access(base / aos_agent_access.DEFAULT_NAME, {
        '_metainfo': dict(aos_agent_access.METAINFO), 'mounts': {'ws': 'workspace'}, 'cwd': 'ws', 'net': False})
    aos_home.write_json(base / 'info.json', indent=2, obj={
        '_metainfo': {'_type': 'llm_agent', '_version': 1}, 'system': 'prompts/system.json',
        'history': 'prompts/history.json', 'tools': ['tools'],
        'llm': {'model': 'default', 'pool': 'llm', 'timeout_ms': 125000},
        'tool_pool': 'default', 'tick': {'pool': 'default', 'interval_ms': 1000}})
    print('initialized ' + str(base))
    print('access.json：工具關在牢裡，只看得到 /work/ws（＝workspace，可寫）、不能上網；改：aos-agent access ls／set')
    print('llm.model 是代號 "default"：llm.json（kernel 的 llm 池用 AOS_LLM_CONFIG 指的那份，'
          '見 proto5/tutorials/01-daemon-kernel.md）要有 default 這個代號')
    return 0


# ------------------------------------------------------------ 照模板生 ----
# spec/team/templates.md。aos-team init 對名冊每一列叫它；aos-agent init --template 的旗標由第 4 隊接。

MARKER = '.aos-template.json'
VARS = ('name', 'mail_to', 'members')


def _rel(path, base):
    return os.path.relpath(os.path.abspath(path), base)


def _mount_value(value, anchor, base, absolute):
    """名冊／模板的 mount 值（相對 anchor）→ access.json 的值（相對家，或絕對）。"""
    ro = isinstance(value, dict)
    raw = value['$val'] if ro else value
    full = os.path.abspath(os.path.join(anchor, os.path.expanduser(raw)))
    val = full if absolute else _rel(full, base)
    return {'$opt': 'ro', '$val': val} if ro else val


def _access(base, tpl, folder, member):
    import aos_agent_access
    mounts = {}
    if member is None:
        (base / 'workspace').mkdir(exist_ok=True)
        mounts['ws'] = 'workspace'
    else:
        team = member['team_dir']
        ws = _rel(member['project'], base)
        mounts['ws'] = {'$opt': 'ro', '$val': ws} if tpl.get('project', 'rw') == 'ro' else ws
        mounts['outbox'] = _rel(os.path.join(team, 'team', 'outbox', member['name']), base)
        mounts['board'] = {'$opt': 'ro', '$val': _rel(os.path.join(team, 'team', 'tasks'), base)}
        if tpl.get('notes'):
            _check_notes_dir(member)
            mounts['notes'] = _rel(_notes_dir(member), base)
            mounts['mem'] = dict(MEM_MOUNT)
    for where, extra in (('模板', tpl.get('mounts', {})), ('名冊', (member or {}).get('mounts', {}))):
        if 'mem' in extra:
            # 保留名的主檢查在 aos_team_format.RESERVED_MOUNTS；這裡再擋一次，免得蓋掉內建的唯讀 mem
            raise AgentError('FormatInvalid', '%s的 mounts 不能用 mem（保留名：init 內建掛自己的 prompts/，唯讀）' % where)
    for name, value in tpl.get('mounts', {}).items():
        mounts[name] = _mount_value(value, folder, base, True)
    for name, value in (member or {}).get('mounts', {}).items():
        mounts[name] = _mount_value(value, member['team_dir'], base, False)
    if member is not None:
        _guard_team(base, mounts, member)
    return {'_metainfo': dict(aos_agent_access.METAINFO), 'mounts': mounts, 'cwd': 'ws', 'net': False}


def _guard_team(base, mounts, member):
    """多掛的可寫資料夾不准碰團隊的控制資料：team.json、team/（別人的 outbox、任務表、問題）、members/（所有人的家）、
    proto5 自己（模板、工具包、程式）。自己的 outbox、notes、mem 是內建掛點（保留名，名冊與模板用不了），不在這裡查。只查可寫的；唯讀照 access.md 的規則。"""
    team = os.path.realpath(member['team_dir'])
    guarded = [os.path.join(team, 'team.json'), os.path.join(team, 'team'), os.path.join(team, 'members'),
               os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))]
    for name, value in mounts.items():
        if name in ('ws', 'outbox', 'board', 'notes', 'mem') or isinstance(value, dict):
            continue
        real = os.path.realpath(os.path.join(base, os.path.expanduser(value)))
        for g in guarded:
            g = os.path.realpath(g)
            if real == g or real.startswith(g.rstrip(os.sep) + os.sep) or g.startswith(real.rstrip(os.sep) + os.sep):
                raise AgentError('AccessUnsafe', '多掛的 %s（%s）可寫，但碰到團隊控制資料 %s；改成唯讀 '
                                 '{"$opt": "ro", "$val": …} 或換一個資料夾' % (name, real, g))


# 模板 notes: true 的成員多掛自己家的 prompts/（唯讀）＝牢裡 /work/mem：recall 找 archive/、context 量 history.json。
# 掛資料夾不掛檔：tick 用暫存檔＋rename 換 history.json，掛檔會一直看到舊的那份。唯讀可以跟信任資料重疊（contract §3）。
MEM_MOUNT = {'$opt': 'ro', '$val': 'prompts'}


def _notes_dir(member):
    """成員自己的筆記資料夾 team/notes/<名>/（spec/team/layout.md）；牢裡是 /work/notes，note 工具寫 notes.json。"""
    return os.path.join(member['team_dir'], 'team', 'notes', member['name'])


def _check_notes_dir(member):
    """內建 notes 掛點的實際落點要就是 team/notes/<名>/：途中（team、notes、<名>）不准是符號連結，
    解開後也要在原位（astra T5 M1：事先放一個 team/notes/worker-1 → ../tasks，會把任務表掛成可寫）。"""
    team = os.path.realpath(member['team_dir'])
    want = os.path.join(team, 'team', 'notes', member['name'])
    cur = team
    for part in ('team', 'notes', member['name']):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise AgentError('AccessUnsafe', '筆記資料夾途中的 %s 是符號連結；內建 notes 掛點只准是真的資料夾 %s'
                             % (cur, want))
    if os.path.exists(want) and (not os.path.isdir(want) or os.path.realpath(want) != want):
        raise AgentError('AccessUnsafe', '筆記資料夾 %s 不是普通資料夾' % want)


def _ensure_notes(base, tpl, member, lines):
    """模板 notes: true：建 team/notes/<名>/；已生的舊家 access.json 沒有 notes／mem 掛載就補那一格（只補缺的，
    其他掛載不動；已被人改指別處也不動）。不補的話重跑 init 裝上的 note／recall／context 在牢裡找不到 /work/notes、/work/mem。"""
    if member is None or not tpl.get('notes'):
        return
    _check_notes_dir(member)
    os.makedirs(_notes_dir(member), exist_ok=True)
    _check_notes_dir(member)
    path = base / 'access.json'
    if not path.is_file():
        return                                            # 新生的家：_access 已經寫了
    import aos_agent_access
    try:
        doc = aos_home.read_json(path)
    except aos_home.HomeError:
        return                                            # 壞掉的交給最後的 aos_agent_access.load 報
    mounts = doc.get('mounts') if isinstance(doc, dict) else None
    if not isinstance(mounts, dict):
        return
    added = []
    if 'notes' not in mounts:
        mounts['notes'] = _rel(_notes_dir(member), base)
        added.append('access.json 補掛 notes（→ team/notes/%s/）' % member['name'])
    if 'mem' not in mounts:
        mounts['mem'] = dict(MEM_MOUNT)
        added.append('access.json 補掛 mem（→ prompts/，唯讀）')
    if added:
        aos_agent_access.write_access(path, doc)
        lines.extend(added)


def _system_text(folder, tpl, name, member):
    text = (folder / tpl['system']).read_text(encoding='utf-8')
    values = {'name': name,
              'mail_to': '、'.join((member or {}).get('mail_to', [])) or '（無）',
              'members': '、'.join((member or {}).get('members', [])) or '（無）'}
    for k in VARS:
        text = text.replace('{%s}' % k, values[k])
    return text.strip()


def team_config(member):
    """team: true 的工具包裝完寫進 config.json 的鍵（牢裡看到的路徑）。"""
    return {'member': member['name'], 'mail_to': list(member['mail_to']), 'members': list(member['members']),
            'outbox': '/work/outbox', 'board': '/work/board', 'tz': member.get('tz')}


def _write_team_config(base, pack, member):
    import json
    cfg_path = base / 'tools' / pack / 'config.json'
    cfg = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        except ValueError:
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
    cfg.update(team_config(member))
    aos_home.write_json(cfg_path, cfg, indent=2)


def _installed(base, pack):
    """裝好＝工具檔在，而且 info.tools 有一條指到它（只有工具檔、沒有那一條＝崩在 tools add 中間，要重裝）。"""
    if not (base / 'tools' / (pack + '.json')).exists():
        return False
    try:
        tools = aos_home.read_json(base / 'info.json').get('tools', [])
    except (aos_home.HomeError, AttributeError):
        return False
    want = 'tools/%s.json' % pack
    return any((e if isinstance(e, str) else e.get('$val') if isinstance(e, dict) else None) == want for e in tools)


def _install_tools(base, entries, member, lines):
    """依序裝工具包；裝過的（tools/<包>.json 在）不重裝；optional 的包不在就跳過。回有沒有全裝好。"""
    import contextlib
    import io
    import aos_agent_tools
    for entry in entries:
        pack = entry['pack']
        if not (aos_agent_tools.PACKAGES / pack / (pack + '.json')).is_file():
            if entry.get('optional'):
                lines.append('跳過工具包 %s（還沒有這個包，之後重跑 init 會補）' % pack)
                continue
            raise AgentError('NotFound', '模板要的工具包 %s 不在 %s' % (pack, aos_agent_tools.PACKAGES))
        if not _installed(base, pack):
            with contextlib.redirect_stdout(io.StringIO()):
                aos_agent_tools.add(str(base), pack, only=entry.get('only'))
            lines.append('裝了 %s%s' % (pack, '（%s）' % '、'.join(entry['only']) if entry.get('only') else ''))
        if entry.get('team'):
            if member is None:
                raise AgentError('Usage', '工具包 %s 要團隊設定，這個模板只能用 aos-team init 生' % pack)
            _write_team_config(base, pack, member)


def init_from_template(agent_dir, template, *, name=None, member=None, force=False):
    """照模板生一個 agent 家；回要印的幾行。

    member（團隊成員才給）：{"name", "team_dir", "project"（絕對路徑）, "mail_to", "members", "tz",
    "model", "mounts"（相對團隊資料夾）, "tools"（多裝的包）}。
    家已在：有 .aos-template.json 且 complete=false＝上次生到一半，補完；complete=true 且是團隊成員＝只更新
    工具包的團隊設定與補裝新加的包（不動人格、記憶、access.json；唯一例外：模板 notes: true 而 access.json
    還沒有 notes／mem 掛載＝補那一格）；其他＝AlreadyExists。
    """
    from aos_team_format import TeamError, load_template
    try:
        folder, tpl = load_template(template)
    except TeamError as e:
        raise AgentError(e.code, e.msg)
    base = Path(os.path.abspath(agent_dir))
    name = name or (member or {}).get('name') or base.name
    if tpl.get('team') and member is None:
        raise AgentError('Usage', '模板 %s 是團隊用的（要名冊），請用 aos-team init' % template)
    entries = list(tpl.get('tools', [])) + list((member or {}).get('tools', []))
    marker = base / MARKER
    lines = []
    try:
        mark = aos_home.read_json(marker) if marker.exists() else None
    except aos_home.HomeError:
        mark = None
    if mark is not None and mark.get('template') != template:
        raise AgentError('AlreadyExists', '%s 是照模板 %s 生的，不是 %s；要換模板先 aos-team rm 再 init'
                         % (base, mark.get('template'), template))
    if os.path.lexists(base / 'info.json'):
        if mark is None:
            raise AgentError('AlreadyExists', '%s 已經是 agent 家（拒絕覆蓋）' % (base / 'info.json'))
        if mark.get('complete') and member is None:
            raise AgentError('AlreadyExists', '%s 已經照模板 %s 生好了' % (base, mark.get('template')))
        lines.append('已在，%s' % ('補完上次沒生完的' if not mark.get('complete') else '更新工具設定'))
    else:
        # 有自己的 marker（complete=false）＝上次崩在寫 info.json 之前，照新生的做（檔都會整份重寫）
        if not force and mark is None and base.is_dir() and any(base.iterdir()):
            raise AgentError('NotEmpty', '%s 不是空資料夾，也不是 agent 家；確定要生在這裡就加 --force' % base)
        for sub in ('prompts', 'tools', 'input', 'log'):
            (base / sub).mkdir(parents=True, exist_ok=True)
        aos_home.write_json(marker, {'template': template, 'member': name, 'complete': False})
        aos_home.write_json(base / 'prompts/system.json', {'content': _system_text(folder, tpl, name, member)})
        aos_home.write_json(base / 'state.json', {'input': 'input/'})
        from aos_agent_access import write_access
        write_access(base / 'access.json', _access(base, tpl, folder, member))
        llm = dict({'model': 'default', 'timeout_ms': 125000}, **tpl.get('llm', {}))
        if member is not None and member.get('model'):
            llm['model'] = member['model']
        llm['pool'] = 'llm'
        aos_home.write_json(base / 'info.json', indent=2, obj={
            '_metainfo': {'_type': 'llm_agent', '_version': 1}, 'system': 'prompts/system.json',
            'history': 'prompts/history.json', 'tools': [], 'llm': llm, 'tool_pool': 'default',
            'tick': {'pool': 'default', 'interval_ms': tpl.get('tick', {}).get('interval_ms', 1000)}})
        lines.append('生了 %s（模板 %s，模型代號 %s）' % (base, template, llm['model']))
    _ensure_notes(base, tpl, member, lines)
    _install_tools(base, entries, member, lines)
    import aos_agent_access
    aos_agent_access.load(str(base))                      # access.json 要解得開、不蓋到信任資料
    aos_home.write_json(marker, {'template': template, 'member': name, 'complete': True})
    return lines
