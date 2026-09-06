"""shell 工具包 — 在自己的世界資料夾裡跑一句 shell 指令。"""
import subprocess

TIMEOUT = 60

PROMPT = ("shell：sh 這個工具會在你自己的資料夾裡跑一句 shell 指令，回你退出碼跟輸出。"
          "想看檔案、找東西、跑小程式都用它。一句最多跑 60 秒，輸出太長會被截斷。"
          "會刪東西、會動別人資料夾的指令，先講一聲再做。")

TOOLS = [
    {"name": "sh",
     "description": "在你自己的資料夾裡跑一句 shell 指令，回 exit／stdout／stderr。最多跑 60 秒。",
     "parameters": {"type": "object", "properties": {
         "command": {"type": "string", "description": "要跑的 shell 指令"}},
         "required": ["command"]}},
]


def run(name, args, ctx):
    if name != "sh":
        return {"error": "shell 沒有這個工具：%s" % name}
    cmd = args.get("command") or ""
    try:
        done = subprocess.run(cmd, shell=True, cwd=ctx.world, capture_output=True,
                              text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"exit": None, "stdout": "", "stderr": "跑超過 %d 秒被砍掉了" % TIMEOUT}
    return {"exit": done.returncode, "stdout": ctx.truncate(done.stdout),
            "stderr": ctx.truncate(done.stderr)}
