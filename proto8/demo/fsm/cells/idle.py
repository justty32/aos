"""idle 格：看 inbox/ 有沒有信（*.txt）。有就拿最早那封開一段新對話、回 next=thinking；沒有就不回 next（留在 idle）。"""
import os

from common import DIR, args, ret, save

args()
inbox = os.path.join(DIR, "inbox")
mail = sorted(n for n in os.listdir(inbox) if n.endswith(".txt"))
if not mail:
    ret({})
else:
    path = os.path.join(inbox, mail[0])
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    save([{"role": "user", "text": text}])
    os.remove(path)
    ret({"next": "thinking", "data": {"q": text}})
