#pragma once

#include <aos/export.h>

#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace aos {

/* 五組宣告對應 src/ 裡五個分層，相依單向：inst ← format ← handoff、
 * inst ← format ← resolve，以及 inst ← exec。resolve、handoff、exec 互不
 * 相依；併在同一個標頭裡不代表它們可以互相引用。 */

enum class InstState {
    Ok,
    InvalidArgument,
    JsonSyntax,
    NotAnObject,
    UnknownKey,
    FieldTypeMismatch,
    EmptyArgv,
    EnvKeyInvalid,
    DirectiveKeyCountInvalid = 12,
    UnknownDirective,
    DirectiveValueTypeMismatch,
    UnknownOption,
};

enum class DirectiveKind {
    Environment,
    Reference,
};

enum class DirectiveField {
    Argv,
    Stdin,
    Stdout,
    Stderr,
    Exit,
    Cwd,
    EnvValue,
};

struct PendingDirective {
    DirectiveKind kind = DirectiveKind::Environment;
    DirectiveField field = DirectiveField::Argv;
    std::size_t argv_index = 0;
    std::string env_key;
    std::string argument;
};

struct inst_t {
    std::vector<std::string> argv;
    std::string stdin_path;
    std::string stdout_path;
    std::string stderr_path;
    bool stderr_merge = false;
    std::string exit_path;
    std::string cwd;
    std::map<std::string, std::string> env;
    std::vector<PendingDirective> pending_directives;
    std::uint64_t timeout_ms = 0;
    bool parallel = false;

    AOS_API void clear() noexcept;
};

AOS_API const char *to_string(InstState state) noexcept;

/* format：唯一懂得 JSON 文件 schema 的分層。 */

AOS_API InstState read_all(const char *data, std::size_t size,
                           std::vector<inst_t> &out,
                           std::size_t *error_record);

AOS_API InstState read_one(const char *data, std::size_t size,
                           inst_t &out);

AOS_API InstState write_one(const inst_t &inst, std::string &out);

AOS_API InstState write_all(const std::vector<inst_t> &insts, std::string &out,
                            std::size_t *error_record);
AOS_API InstState validate(const inst_t &inst);

/* resolve：以呼叫端明示的環境與路徑基準解析指示詞。 */

struct ResolveContext {
    std::map<std::string, std::string> environment;
    std::string base_path;
};

enum class ResolveState {
    Ok,
    InvalidArgument,
    EnvironmentVariableMissing,
    ValidationFailed,
    ReferenceReadFailed,
    ReferenceJsonInvalid,
    ReferencePointerInvalid,
    ReferenceValueInvalid,
    ReferenceCycle,
};

struct ResolveResult {
    DirectiveField field = DirectiveField::Argv;
    std::size_t argv_index = 0;
    std::string env_key;
    std::string variable;
    std::string reference_path;
    std::string pointer;
    std::vector<std::string> reference_chain;
    int error = 0;
    InstState validation_state = InstState::Ok;
};

AOS_API ResolveState capture_environment(
    const char *const *environment, const std::string &base_path,
    ResolveContext &context);
AOS_API ResolveState resolve(inst_t &inst, const ResolveContext &context,
                             ResolveResult &result);
AOS_API const char *to_string(ResolveState state) noexcept;
AOS_API const char *to_string(DirectiveField field) noexcept;

/* handoff：彙整、取件、釋放 instruction 檔，不執行 instruction。 */

/* 新值一律加在尾端——而且**這個列舉已經加不動了**：鏡射它的 aos_handoff_state
 * （inst.h）在第 10／11／12 三格放了 C ABI 專屬的 ALLOC_FAILED／READ_ERROR／
 * BUFFER_TOO_SMALL，C++ 端再加第 10 個值就會跟 C 端錯開，capi_handoff.cpp 的
 * static_cast 會把它翻成錯的 C 狀態。要表達新的失敗，就借語意最接近的既有值
 * （例如 #26 那個「header 寫失敗 ＋ 投遞刪失敗」的致命組合借 PublishWriteFailed，
 * 位置放在 HandoffResult::path／error），或等一次同時改兩邊的 ABI 修訂。 */
enum class HandoffState {
    Ok,
    InvalidArgument,
    Busy,
    NoInstruction,
    InboxReadFailed,
    InstructionReadFailed,
    PublishWriteFailed,
    RenameFailed,
    ReleaseFailed,
    DeliveryInvalid, /* 投遞的文件過不了唯一 parser：原因在 DeliverResult */
};

/* 新值一律加在尾端。這個列舉**沒有** C ABI 鏡射（inst.h 不宣告 issue），所以
 * 尾端追加是安全的，不像上面的 HandoffState。 */
enum class HandoffIssueKind {
    InvalidDelivery,
    DeliveryReadFailed,  /* 投遞讀不到（權限／IO）：留在原地不隔離，下一輪再試 */
    IsolationFailed,
    DeliveryRemoveFailed,
    HeaderWriteFailed,   /* header sidecar 寫不成：批照發，這一輪沒有去重保證 */
    HeaderInvalid,       /* 現任 header 讀不到或讀不懂：視同沒有 header */
    DirectorySyncFailed, /* rename／unlink 之後的目錄 fsync 失敗：耐久性缺角 */
    DeliveryNotRegular,  /* 收件匣裡不是普通檔（FIFO／目錄／socket）：跳過不讀、
                          * 不隔離。沒有寫端的 FIFO 會讓 open 永久阻塞，而那發生
                          * 在取件之前——整台機器會無聲停擺 */
    DeliveryNameIgnored, /* 以 .json 結尾但檔名形狀不合（a.b.json／.hidden.json）：
                          * 不收、不隔離，只出聲，不再靜默躺在收件匣裡 */
};

struct HandoffIssue {
    HandoffIssueKind kind = HandoffIssueKind::InvalidDelivery;
    std::string path;
    InstState inst_state = InstState::Ok;
    int error = 0;
};

struct HandoffResult {
    bool published = false;
    std::string path;
    int error = 0;
    std::vector<HandoffIssue> issues;
};

/* deliver（SPEC §D-3）：三步協定裡唯一由外部生產者執行的那一步。協定細節
 * （唯一檔名、先 .temp 後排他 rename、canonical 位元組）全部內建，所以沒有
 * 「直接寫 ready」的捷徑可用。 */
struct DeliverResult {
    std::string name;      /* 發布後的投遞檔名，例如 4711-0.json */
    std::string inbox;     /* 投遞落腳的收件匣路徑（由 instruction_path 推導） */
    std::size_t count = 0; /* 這批有幾筆 instruction（空批次合法，見 §C-2） */
    std::string path;      /* 失敗發生在哪個位置 */
    int error = 0;         /* 失敗的 errno */
    InstState inst_state = InstState::Ok; /* DeliveryInvalid 時的驗證結果 */
    std::size_t error_record = 0;         /* DeliveryInvalid 時的記錄序號（1 起算） */
    int sync_error = 0;    /* 已發布、但收件匣目錄 fsync 失敗的 errno（警告，非失敗） */
};

AOS_API HandoffState deliver_instructions(const std::string &instruction_path,
                                          const std::string &document,
                                          DeliverResult &result);
AOS_API HandoffState aggregate_instructions(
    const std::string &instruction_path, HandoffResult &result);
AOS_API HandoffState claim_instruction(
    const std::string &instruction_path, std::string &document,
    HandoffResult &result);
AOS_API HandoffState release_instruction(
    const std::string &instruction_path, HandoffResult &result);
AOS_API const char *to_string(HandoffState state) noexcept;
AOS_API const char *to_string(HandoffIssueKind kind) noexcept;

/* exec：唯一碰 fork／exec／waitpid 的分層。 */

enum class ExecState {
    Ok,
    InvalidArgument,
    SpawnFailed,
    WaitFailed,
    ExitWriteFailed,
};

struct ExecResult {
    int status = 0;
    bool signalled = false;
    bool timed_out = false;
    int error = 0;
};

AOS_API ExecState execute(inst_t &inst, ExecResult &result);
AOS_API const char *to_string(ExecState state) noexcept;

}  // namespace aos
