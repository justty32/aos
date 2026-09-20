"""把 Claude Code 登入過的 OAuth token 餵給 litellm 的 anthropic/ provider，每次呼叫都拿最新的。

Claude Code 的登入檔在 ~/.claude/.credentials.json：{"claudeAiOauth": {accessToken, refreshToken,
expiresAt(毫秒), ...}}。accessToken（sk-ant-oat01-…）只活幾小時，Claude Code 自己會續，所以不能像
DEEPSEEK_API_KEY 那樣寫死在 yaml 或啟動時讀一次。這支是 litellm proxy 的 callback（yaml 的
litellm_settings.callbacks 掛上 claude_auth_from_claude_code.handler）：每個請求進來，先看它打到的
deployment 是不是 api_key 寫著 claude-code-login 這個佔位值，是的話就從登入檔讀最新 accessToken
塞進 data["api_key"]（router 會用它蓋掉 yaml 那個佔位值）。litellm 1.87.5 看到 sk-ant-oat01- 開頭
的 key 會自動改用 Authorization: Bearer 加 anthropic-beta: oauth-2025-04-20，不用另外設 header。

順便做第二件事：Anthropic 的 OAuth 後端對 opus-5 / sonnet-5 要求 system prompt 的第一個 block
一字不差是「You are Claude Code, Anthropic's official CLI for Claude.」（獨立一塊，後面才能接你自己的
system），不然回 429 rate_limit_error、訊息只有 "Error"（2026-09-20 實打；haiku-4.5 不檢查）。
litellm 把每個 OpenAI system 訊息各自轉成一個 Anthropic system block、順序不變，所以這裡在 messages
最前面插一條那句話的 system 訊息，你原本的 system 會變成第二塊，照樣生效。

只讀 ~/.claude/.credentials.json，不寫、不 refresh —— 續 token 是 Claude Code 的事。
檔案沒變（mtime 一樣）就用快取，不會每個請求都開檔。
登入檔路徑可用 CLAUDE_CODE_CREDENTIALS_FILE 改。
"""
import json
import os
import time
from typing import Optional

from fastapi import HTTPException

from litellm.integrations.custom_logger import CustomLogger

SENTINEL = "claude-code-login"
CLAUDE_CODE_SYSTEM = "You are Claude Code, Anthropic's official CLI for Claude."
CRED_FILE = os.path.expanduser(
    os.environ.get("CLAUDE_CODE_CREDENTIALS_FILE", "~/.claude/.credentials.json")
)


class ClaudeCodeAuth(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self._mtime: Optional[float] = None
        self._token: Optional[str] = None
        self._expires_at: float = 0.0  # 秒

    def _load(self) -> None:
        try:
            mtime = os.stat(CRED_FILE).st_mtime
        except FileNotFoundError:
            raise HTTPException(
                status_code=401,
                detail={"error": f"找不到 {CRED_FILE}，先跑一次 `claude` 登入"},
            )
        if mtime == self._mtime and self._token:
            return
        with open(CRED_FILE) as f:
            oauth = (json.load(f).get("claudeAiOauth") or {})
        token = oauth.get("accessToken")
        if not token:
            raise HTTPException(
                status_code=401,
                detail={"error": f"{CRED_FILE} 裡沒有 claudeAiOauth.accessToken，先跑一次 `claude` 登入"},
            )
        self._mtime = mtime
        self._token = token
        self._expires_at = (oauth.get("expiresAt") or 0) / 1000

    def token(self) -> str:
        self._load()
        if self._expires_at and time.time() > self._expires_at:
            # 不自己 refresh：Claude Code 一動就會續（登入檔 mtime 會變，下次呼叫自動吃到新的）。
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Claude Code 的 accessToken 已過期而且還沒續；開一下 `claude` 讓它自己續掉再打"
                },
            )
        return self._token  # type: ignore[return-value]

    @staticmethod
    def _uses_claude_code(model: Optional[str]) -> bool:
        if not model:
            return False
        from litellm.proxy.proxy_server import llm_router

        if llm_router is None:
            return False
        for d in llm_router.get_model_list(model_name=model) or []:
            if (d.get("litellm_params") or {}).get("api_key") == SENTINEL:
                return True
        return False

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type):
        if not self._uses_claude_code(data.get("model")):
            return None
        data["api_key"] = self.token()
        msgs = data.get("messages")
        if isinstance(msgs, list) and not (
            msgs and msgs[0].get("role") == "system" and msgs[0].get("content") == CLAUDE_CODE_SYSTEM
        ):
            data["messages"] = [{"role": "system", "content": CLAUDE_CODE_SYSTEM}, *msgs]
        return data


handler = ClaudeCodeAuth()
