"""錯誤型別：所有被拒的情況都丟 `InstError`，`str(e)` 是「代號: 白話」。

對應 spec：proto6/spec/base/inst.md〈執行與錯誤〉與 proto5/spec/directives/errors.md §6。
`exit_code` 是呼叫方該回的程序結束碼：一般 125（沒跑、不寫 exit），用法錯 2。
"""

EXIT_REFUSED = 125      # 授權、解析驗證、執行前準備失敗：不啟動、不寫 exit
EXIT_USAGE = 2          # 用法錯（例如目標資料夾裡找不到 inst）

# inst 宿主自己的代號（inst.md〈執行與錯誤〉表）
INST_CODES = (
    "ReadFailed", "JsonSyntax", "NotAnObject", "MetainfoInvalid",
    "UnsupportedInstType", "UnsupportedInstVersion", "EmptyArgv",
    "FieldTypeMismatch", "EnvKeyInvalid",
)
# 指示詞機制的代號（directives/errors.md §6）
DIRECTIVE_CODES = (
    "UnknownDirective", "DirectiveValueTypeMismatch", "FormatVariableInvalid",
    "UnknownOption", "OptionConflict", "EnvironmentVariableMissing",
    "UnknownFormatVariable", "ReferenceReadFailed", "ReferenceJsonInvalid",
    "ReferencePointerInvalid", "ReferenceCycle",
)
# 身分（inst.md 標「建議預設，未拍板」的代號，照建議用）
IDENTITY_CODES = ("UserInvalid", "UserNotGranted", "UserMismatch", "SourceChanged")
# 本實作自訂（spec 沒給代號的地方，見 README〈自己做的判斷〉）
LOCAL_CODES = (
    "Usage",            # 用法錯，exit_code 2
    "PrepareFailed",    # 執行前建目錄／開串流失敗、cwd 不是資料夾、exit 父目錄不存在
    "FinalizeFailed",   # 子程式跑完了，但 exit 檔寫不進去
)


class InstError(Exception):
    """一份 inst 被拒（不是程式炸了）。`code` 代號、`msg` 白話、`exit_code` 建議結束碼。"""

    def __init__(self, code, msg, exit_code=EXIT_REFUSED):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg
        self.exit_code = exit_code


def usage(msg):
    """用法錯（結束碼 2）。"""
    return InstError("Usage", msg, EXIT_USAGE)
