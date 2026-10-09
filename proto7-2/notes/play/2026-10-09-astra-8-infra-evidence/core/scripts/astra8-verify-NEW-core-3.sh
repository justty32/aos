T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1

python3 -B proto7-2/bin/aos7-ctl --not-an-option
printf 'bad-args rc=%s\n' "$?"

# 對真 CLI main 的寫入邊界注入 EIO；不依賴 chmod 或執行者權限。
python3 -B - <<'PY'
import errno, os, sys
from unittest.mock import patch
sys.path[:0] = [
    "proto7-2/modules/tools", "proto7-2/modules/control", "proto7-2/lib"
]
import aos7_ctl
with patch.object(aos7_ctl, "write_json",
                  side_effect=OSError(errno.EIO, "astra8 write failure")):
    sys.exit(aos7_ctl.main(["daemon", os.environ["T"], "register", "n"]))
PY
printf 'write-error rc=%s\n' "$?"
rm -rf "$T"
