#!/usr/bin/env python3
"""wrap-cli fixture：不管給什麼參數都把 argv 印成 JSON（給 help 文字 fixture 當「指令本體」，測 argv 怎麼組）。
環境變數 ECHOARGS_EXIT 設了就用那個退出碼（測 CommandFailed）。"""
import json
import os
import sys

print(json.dumps(sys.argv[1:]))
if os.environ.get('ECHOARGS_EXIT'):
    print('echoargs: failing on purpose', file=sys.stderr)
    sys.exit(int(os.environ['ECHOARGS_EXIT']))
