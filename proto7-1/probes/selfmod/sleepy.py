"""keep 任務：把 argv 帶進來的版本寫到 <node>/ver/<tid>，然後一直睡。"""
import sys
import time
from common import NODE, TID, fs, os

fs.write_json(os.path.join(NODE, "ver", TID), sys.argv[1])
while True:
    time.sleep(1)
