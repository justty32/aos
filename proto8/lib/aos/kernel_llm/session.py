# 問腦請求的固定 session id：包寫了 session_key 時，同一個寄件人的每封請求都帶同一個值，上游才接得回同一份提示快取。
# 11-14 ok-fsm 實測（thinking/2026-11/14/ok-fsm-1114/01-預設工具包-設計稿.md「第二步對照實驗結果」）：LiteLLM 的 chatgpt 後端
# 每個請求送一個 session_id，呼叫方沒給就每次換一個；帶固定值命中 88%，不帶 18%。
# 包沒寫 session_key（預設）＝請求原樣交出去，同一個物件、一個字不動。
import hashlib


def session_id(sender):
    """寄件人（它的 stack 路徑字串）→ 固定的 32 個十六進位字。只是分流用的標籤，不含路徑本身。"""
    return hashlib.sha256(sender.encode("utf-8")).hexdigest()[:32]


def tag(key, sender, request):
    """回交給端點函數的 request：key 是非空字串、有寄件人、request 是物件且自己沒寫那個鍵＝複本加 {key: session_id}；
    其他情況回原來那個物件（不複製）。"""
    if not isinstance(key, str) or not key or not isinstance(sender, str) or not sender:
        return request
    if not isinstance(request, dict) or key in request:
        return request
    out = dict(request)
    out[key] = session_id(sender)
    return out
