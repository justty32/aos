"""固定答案＋隔離變體；不跑 make_fixture、不 import 候選。"""
NAME = 'runs'

EMPTY = {'v': 1, 'routines': [], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': []}
CASES = [(['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}]}), (['--now', '2026-10-09T12:00:00Z'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'overdue', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'overdue', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'overdue', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 3, 'ok': 1}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}]})]
VARIANTS = [
    ({'wf/routines.json': None}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': []}),
    ({'wf/routines.json': '{'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': 'NaN'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': 'null'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': '[]'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': '{"contract":"other","columns":[],"rows":[]}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': '{"contract":"wf-table/1","columns":[],"rows":{}}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': '{"contract":"wf-table/1","columns":null,"rows":[]}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [], 'schedule': [{'name': 'a-due', 'at': '2020-01-01T00:00:00+08:00', 'state': 'due'}, {'name': 'b-pending', 'at': '2099-01-01T00:00:00+08:00', 'state': 'pending'}, {'name': 'c-local', 'at': '2099-01-02T00:00:00+08:00', 'state': 'pending'}], 'counts': {'routines': {'running': 0, 'never': 0, 'failed': 0, 'overdue': 0, 'ok': 0}, 'schedule': {'interrupted': 0, 'due': 1, 'pending': 2}}, 'bad': [{'table': 'routines', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': None}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}]}),
    ({'wf/schedule.json': '{'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': 'NaN'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': 'null'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': '[]'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': '{"contract":"other","columns":[],"rows":[]}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': '{"contract":"wf-table/1","columns":[],"rows":{}}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/schedule.json': '{"contract":"wf-table/1","columns":null,"rows":[]}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'a-ok', 'every': '1h', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T11:29:48Z'}, {'name': 'b-failed', 'every': '2m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 7, 'state': 'failed', 'next': '2026-10-09T10:31:48Z'}, {'name': 'c-round', 'every': '3r', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'd-day', 'every': '1d', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-10T10:29:48Z'}, {'name': 'e-seconds', 'every': '30s', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:18Z'}, {'name': 'f-minutes', 'every': '5m', 'last_time': '2026-10-09T18:29:48.683846+08:00', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:34:48Z'}, {'name': 'g-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'h-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}, {'name': 'i-never', 'every': '1h', 'last_time': None, 'last_code': None, 'state': 'never', 'next': None}], 'schedule': [], 'counts': {'routines': {'running': 0, 'never': 4, 'failed': 1, 'overdue': 0, 'ok': 4}, 'schedule': {'interrupted': 0, 'due': 0, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 9, 'why': 'bad_row'}, {'table': 'routines', 'row': 10, 'why': 'dup_name'}, {'table': 'schedule', 'row': None, 'why': 'bad_table'}]}),
    ({'wf/routines.json': '{"contract": "wf-table/1", "columns": [], "rows": [{"name": "same", "every": "bad", "last_time": "", "last_code": ""}, {"name": "same", "every": "1h", "last_time": "", "last_code": ""}, {"name": "missing"}, {"name": "missing", "every": "1h", "last_time": "", "last_code": ""}, null, {"name": "bool", "every": "1h", "last_time": "", "last_code": true}, {"name": "", "every": "1h", "last_time": "", "last_code": ""}, {"name": "badtime", "every": "1h", "last_time": "no", "last_code": "0"}, {"name": "badcode", "every": "1h", "last_time": "", "last_code": "NaN"}, {"name": "running", "every": "1h", "last_time": "", "last_code": "running"}, {"name": "local", "every": "1h", "last_time": "2026-10-09T17:30:00.500", "last_code": "+0"}, {"name": "negative", "every": "1h", "last_time": "2026-10-09T17:30:00", "last_code": "-2"}]}', 'wf/schedule.json': '{"contract": "wf-table/1", "columns": [], "rows": [{"name": "claimed", "at": "2026-10-10T00:00:00", "claimed": "yes"}, {"name": "badtime", "at": "no", "claimed": ""}, {"name": "badtype", "at": true, "claimed": ""}, {"name": "local", "at": "2026-10-09T18:30:00", "claimed": ""}]}'}, ['--now', '2026-10-09T18:30:00+08:00'], {'v': 1, 'routines': [{'name': 'local', 'every': '1h', 'last_time': '2026-10-09T17:30:00.500', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T10:30:00Z'}, {'name': 'negative', 'every': '1h', 'last_time': '2026-10-09T17:30:00', 'last_code': -2, 'state': 'failed', 'next': '2026-10-09T10:30:00Z'}, {'name': 'running', 'every': '1h', 'last_time': None, 'last_code': 'running', 'state': 'running', 'next': None}], 'schedule': [{'name': 'claimed', 'at': '2026-10-10T00:00:00', 'state': 'interrupted'}, {'name': 'local', 'at': '2026-10-09T18:30:00', 'state': 'due'}], 'counts': {'routines': {'running': 1, 'never': 0, 'failed': 1, 'overdue': 0, 'ok': 1}, 'schedule': {'interrupted': 1, 'due': 1, 'pending': 0}}, 'bad': [{'table': 'routines', 'row': 0, 'why': 'bad_row'}, {'table': 'routines', 'row': 1, 'why': 'dup_name'}, {'table': 'routines', 'row': 2, 'why': 'bad_row'}, {'table': 'routines', 'row': 3, 'why': 'dup_name'}, {'table': 'routines', 'row': 4, 'why': 'bad_row'}, {'table': 'routines', 'row': 5, 'why': 'bad_row'}, {'table': 'routines', 'row': 6, 'why': 'bad_row'}, {'table': 'routines', 'row': 7, 'why': 'bad_row'}, {'table': 'routines', 'row': 8, 'why': 'bad_row'}, {'table': 'schedule', 'row': 1, 'why': 'bad_row'}, {'table': 'schedule', 'row': 2, 'why': 'bad_row'}]}),
    ({'wf/routines.json': '{"contract": "wf-table/1", "columns": [], "rows": [{"name": "same", "every": "bad", "last_time": "", "last_code": ""}, {"name": "same", "every": "1h", "last_time": "", "last_code": ""}, {"name": "missing"}, {"name": "missing", "every": "1h", "last_time": "", "last_code": ""}, null, {"name": "bool", "every": "1h", "last_time": "", "last_code": true}, {"name": "", "every": "1h", "last_time": "", "last_code": ""}, {"name": "badtime", "every": "1h", "last_time": "no", "last_code": "0"}, {"name": "badcode", "every": "1h", "last_time": "", "last_code": "NaN"}, {"name": "running", "every": "1h", "last_time": "", "last_code": "running"}, {"name": "local", "every": "1h", "last_time": "2026-10-09T17:30:00.500", "last_code": "+0"}, {"name": "negative", "every": "1h", "last_time": "2026-10-09T17:30:00", "last_code": "-2"}]}', 'wf/schedule.json': '{"contract": "wf-table/1", "columns": [], "rows": [{"name": "claimed", "at": "2026-10-10T00:00:00", "claimed": "yes"}, {"name": "badtime", "at": "no", "claimed": ""}, {"name": "badtype", "at": true, "claimed": ""}, {"name": "local", "at": "2026-10-09T18:30:00", "claimed": ""}]}'}, ['--now', '2026-10-09T12:00:00Z'], {'v': 1, 'routines': [{'name': 'local', 'every': '1h', 'last_time': '2026-10-09T17:30:00.500', 'last_code': 0, 'state': 'ok', 'next': '2026-10-09T18:30:00Z'}, {'name': 'negative', 'every': '1h', 'last_time': '2026-10-09T17:30:00', 'last_code': -2, 'state': 'failed', 'next': '2026-10-09T18:30:00Z'}, {'name': 'running', 'every': '1h', 'last_time': None, 'last_code': 'running', 'state': 'running', 'next': None}], 'schedule': [{'name': 'claimed', 'at': '2026-10-10T00:00:00', 'state': 'interrupted'}, {'name': 'local', 'at': '2026-10-09T18:30:00', 'state': 'pending'}], 'counts': {'routines': {'running': 1, 'never': 0, 'failed': 1, 'overdue': 0, 'ok': 1}, 'schedule': {'interrupted': 1, 'due': 0, 'pending': 1}}, 'bad': [{'table': 'routines', 'row': 0, 'why': 'bad_row'}, {'table': 'routines', 'row': 1, 'why': 'dup_name'}, {'table': 'routines', 'row': 2, 'why': 'bad_row'}, {'table': 'routines', 'row': 3, 'why': 'dup_name'}, {'table': 'routines', 'row': 4, 'why': 'bad_row'}, {'table': 'routines', 'row': 5, 'why': 'bad_row'}, {'table': 'routines', 'row': 6, 'why': 'bad_row'}, {'table': 'routines', 'row': 7, 'why': 'bad_row'}, {'table': 'routines', 'row': 8, 'why': 'bad_row'}, {'table': 'schedule', 'row': 1, 'why': 'bad_row'}, {'table': 'schedule', 'row': 2, 'why': 'bad_row'}]}),
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
