"""退出碼。WRITER-BRIEF 4.10。"""
OK = 0
USAGE = 2
PARSE = 3        # 解析拒絕（嚴格解析失敗）
NOT_A_LAND = 4
STOPPED = 5      # 因失敗／預算停（只 run）
LOCK_BUSY = 75
CANCELLED = 130

# aos llm 專用：0 成功、2 用法錯、75 後端或傳輸失敗（可重試）、130 被取消
LLM_BACKEND = 75
