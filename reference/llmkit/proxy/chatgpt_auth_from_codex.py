#!/usr/bin/env python3
"""把 codex CLI 登入過的 token 轉成 litellm chatgpt provider 吃的格式。

codex 的 ~/.codex/auth.json 長這樣：{"auth_mode": "chatgpt", "tokens": {id_token, access_token,
refresh_token, account_id}, ...}；litellm 讀的是攤平的 {access_token, refresh_token, id_token,
expires_at, account_id}，而且它會回寫（補 expires_at、refresh 後換 token），所以不能直接 symlink
過去污染 codex 的檔，只能複製一份到 litellm 自己的路徑（預設 ~/.config/litellm/chatgpt/auth.json，
可用 CHATGPT_TOKEN_DIR / CHATGPT_AUTH_FILE 改）。

codex 那邊 token 換新（`codex login` 重登、或它自己 refresh）之後再跑一次就好。
只讀 codex 的檔，不會改它。
"""
import base64
import json
import os
import sys

src = os.path.expanduser(os.environ.get("CODEX_AUTH_FILE", "~/.codex/auth.json"))
dst_dir = os.path.expanduser(os.environ.get("CHATGPT_TOKEN_DIR", "~/.config/litellm/chatgpt"))
dst = os.path.join(dst_dir, os.environ.get("CHATGPT_AUTH_FILE", "auth.json"))

with open(src) as f:
    codex = json.load(f)
tokens = codex.get("tokens") or {}
access = tokens.get("access_token")
if codex.get("auth_mode") != "chatgpt" or not access:
    sys.exit(f"{src} 不是 chatgpt 登入（auth_mode={codex.get('auth_mode')!r}），先跑 `codex login`")


def jwt_claims(tok):
    p = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


claims = jwt_claims(access)
record = {
    "access_token": access,
    "refresh_token": tokens.get("refresh_token"),
    "id_token": tokens.get("id_token"),
    "expires_at": claims.get("exp"),
    "account_id": tokens.get("account_id")
    or (claims.get("https://api.openai.com/auth") or {}).get("chatgpt_account_id"),
}
os.makedirs(dst_dir, mode=0o700, exist_ok=True)
fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(record, f)

import datetime as _dt

exp = _dt.datetime.fromtimestamp(claims["exp"], _dt.timezone.utc) if claims.get("exp") else None
plan = (claims.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type")
print(f"寫到 {dst}（plan={plan}，access_token 到 {exp:%Y-%m-%d %H:%M} UTC 為止，之後 litellm 會自己拿 refresh_token 換）")
