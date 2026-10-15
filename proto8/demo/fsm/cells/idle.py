"""idle 格（cwd＝frame）：看 inbox/ 有沒有信（*.txt）。有就拿最早那封開一段新對話（history＝[user 訊息]）、回 next=thinking；
沒有就回 next=done（done 在 end 裡：寫 ret.json、停掉拍它的 loop）。"""
import os

from common import ret, save

mail = sorted(n for n in os.listdir("inbox") if n.endswith(".txt")) if os.path.isdir("inbox") else []
if not mail:
    ret({"next": "done"})
else:
    path = os.path.join("inbox", mail[0])
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    save([{"role": "user", "content": text}])
    os.remove(path)
    ret({"next": "thinking", "data": {"q": text}})
