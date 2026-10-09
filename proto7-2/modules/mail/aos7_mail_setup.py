"""ROSTER 原子追加與團隊完整發布；共用郵局路由。"""
import os
from pathlib import Path
import re
import shutil
import tempfile
from aos7_mail import name, inbox, team_of, locked, test_point

def roster(root, me, who, up, territory, can, cannot, team=None):
    name(me)
    name(up)
    if team:
        name(team)
    path = Path(root) / me / 'wf/workflows/inbox/ROSTER.md'
    with locked(str(path)):
        text = path.read_text() if path.exists() else '# ROSTER\n\n## 現役成員\n'
        if f'### `{me}`' in text.splitlines():
            raise ValueError('同名 ROSTER 格已存在')
        fields = [('狀態', '現役'), ('我是誰', who), ('團隊', f'`teams/{team}`' if team else '無'),
                  ('上游', up), ('領地', territory), ('答得出什麼', can), ('答不出什麼', cannot),
                  ('怎麼找我', str(inbox(root, me))), ('訂閱主題', '無')]
        if any('\n' in v or '\r' in v for _, v in fields):
            raise ValueError('ROSTER 每欄必須是一行')
        active = re.search(r'^## 現役成員\s*$', text, re.M)
        following = re.search(r'^## ', text[active.end():], re.M) if active else None
        end = active.end() + following.start() if following else len(text)
        entry = f'\n### `{me}`\n' + ''.join(f'- **{k}**：{v}\n' for k, v in fields) + '\n'
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            f.write((text[:end] + entry + text[end:]).encode('utf-8'))
        try:
            test_point('mail.roster_before_replace')
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def team(root, group, leader, members):
    name(group)
    people = [name(p) for p in [leader, *members]]
    with locked(str(Path(root) / 'teams/.membership')):
        staging = Path(root) / '.staging'
        staging.mkdir(exist_ok=True)
        for old in staging.glob('mail-team-*'):
            shutil.rmtree(old)
        folder = Path(root) / 'teams' / group
        content = '\n'.join(people) + '\n'
        if folder.exists():
            if (folder / 'members').read_text() == content:
                return
            raise ValueError('團隊已存在且 members 不同')
        if len(set(people)) != len(people) or any(team_of(root, p) for p in people):
            raise ValueError('成員重複或已在別的團隊')
        prepared = Path(tempfile.mkdtemp(prefix='mail-team-', dir=staging))
        (prepared / 'inbox').mkdir()
        (prepared / 'members').write_text(content)
        test_point('mail.team_before_publish')
        os.rename(prepared, folder)
