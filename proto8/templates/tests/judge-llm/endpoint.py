#!/usr/bin/env python3
# Return deterministic semantic-comparison replies with nonzero fake token usage.
import json
import sys

args = json.load(sys.stdin)
sections = json.loads(args['request']['messages'][-1]['content'])
same = sections['expect'] == sections['got']
content = json.dumps({'score': .95 if same else .1,
                      'diff': [] if same else ['stdout.json'],
                      'why': 'same' if same else 'wrong'})
print(json.dumps({'message': {'role': 'assistant', 'content': content},
                  'model': 'judge-test',
                  'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10}}))
