# 這是 snippet，複製後改名（或整段貼進你的主程式），不要直接在這裡改。
"""把資料存成一個 JSON 檔、再讀回來。路徑一律用參數傳進來，不寫死在函式裡。"""
# SNIPPET-BODY：scaffold 只會把這一行以下的內容（含 import）合進主程式。
import json
import os


def load(path, default=None):
    """讀 JSON 檔。檔案不存在、或內容壞掉，都回 default，不會丟例外。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def save(path, data):
    """先寫 .tmp 再改名，寫到一半被中斷也不會留下半個檔。回寫好的路徑。"""
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path
