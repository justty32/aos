"""`aos-team hr ls／set`：列成員的模型、等級與薪資，改名冊與家的 llm.model／正式與否並重啟。"""
import json
import os
from pathlib import Path

from aos_team_format import Layout, TeamError, load_roster, read_json, roster_lock, validate_roster, write_json

from aos_team_hr_book import hr_lock, load_salary, tier_of
from aos_team_hr_count import check_regular, member_model, register_team_locked


# ------------------------------------------------------------------ ls ----

def ls_rows(team_dir, hr):
    roster = load_roster(team_dir)
    sal = load_salary(hr)
    rows = []
    for name, m in roster['members'].items():
        model = member_model(roster, name)
        pos = sal['positions'].get(m['template']) or {}
        mp = pos.get('min_pass') or {}
        rows.append({'name': name, 'position': m['template'], 'model': model, 'tier': tier_of(sal, model) or '?',
                     'employment': m['employment'], 'min_pass': mp.get('model'), 'min_pass_tier': mp.get('tier'),
                     'evidence': mp.get('trial')})
    return rows


def cmd_ls(team_dir, hr, args):
    rows = ls_rows(team_dir, hr)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print('%-12s %-10s %-6s %-30s %-4s %s' % ('成員', '位子', '類型', '模型', '等級', '最低通過（證據）'))
    for r in rows:
        mp = '%s（%s，%s）' % (r['min_pass'], r['min_pass_tier'], r['evidence']) if r['min_pass'] else '—（沒試過）'
        print('%-12s %-10s %-6s %-30s %-4s %s' % (r['name'], r['position'], '正式' if r['employment'] == 'regular'
                                                   else '臨時', r['model'], r['tier'], mp))
    return 0


# ----------------------------------------------------------------- set ----

def set_member(team_dir, hr, name, model=None, employment=None, restart=True, env=None, out=print):
    """改名冊一個成員的 model／employment；model 改了也改它家的 info.json、登記著就重啟。"""
    env = os.environ if env is None else env
    lay = Layout(team_dir)
    with hr_lock(Path(hr)), roster_lock(lay):   # astra 09-25：數人頭到寫名冊一口氣（鎖順序一律 HR → 名冊）
        raw = read_json(lay.roster)
        if name not in raw.get('members', {}):
            raise TeamError('NotFound', '%s 不在名冊裡（有：%s）' % (name, '、'.join(raw.get('members', {}))))
        row = raw['members'][name]
        if model is not None:
            row['model'] = model
        if employment is not None:
            row['employment'] = employment
        after = validate_roster(raw, str(lay.roster))
        if employment == 'regular':
            check_regular(hr, team_dir, after)
        write_json(lay.roster, raw, indent=2)
        register_team_locked(hr, team_dir)
    out('team.json 的 %s 改好了%s%s' % (name, '：model=%s' % model if model else '',
                                        '：employment=%s' % employment if employment else ''))
    if model is None:
        return 0
    home = lay.member(name)
    info_p = home / 'info.json'
    if not info_p.exists():
        out('%s 還沒有家；aos-team init 生家時就會用新模型' % name)
        return 0
    import aos_agent
    import aos_agent_status
    from aos_agent_tools_edit import info_lock
    running = False
    if restart:
        running = not aos_agent_status.unregistered(aos_agent_status.kernel_status(str(home), env))
        if running and aos_agent.stop(str(home), env=env):      # astra 09-25：先停、再改、再開
            raise TeamError('StillRunning', '%s 停不下來；aos-agent status --target %s 看' % (name, home))
    with info_lock(home):                    # 跟 tools add／access set 共用同一把鎖
        info = read_json(info_p)
        info.setdefault('llm', {})['model'] = model
        write_json(info_p, info, indent=2)
    out('%s 的家 info.json 的 llm.model 改成 %s' % (name, model))
    if not running:
        out('%s 沒登記在 kernel（或 --no-restart），不用重啟' % name)
        return 0
    rc = aos_agent.start(str(home), env=env)
    out('%s 重啟%s' % (name, '好了' if rc == 0 else '失敗（aos-agent status --target %s 看）' % home))
    return 1 if rc else 0
