"""固定答案＋隔離變體；不跑 make_fixture、不 import 候選。"""
NAME = 'mailtodo'

EMPTY = {'v': 1, 'open': [], 'boxes': {}, 'bad': []}
CASES = [(['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}), (['--now', '2026-10-09T12:00:00Z'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 90}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 90}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 90}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 90}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]})]
VARIANTS = [
    ({'bob/inbox/99990101T0000-extra.md': '---\nfrom: alice\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: \nfrom: alice\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: \nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: \nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: destination\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: \nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: REQUEST\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: REQUEST\nat: \nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nstatus: REQUEST\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000-extra.md': '# before\n---\nid: extra\n---\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/99990101T0000_extra.md': '---\nid: discarded\nid: extra\nfrom: alice\nto: wrong\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nignored line\nre: \n---\n# extra\n', 'bob/inbox/done/99990101T0001_reply.md': '---\nid: reply\nfrom: alice\nto: destination\nstatus: PROGRESS\nat: 2026-10-09T18:29:30\nre: extra\n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}, {'id': 'extra', 'from': 'alice', 'to': 'destination', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 3}, 'done': 3}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
    ({'bob/inbox/bad-name.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n', 'bob/inbox/20261309T0000-extra.md': '---\nid: invalid-date\nfrom: alice\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n', 'bob/inbox/99990101T0000-extra.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: REQUEST\nat: invalid\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 0}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 0}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 2}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/20261309T0000-extra.md', 'why': 'bad_name'}, {'file': 'bob/inbox/99990101T0000-extra.md', 'why': 'no_field'}, {'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}, {'file': 'bob/inbox/bad-name.md', 'why': 'bad_name'}]}),
    ({'bob/inbox/99990101T0000_extra.md': '---\nid: extra\nfrom: alice\nto: destination\nstatus: REQUEST\nat: 2026-10-09T18:29:30\nre: \n---\n# extra\n'}, ['--now', '2026-10-09T12:00:00Z'], {'v': 1, 'open': [{'id': 'bob-20261009T182909-0e11821ea302', 'from': 'bob', 'to': 'alice', 'where': 'inbox', 'age_min': 90}, {'id': 'carol-20261009T182909-cbcbce88ed99', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 90}, {'id': 'carol-20261009T182909-f2e380fe4d5a', 'from': 'carol', 'to': 'bob', 'where': 'inbox', 'age_min': 90}, {'id': 'bob-20261009T182909-b31511ae1b6a', 'from': 'bob', 'to': 'carol', 'where': 'inbox', 'age_min': 90}, {'id': 'extra', 'from': 'alice', 'to': 'destination', 'where': 'inbox', 'age_min': -390}], 'boxes': {'alice': {'inbox': {'DONE': 2, 'REQUEST': 1}, 'done': 0}, 'bob': {'inbox': {'REQUEST': 3}, 'done': 2}, 'carol': {'inbox': {'PROGRESS': 2, 'REQUEST': 1}, 'done': 0}}, 'bad': [{'file': 'bob/inbox/99990101T0000-no-frontmatter.md', 'why': 'no_frontmatter'}, {'file': 'bob/inbox/99990101T0001-dup.md', 'why': 'dup_id'}]}),
]

def empty_answer():
    return EMPTY

def cases():
    return CASES

def variants():
    return VARIANTS

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


def snapshot(root):
    """lstat only; never descend into links; cache directories are permitted."""
    result = {}
    def visit(path):
        st = os.lstat(path)
        kind = stat.S_IFMT(st.st_mode)
        content = path.read_bytes() if stat.S_ISREG(st.st_mode) else os.readlink(path) if stat.S_ISLNK(st.st_mode) else None
        result[path.relative_to(root).as_posix()] = (kind, st.st_size, stat.S_IMODE(st.st_mode), st.st_mtime_ns, content, stat.S_ISDIR(st.st_mode) and os.path.lexists(path / '__pycache__'))
        if stat.S_ISDIR(st.st_mode):
            for name in sorted(os.listdir(path)):
                if name != '__pycache__':
                    visit(path / name)
    visit(root)
    return result


def same_snapshot(before, after):
    if before.keys() != after.keys():
        return False
    for key, old in before.items():
        new = after[key]
        if old == new:
            continue
        # An excluded cache appearing/disappearing changes its parent's size/mtime.
        # Still compare directory type/mode and every visible child.
        if old[0] == new[0] == stat.S_IFDIR and old[5] != new[5] and old[2] == new[2]:
            continue
        return False
    return True


def exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def readonly(node):
    modes = []
    for path in [node, *node.rglob('*')]:
        st = os.lstat(path)
        if not stat.S_ISLNK(st.st_mode):
            modes.append((path, stat.S_IMODE(st.st_mode)))
            path.chmod(stat.S_IMODE(st.st_mode) & ~0o222)
    return modes


def check_answer(top, fixture):
    issues = []
    entry = Path(top).resolve() / ('packs/' + NAME + '/bin/aos7-' + NAME)
    def run(node, args, expected=None, code=0, label='case'):
        # Parent snapshot also covers nonexistent/file inputs and sibling side effects.
        before = snapshot(node.parent)
        try:
            p = subprocess.run([sys.executable, '-B', str(entry), str(node), *args], capture_output=True, timeout=15)
            if p.returncode != code:
                issues.append(label + ': 退出碼不合：' + str(p.returncode))
            if code == 2:
                if p.stdout:
                    issues.append(label + ': 錯誤路徑 stdout 應空')
            elif len(p.stdout.splitlines()) != 1 or not exact(json.loads(p.stdout), expected):
                issues.append(label + ': 答案、型別或一行 stdout 不合：' + p.stdout.decode('utf-8', 'replace')[:300])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            issues.append(label + ': ' + str(exc))
        finally:
            try:
                unchanged = same_snapshot(before, snapshot(node.parent))
            except OSError:
                unchanged = False
            if not unchanged:
                issues.append(label + ': 輸入／父目錄的型別、大小、權限、mtime_ns 或內容被修改')
    original = Path(fixture).resolve()
    for args, expected in cases():
        run(original, args, expected)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for i, (changes, args, expected) in enumerate(variants()):
            node = root / str(i)
            shutil.copytree(original, node, symlinks=True)
            for rel, value in changes.items():
                path = node / rel
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(value if isinstance(value, bytes) else value.encode())
            run(node, args, expected, label='variant ' + str(i))
        ro = root / 'readonly'
        shutil.copytree(original, ro, symlinks=True)
        modes = readonly(ro)
        try:
            for args, expected in cases():
                run(ro, args, expected, label='readonly')
        finally:
            for path, mode in modes:
                path.chmod(mode)
        args = cases()[0][0]
        file = root / 'file'
        file.write_text('not a directory')
        for node in (root / 'absent', file):
            run(node, args, code=2)
        empty = root / 'empty'
        empty.mkdir()
        # A dangling link must stay a link and must not be followed.
        (empty / 'ignored-link').symlink_to(root / 'absent-target')
        run(empty, args, empty_answer())
        if NAME != 'evgap':
            run(original, [], code=2)
            for now in ('oops', '2026-10-09T02:00:00'):
                run(original, ['--now', now], code=2)
    return dict(ok=not issues, issues=issues)


if __name__ == '__main__':
    answer = check_answer(*sys.argv[1:]) if len(sys.argv) == 3 else dict(ok=False, issues=['用法：check_answer.py <proto根> <fixture>'])
    print(json.dumps(answer, ensure_ascii=False))
    raise SystemExit(0 if answer['ok'] else 1)
