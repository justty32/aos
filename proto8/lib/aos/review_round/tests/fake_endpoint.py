#!/usr/bin/env python3
# Run the real fake endpoint and report the endpoint's configured token usage.
import json
from pathlib import Path
import subprocess
import sys


args = json.load(sys.stdin)
fake = Path(__file__).resolve().parents[3] / 'base/llm_fake/_entry'
result = subprocess.run([sys.executable, str(fake)], input=json.dumps(args),
                        capture_output=True, text=True)
if result.returncode:
    sys.stderr.write(result.stderr)
    sys.stdout.write(result.stdout)
    sys.exit(result.returncode)
value = json.loads(result.stdout)
tokens = args['endpoint']['prompt_tokens']
value['usage'] = {'prompt_tokens': tokens, 'completion_tokens': 3,
                  'total_tokens': tokens + 3}
print(json.dumps(value))
