"""`tools wrap-cli` 共用常數：參數表的種類、型別、名字與旗標規則、各種上限。"""
import re

import aos_agent_tools_dev as dev


KINDS = ('flag', 'count', 'option', 'positional')
TYPES = ('string', 'integer', 'number', 'boolean')
PARAM_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}\Z')
FLAG = re.compile(r'-{1,2}[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
SKIP_FLAGS = ('--help', '--version', '-help', '-version', '-?')
INT_META = {'n', 'num', 'number', 'int', 'integer', 'count'}
FLOAT_META = {'float'}
LLM_CAP = 12000                 # 送模型的 help 文字最多幾個字
HELP_MAX = 200                  # 參數說明、工具描述最多幾個字
RUN_TIMEOUT = 50                # 產的 run 跑指令的逾時（秒），比 aos-agent 預設的 _timeout_ms 60 秒短
MAX_TIMEOUT = 600               # 參數表 timeout 的上限（秒）
MAX_NARGS = 100
CONTROL = dev.CONTROL           # 控制字元（ESC、NUL…）：描述與說明裡一律不收（審查 S1）
FIXED = ('run', 'wrapcli.json', '_common.py', 'config.json', 'README.md')
SPEC_TYPE = 'aos_wrap_cli'
