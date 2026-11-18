"""agent_files - 匯出共用的定義檔與 stack 覆蓋檔宣告讀取器。"""
import os
import sys

# 單獨 import agent_files 時也找得到同層的 declared_files（S3 起共用模組平鋪在 py/、裝成 lib/）；import 後還原查找順序。
_lib = os.path.dirname(os.path.realpath(__file__))
_added_lib = os.path.isfile(os.path.join(_lib, "declared_files.py"))
if _added_lib:
    sys.path.insert(0, _lib)
try:
    from declared_files import declared_files
finally:
    if _added_lib:
        sys.path.pop(0)
