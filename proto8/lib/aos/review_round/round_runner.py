"""Execute review steps, promote cheaper passing candidates and record growth signals."""
import os
from pathlib import Path
import shutil

from tool_io import Error
from review_data import (add_cost, call, dirty, history, local, new_round, nodes,
                         read, settings, unit, write)

HERE = Path(__file__).resolve().parent


def retire(defs, reviews, count=3, refs=None):
    if len(reviews) < count:
        return []
    seen = {name for review in reviews[-count:] for node in nodes(review['tree'])
            if (name := local(node.get('def'), defs))}
    agents = []
    for path in sorted(defs.rglob('interfaces.json')):
        name = path.parent.relative_to(defs).as_posix()
        if not any(part.startswith('.') for part in path.relative_to(defs).parts) and 'aos-agent' in read(path):
            agents.append(name)
    result = []
    for name in agents:
        siblings = sorted(x for x in agents if x != name and Path(x).parent == Path(name).parent and x in seen)
        if name in seen or not siblings:
            continue
        callers = set()
        for review in reviews:
            def find_callers(node, owner=None):
                current = local(node.get('def'), defs)
                if current == name and owner:
                    callers.add(owner)
                if node.get('kind') == 'agent' and current:
                    owner = current
                for child in node.get('children', []):
                    find_callers(child, owner)
            find_callers(review['tree'])
        result.append({'def': name, 'signal': 'unused_%d_cases' % count,
                       'siblings_called': siblings, 'callers': sorted(callers),
                       'refs': refs(name) if refs else [], 'merge_into': None})
    return result


def suggestions(defs, reviews, config):
    listing = call('defs_ls', HERE.parent / 'defs', {'op': 'ls', 'root': str(defs)})
    groups = call('defs_dup', HERE.parent / 'defs', {'op': 'dup', 'root': str(defs)})['groups']
    retired = retire(defs, reviews, config.get('retire_after_cases', 3),
                     lambda name: call('defs_refs', HERE.parent / 'defs',
                                       {'op': 'refs', 'root': str(defs), 'def': name})['refs'])
    definitions = {row['path']: row for row in listing['defs']}
    reviews[-1]['definition_signatures'] = {name: signature for name, signature in
        ((row['path'], {key: row.get(key) for key in ('tools', 'endpoint', 'memory')})
         for row in listing['defs'] if row.get('brain'))}
    specialized = []
    def signature(row):
        return {key: row.get(key) for key in ('tools', 'endpoint', 'memory')}
    def child_pairs(tree):
        pairs = set()
        def walk(node, owner=None, bridge=False):
            name = local(node.get('def'), defs)
            if node.get('kind') == 'agent':
                if owner and bridge and name in definitions:
                    pairs.add((owner, name))
                owner, bridge = name, False
            elif Path(str(node.get('def', ''))).name in ('thought', 'agents'):
                bridge = True
            for child in node.get('children', []):
                walk(child, owner, bridge)
        walk(tree)
        return pairs
    if len(reviews) >= 2 and reviews[-2].get('case') != reviews[-1].get('case'):
        for source, target in sorted(child_pairs(reviews[-2]['tree']) & child_pairs(reviews[-1]['tree'])):
            proposal = signature(definitions[target])
            if reviews[-2].get('definition_signatures', {}).get(target, {}).get('tools') != proposal['tools']:
                continue
            specialized.append({'from': source, 'signal': 'repeated_child',
                'evidence': {'child': target, 'cases': [r.get('case') for r in reviews[-2:]]},
                'proposal': proposal, 'existing': [name for name, row in definitions.items()
                    if row.get('brain') and signature(row) == proposal] or None})
    threshold = config.get('max_prompt_tokens_median', 10000)
    for node in nodes(reviews[-1]['tree']):
        name = local(node.get('def'), defs)
        median = node.get('prompt_tokens_median')
        if name and type(median) in (int, float) and median > threshold:
            specialized.append({'from': name, 'signal': 'context_too_big',
                'evidence': {'prompt_tokens_median': median, 'max_prompt_tokens_median': threshold},
                'proposal': None, 'existing': None})
    return {'retire': retired, 'specialize': specialized,
            'differentiate': [dict(group, same_duty=None) for group in groups]}


def run(args):
    if not os.environ.get('AOS_STACK'):
        raise Error('StackMissing', 'AOS_STACK is not set')
    ws_value = args.get('ws') or os.environ.get('AOS_WS')
    if not ws_value or not Path(ws_value).is_dir():
        raise Error('WsMissing', 'ws or AOS_WS must name an existing directory')
    defs, case = Path(args['defs']).resolve(), Path(args['case']).resolve()
    if not defs.is_dir():
        raise Error('PathBad', 'defs must name a definition directory')
    config = settings(args['ladder'])
    reviews = Path(ws_value).resolve() / 'reviews'
    if reviews.is_relative_to(defs):
        raise Error('PathBad', 'reviews must be outside defs to copy the definition root')
    reviewed_at, folder = new_round(reviews)
    watch_file = reviews / 'watch.json'
    past = history(reviews)
    measured = []

    def measure(root):
        result = call('measure_%d' % len(measured), HERE.parent / 'measure', {
            'case': str(case), 'defs': str(root), 'repeat': config['repeat'],
            'check': {'min_score': config['min_score']}})
        measured.append(result)
        return result

    before = measure(defs)
    feed = call('watch_feed', HERE.parent / 'watch', {
        'op': 'feed', 'watch': str(watch_file), 'case': str(case), 'measure': before})
    windows = read(watch_file).get('watch', []) if watch_file.exists() else []
    excluded = {row['target'] for row in windows if row['state'] == 'watching'
                and Path(row['defs']).resolve() == defs}
    rolled_back = {row['target'] for row in feed['changes'] if row['state'] == 'rolled_back'}
    excluded.update(row['target'] for row in windows if row['target'] in rolled_back
                    and row['state'] == 'rolled_back' and Path(row['defs']).resolve() == defs)
    choices = [(node, local(node.get('def'), defs)) for node in nodes(before['tree'])
               if node.get('kind') == 'agent']
    choices = [(node, name) for node, name in choices if name and name not in excluded]
    choices.sort(key=lambda pair: pair[0]['cost'].get('token', {}).get('in', 0), reverse=True)
    review = {
        'round': folder.name, 'case': str(case), 'defs': str(defs),
        'before': before['cost'], 'after': before['cost'], 'size_bytes': before['size_bytes'],
        'tree': before['tree'], 'target': None, 'tried': [], 'adopted': None, 'dirty': [],
        'proposed': None, 'action': 'none', 'prescriptions': [], 'suggest': {},
        'why': 'No eligible agent definition was measured.', 'reviewed_at': reviewed_at,
        'steps': {
            'measure': {'repeat': config['repeat'], 'pass': before['check']['pass'],
                        'reason': 'Measured the complete case with the configured score threshold.'},
            'pick': {'reason': 'No eligible agent definition was measured.'},
            'try': {'reason': 'No downgrade was attempted.'},
            'propagate': {'reason': 'Every candidate measurement covers the complete case.'},
            'record': {'reason': 'Recorded the review without replacing a definition.'},
            'watch': {'changes': feed['changes'], 'reason': 'Fed the new case before selecting a target.'},
            'grow': {'reason': 'Record growth suggestions without applying them.'}}}
    if 'consistency' in before:
        review['consistency'] = before['consistency']
    if choices:
        _, target = choices[0]
        review['target'] = {'def': target, 'reason': 'Agent with the largest measured token.in cost.'}
        review['steps']['pick'] = review['target'].copy()
        review['dirty'] = dirty(before['tree'], target, defs)
        candidate = folder / 'defs'
        shutil.copytree(defs, candidate, symlinks=True)
        review['proposed'] = str(candidate)
        review['action'] = 'prescribe'
        llm_file = candidate / target / 'llm.json'
        llm = read(llm_file) if llm_file.exists() else {}
        endpoint = llm.get('endpoint')
        adopted, last = None, before
        if endpoint in config['ladder']:
            for lower in config['ladder'][config['ladder'].index(endpoint) + 1:]:
                llm['endpoint'] = lower
                write(llm_file, llm)
                attempt = measure(candidate)
                passed = attempt['check']['pass']
                review['tried'].append({'move': 'downgrade', 'from': endpoint, 'to': lower,
                                        'scores': attempt['check']['scores'], 'pass': passed})
                if not passed:
                    break
                endpoint, adopted, last = lower, lower, attempt
        llm['endpoint'] = endpoint
        if llm_file.exists():
            write(llm_file, llm)
        review['steps']['try'] = {'counter_tried': len(review['tried']),
                                  'reason': 'Stopped at the first failed level and retained the last passing endpoint.'}
        review['after'] = last['cost']
        cheaper = adopted is not None and unit(last['cost'], last['size_bytes'], config['watch']['metric']) < unit(
            before['cost'], before['size_bytes'], config['watch']['metric'])
        review['why'] = 'No cheaper passing downgrade was found; prescriptions may be added.'
        if cheaper:
            review['action'] = 'downgrade'
            review['adopted'] = {'move': 'downgrade', 'to': adopted}
            review['why'] = 'The candidate passed the complete case and reduced unit cost.'
            pending = {'defs': str(defs), 'target': target, 'from': str(candidate)}
            if config.get('promote_by', 'self') == 'claude':
                review['pending_promote'] = pending
                review['steps']['record'] = {'reason': 'Promotion is pending Claude approval.'}
            else:
                try:
                    promoted = call('promote', HERE.parent / 'promote',
                                    dict(pending, **({'daemons': args['daemons']} if 'daemons' in args else {})),
                                    tolerated=('DefBusy',))
                except Error as error:
                    if error.code != 'DefBusy':
                        raise
                    review['pending_promote'] = pending
                    review['steps']['record'] = {'reason': 'Promotion is pending because the definition is busy.',
                                                'error': '%s %s' % (error.code, error)}
                else:
                    count = config['watch']['baseline_cases']
                    baselines = [unit(row['before'], row['size_bytes'], config['watch']['metric'])
                                 for row in (past + [review])[-count:]]
                    # baseline_cases 只給這裡算 baseline，不交給 watch（11-10 晚 tool_io 起不認得的鍵＝ArgumentsBad）
                    watch_args = {k: v for k, v in config['watch'].items() if k != 'baseline_cases'}
                    opened = call('watch_open', HERE.parent / 'watch', dict(
                        watch_args, op='open', watch=str(watch_file), target=target, defs=str(defs),
                        round=folder.name, promoted_at=promoted['promoted_at'],
                        baseline=sum(baselines) / len(baselines)))
                    review['steps']['watch']['opened'] = opened['changes']
                    review['steps']['record'] = {'promoted_at': promoted['promoted_at'],
                                                'reason': 'Promoted the cheaper passing candidate and opened a watch window.'}
    review['spent'] = add_cost(cost for result in measured for cost in [
        result['check']['cost'], *(sample['cost'] for sample in result['samples'])])
    review['suggest'] = suggestions(defs, past + [review], config)
    path = folder / 'review.json'
    write(path, review)
    return {'round': folder.name, 'review': str(path), 'action': review['action']}
