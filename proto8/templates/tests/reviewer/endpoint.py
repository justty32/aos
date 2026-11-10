#!/usr/bin/env python3
# Return fake reviewer tool calls using the actual previous review_round result.
import json
from pathlib import Path
import subprocess
import sys

PROTO = Path(__file__).resolve().parents[3]
payload = json.load(sys.stdin)
endpoint = payload['endpoint']
if endpoint.get('role') == 'reviewer':
    messages = payload['request']['messages']
    previous = next((message for message in reversed(messages)
                     if message.get('role') == 'tool'), None)
    prescription = endpoint['prescription']
    edit = {'path': 'unused.json', 'set': {'/prescriptions': [prescription]}}
    if previous:
        try:
            result = json.loads(previous['content'])
        except ValueError:
            result = {}
        if 'review' in result:
            edit['path'] = str(Path(result['review']).relative_to(endpoint['ws']))
    endpoint['script'] = [
        {'tool_calls': [{'name': 'review_round', 'arguments': endpoint['round_args']}]},
        {'tool_calls': [{'name': 'json_write', 'arguments': edit}]},
        {'content': 'Review complete; one split prescription is ready.'}]
result = subprocess.run([sys.executable, str(PROTO / 'lib/base/llm_fake/_entry')],
                        input=json.dumps(payload), capture_output=True, text=True)
sys.stderr.write(result.stderr)
if result.returncode:
    sys.stdout.write(result.stdout)
    sys.exit(result.returncode)
reply = json.loads(result.stdout)
tokens = endpoint.get('prompt_tokens', 7)
reply['usage'] = {'prompt_tokens': tokens, 'completion_tokens': 3,
                  'total_tokens': tokens + 3}
print(json.dumps(reply))
