"""Load and validate decision-page question data and resolve source display paths."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

COLUMNS = ('id section question eli5 options recommend why quotes details source_path '
           'source_lines source_excerpt answer answer_state answer_note answered_at').split()
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')
KEY = re.compile(r'[A-Za-z0-9]{1,8}\Z')


class Error(Exception):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(reason)


def warn(reason):
    print(f'decide_page: warning: {reason}', file=sys.stderr)


def field(ok, name):
    if not ok:
        raise Error('FieldBad', f'{name} is missing or invalid')


def strings(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def load(path):
    path = Path(path).expanduser()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Error('FileMissing', f'data file does not exist: {path}') from None
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise Error('JsonBad', f'cannot decode data: {exc}') from None
    field(isinstance(data, dict), 'data')
    if data.get('contract') != 'wf-table/1' or data.get('kind') != 'decide-page/1':
        raise Error('ContractBad', 'contract must be wf-table/1 and kind must be decide-page/1')
    for name in ('source', 'extracted', 'batch', 'line', 'title'):
        field(isinstance(data.get(name), str), name)
    field(bool(re.fullmatch(r'[A-Za-z0-9-]+', data['batch'])), 'batch')
    try:
        field(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', data['extracted'])), 'extracted')
        datetime.date.fromisoformat(data['extracted'])
    except ValueError:
        raise Error('FieldBad', 'extracted must be YYYY-MM-DD') from None
    field(strings(data.get('lead')), 'lead')
    for name in ('kicker', 'overview_svg', 'overview_caption'):
        field(isinstance(data.get(name, ''), str), name)
    field(data.get('columns') == COLUMNS, 'columns')
    field(data.get('link_columns') == ['source_path'], 'link_columns')
    field(isinstance(data.get('sections'), list), 'sections')
    sections = set()
    for i, section in enumerate(data['sections']):
        prefix = f'section {i}'
        field(isinstance(section, dict), prefix)
        for name in ('id', 'title'):
            field(isinstance(section.get(name), str) and bool(section[name]), f'{prefix}.{name}')
        field(section['id'] not in sections, f'{prefix}.id (duplicate)')
        sections.add(section['id'])
        for name in ('intro', 'figure_svg', 'caption'):
            field(isinstance(section.get(name, ''), str), f'{prefix}.{name}')
    field(isinstance(data.get('appendix', []), list), 'appendix')
    for i, item in enumerate(data.get('appendix', [])):
        field(isinstance(item, dict), f'appendix {i}')
        field(isinstance(item.get('title'), str), f'appendix {i}.title')
        field(strings(item.get('items')), f'appendix {i}.items')
    field(isinstance(data.get('rows'), list), 'rows')
    seen = set()
    for i, row in enumerate(data['rows']):
        field(isinstance(row, dict), f'row {i}')
        for name in COLUMNS:
            row.setdefault(name, [] if name in ('options', 'quotes', 'details') else '')
        rid = row['id']
        field(isinstance(rid, str) and bool(ID.fullmatch(rid)), f'row {i}.id')
        if rid in seen:
            raise Error('IdDuplicate', f'row {rid} duplicates an id')
        seen.add(rid)
        for name in COLUMNS:
            if name not in ('options', 'quotes', 'details'):
                field(isinstance(row[name], str), f'row {rid}.{name}')
        if row['section'] not in sections:
            raise Error('SectionUnknown', f'row {rid}.section names unknown section {row["section"]}')
        field(isinstance(row['options'], list), f'row {rid}.options')
        keys = set()
        for option in row['options']:
            field(isinstance(option, dict), f'row {rid}.options')
            key = option.get('key')
            field(isinstance(key, str) and bool(KEY.fullmatch(key)) and key not in keys,
                  f'row {rid}.options.key')
            keys.add(key)
            for name in ('label', 'consequence'):
                field(isinstance(option.get(name), str), f'row {rid}.options.{name}')
        if row['recommend'] and row['recommend'] not in keys:
            raise Error('RecommendBad', f'row {rid}.recommend is not an option key')
        field(strings(row['details']), f'row {rid}.details')
        field(isinstance(row['quotes'], list), f'row {rid}.quotes')
        for quote in row['quotes']:
            field(isinstance(quote, dict) and all(isinstance(quote.get(k), str)
                  for k in ('text', 'cite')), f'row {rid}.quotes')
        if not row['quotes']:
            warn(f'Row {rid} has no quotes.')
        source = row['source_path'].split('#', 1)[0]
        if source and not (path.parent / source).exists():
            warn(f'Row {rid} source_path does not exist: {source}')
    return data


def shown_source(data_path, source_path):
    if not source_path:
        return ''
    source, marker, anchor = source_path.partition('#')
    directory = Path(data_path).expanduser().resolve().parent
    try:
        result = subprocess.run(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, check=True)
        root = Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        root = directory
    shown = os.path.relpath((directory / source).resolve(), root)
    return shown + (marker + anchor if marker else '')
