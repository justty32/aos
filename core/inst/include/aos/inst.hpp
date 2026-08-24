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
};

struct ResolveResult {
    DirectiveField field = DirectiveField::Argv;
    std::size_t argv_index = 0;
    std::string env_key;
    std::string variable;
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
};

enum class HandoffIssueKind {
    InvalidDelivery,
    DeliveryReadFailed,
    IsolationFailed,
    DeliveryRemoveFailed,
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
