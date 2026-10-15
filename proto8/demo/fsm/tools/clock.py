"""工具 clock：stdin＝引數（這個工具不收引數），stdout 吐 {"time": "HH:MM:SS"}。"""
import json
import sys
import time

json.load(sys.stdin)
print(json.dumps({"time": time.strftime("%H:%M:%S")}))
