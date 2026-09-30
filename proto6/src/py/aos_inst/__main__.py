"""除錯用 CLI：`python3 -m aos_inst <目標>`，只解析並把執行計畫印成 JSON，不跑、不建目錄。

對應 spec：proto6/spec/base/inst.md〈執行與錯誤〉——錯誤在 stderr 印「代號: 白話」、回 125；
用法錯回 2。身分只准目前 UID（`grant_only`），不切身分；`user` 省略時繼承目前 UID。
"""
import json
import os
import sys

from .errors import EXIT_USAGE, InstError
from .identity import grant_only
from .plan import load_plan

USAGE = "用法: python3 -m aos_inst <目標（inst 檔或資料夾）>\n"


def main(argv=None):
    """CLI 進入點；回結束碼（0 成功、125 被拒、2 用法錯）。"""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) != 1 or args[0] in ("-h", "--help", ""):
        sys.stderr.write(USAGE)
        return EXIT_USAGE
    try:
        plan = load_plan(args[0], grant_only([os.getuid()]), create_dirs=False)
    except InstError as e:
        sys.stderr.write("%s\n" % e)
        return e.exit_code
    json.dump(plan.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
