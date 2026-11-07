"""Execute the scripted review steps and promote only cheaper passing candidates."""
import os
from pathlib import Path
import shutil

from tool_io import Error
from review_data import (add_cost, call, dirty, history, local, new_round, nodes,
                         read, settings, unit, write)

HERE = Path(__file__).resolve().parent


def retire(defs, reviews):
    if len(reviews) < 3:
        return []
    seen = {name for review in reviews[-3:] for node in nodes(review['tree'])
            if (name := local(node.get('def'), defs))}
    candidates = []
    for path in sorted(defs.rglob('interfaces.json')):
        relative = path.parent.relative_to(defs).as_posix()
        if any(part.startswith('.') for part in path.relative_to(defs).parts):
            continue
        if 'aos-agent' in read(path) and relative not in seen:
            candidates.append(relative)
    return candidates


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
            'grow': {'reason': 'Suggest retirement after three absent rounds; specialization is deferred.'}}}
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
                    opened = call('watch_open', HERE.parent / 'watch', dict(
                        config['watch'], op='open', watch=str(watch_file), target=target, defs=str(defs),
                        round=folder.name, promoted_at=promoted['promoted_at'],
                        baseline=sum(baselines) / len(baselines)))
                    review['steps']['watch']['opened'] = opened['changes']
                    review['steps']['record'] = {'promoted_at': promoted['promoted_at'],
                                                'reason': 'Promoted the cheaper passing candidate and opened a watch window.'}
    review['spent'] = add_cost(cost for result in measured for cost in [
        result['check']['cost'], *(sample['cost'] for sample in result['samples'])])
    review['suggest'] = {'retire': retire(defs, past + [review]), 'specialize': []}
    path = folder / 'review.json'
    write(path, review)
    return {'round': folder.name, 'review': str(path), 'action': review['action']}
