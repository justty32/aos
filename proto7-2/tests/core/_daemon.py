"""daemon 的測試：登記／取消登記、node 消失搬走 → missing、early_tock 兩種、pause owner、resume 順便 wake、stop／SIGTERM、
控制檔洪水與壞檔、回條只留上一次、卡住的 tick／tock、kill -9 daemon 後接手、舊動作接管、root 消失、log.on。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import json
import copy
import io
import threading
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest
import warnings
from types import SimpleNamespace
from unittest import mock

from base import BIN, LIB, SLEEP, DaemonCase, kill_space_procs
from _matrix import Fault
import aos7_daemon
import aos7_fs
import aos7_proc
import aos7_task
from aos7_fs import read_json, write_json
from aos7_taskside import read_jsonl


