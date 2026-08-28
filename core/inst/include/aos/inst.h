#ifndef AOS_AOS_H
#define AOS_AOS_H

#include <aos/export.h>

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AOS_VERSION_MAJOR 0
#define AOS_VERSION_MINOR 1
#define AOS_VERSION_PATCH 0

/* ABI rule: existing enum values are frozen. New values may only be appended. */
typedef enum aos_inst_state {
    AOS_INST_OK = 0,
    AOS_INST_INVALID_ARGUMENT = 1,
    AOS_INST_JSON_SYNTAX = 2,
    AOS_INST_NOT_AN_OBJECT = 3,
    AOS_INST_UNKNOWN_KEY = 4,
    AOS_INST_FIELD_TYPE_MISMATCH = 5,
    AOS_INST_EMPTY_ARGV = 6,
    AOS_INST_ENV_KEY_INVALID = 7,
    AOS_INST_ALLOC_FAILED = 8,
    AOS_INST_READ_ERROR = 9,
    AOS_INST_BUFFER_TOO_SMALL = 10,
    AOS_INST_WRITE_ERROR = 11,
    AOS_INST_DIRECTIVE_KEY_COUNT_INVALID = 12,
    AOS_INST_UNKNOWN_DIRECTIVE = 13,
    AOS_INST_DIRECTIVE_VALUE_TYPE_MISMATCH = 14,
    AOS_INST_UNKNOWN_OPTION = 15
} aos_inst_state;

/* ABI rule: existing enum values are frozen. New values may only be appended. */
typedef enum aos_inst_field {
    AOS_FIELD_STDIN = 0,
    AOS_FIELD_STDOUT = 1,
    AOS_FIELD_STDERR = 2,
    AOS_FIELD_EXIT = 3,
    AOS_FIELD_CWD = 4
} aos_inst_field;

/* ABI rule: existing enum values are frozen. New values may only be appended. */
typedef enum aos_exec_state {
    AOS_EXEC_OK = 0,
    AOS_EXEC_INVALID_ARGUMENT = 1,
    AOS_EXEC_SPAWN_FAILED = 2,
    AOS_EXEC_WAIT_FAILED = 3,
    AOS_EXEC_EXIT_WRITE_FAILED = 4,
    AOS_EXEC_ALLOC_FAILED = 5
} aos_exec_state;

/* ABI rule: existing enum values are frozen. New values may only be appended.
 * Mirrors aos::HandoffState (values 0-9); values from 10 are C-ABI-only
 * extensions that have no C++ counterpart (same pattern as aos_inst_state's
 * ALLOC_FAILED/READ_ERROR/WRITE_ERROR/BUFFER_TOO_SMALL). */
typedef enum aos_handoff_state {
    AOS_HANDOFF_OK = 0,
    AOS_HANDOFF_INVALID_ARGUMENT = 1,
    AOS_HANDOFF_BUSY = 2,
    AOS_HANDOFF_NO_INSTRUCTION = 3,
    AOS_HANDOFF_INBOX_READ_FAILED = 4,
    AOS_HANDOFF_INSTRUCTION_READ_FAILED = 5,
    AOS_HANDOFF_PUBLISH_WRITE_FAILED = 6,
    AOS_HANDOFF_RENAME_FAILED = 7,
    AOS_HANDOFF_RELEASE_FAILED = 8,
    AOS_HANDOFF_DELIVERY_INVALID = 9,
    AOS_HANDOFF_ALLOC_FAILED = 10,
    AOS_HANDOFF_READ_ERROR = 11,
    AOS_HANDOFF_BUFFER_TOO_SMALL = 12
} aos_handoff_state;

typedef struct aos_instruction aos_instruction;

typedef struct aos_exec_result {
    int status;
    int signalled;
    int timed_out;
    int error;
} aos_exec_result;

/* 投遞後的檔名（"<pid>-<seq>.json"）在任何平台上都塞得進這個大小：
 * pid_t 最多 10 位十進位、seq 是 size_t 最多 20 位，含分隔字元與副檔名還有餘裕。
 * 給 aos_deliver_buffer／aos_deliver_file 的 name 緩衝區用這個常數就絕對夠用，
 * 不必先探大小——探大小的兩段式呼叫在這裡不適用，見下方函式說明。 */
#define AOS_DELIVER_NAME_MAX 64

/* aos_deliver_buffer／aos_deliver_file 的診斷輸出。result 可傳 NULL（不需要診斷時）。 */
typedef struct aos_deliver_result {
    size_t count;            /* 這批有幾筆 instruction（空批次合法） */
    aos_inst_state inst_state; /* AOS_HANDOFF_DELIVERY_INVALID 時的驗證失敗原因 */
    size_t error_record;     /* 同上，記錄序號（1 起算，尚未進入逐筆解碼時為 0） */
    int error;                /* 失敗時的 errno（依狀態而定） */
    int sync_error;           /* 已發布、但收件匣目錄 fsync 失敗的 errno（警告，非失敗） */
} aos_deliver_result;

AOS_API aos_instruction *aos_instruction_new(void);
AOS_API void aos_instruction_free(aos_instruction *instruction);
AOS_API void aos_instruction_clear(aos_instruction *instruction);

AOS_API size_t aos_instruction_argc(const aos_instruction *instruction);
AOS_API const char *aos_instruction_arg(
    const aos_instruction *instruction, size_t index);
AOS_API aos_inst_state aos_instruction_push_arg(
    aos_instruction *instruction, const char *value);

AOS_API const char *aos_instruction_field(
    const aos_instruction *instruction, aos_inst_field field);
AOS_API aos_inst_state aos_instruction_set_field(
    aos_instruction *instruction, aos_inst_field field, const char *value);
AOS_API int aos_instruction_stderr_merge(
    const aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_set_stderr_merge(
    aos_instruction *instruction, int value);

AOS_API size_t aos_instruction_env_count(const aos_instruction *instruction);
AOS_API const char *aos_instruction_env_key(
    const aos_instruction *instruction, size_t index);
AOS_API const char *aos_instruction_env_value(
    const aos_instruction *instruction, size_t index);
AOS_API aos_inst_state aos_instruction_set_env(
    aos_instruction *instruction, const char *key, const char *value);

AOS_API uint64_t aos_instruction_timeout_ms(
    const aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_set_timeout_ms(
    aos_instruction *instruction, uint64_t value);
AOS_API int aos_instruction_parallel(
    const aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_set_parallel(
    aos_instruction *instruction, int value);

AOS_API aos_inst_state aos_instruction_read_buffer(
    const char *data, size_t size, aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_read_fd(
    int fd, aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_read_file(
    const char *path, aos_instruction *instruction);
AOS_API aos_inst_state aos_instruction_write_buffer(
    const aos_instruction *instruction, char *buffer, size_t size,
    size_t *needed);
AOS_API aos_inst_state aos_instruction_write_fd(
    const aos_instruction *instruction, int fd);
AOS_API aos_inst_state aos_instruction_write_file(
    const aos_instruction *instruction, const char *path);

AOS_API aos_exec_state aos_instruction_execute(
    aos_instruction *instruction, aos_exec_result *result);

/* deliver（SPEC §D-3）：把 data／檔案內容當一批 instruction 投進
 * instruction_path 推導出的收件匣。協定細節（唯一檔名、先 .temp 後排他 rename、
 * canonical 位元組）全部內建，沒有「直接寫 ready」的捷徑；收件匣不存在時回
 * AOS_HANDOFF_INBOX_READ_FAILED，不會自動建世界。
 *
 * 每次呼叫都會真的投遞一次——跟 aos_instruction_write_buffer 那種「先探大小、
 * buffer 不夠再呼叫一次」的兩段式模式不同：這裡呼叫一次就落地一次，第二次呼叫
 * 是另一筆新投遞，不是重試。name／name_size 只影響*能不能把投遞後的檔名回報
 * 給你*，跟「有沒有投遞」無關——buffer 太小（或 name 為 NULL）時投遞已經完成，
 * 回傳 AOS_HANDOFF_BUFFER_TOO_SMALL、needed 給實際長度，但**不要**因為看到這個
 * 狀態就重打一次，重打會多投一份。給 name／name_size 至少 AOS_DELIVER_NAME_MAX
 * 就不會遇到這個狀態。needed 不得為 NULL；result 可為 NULL。 */
AOS_API aos_handoff_state aos_deliver_buffer(
    const char *instruction_path, const char *data, size_t size,
    char *name, size_t name_size, size_t *needed,
    aos_deliver_result *result);
AOS_API aos_handoff_state aos_deliver_file(
    const char *instruction_path, const char *path,
    char *name, size_t name_size, size_t *needed,
    aos_deliver_result *result);

AOS_API const char *aos_inst_state_string(aos_inst_state state);
AOS_API const char *aos_exec_state_string(aos_exec_state state);
AOS_API const char *aos_handoff_state_string(aos_handoff_state state);
AOS_API const char *aos_version_string(void);

#ifdef __cplusplus
}
#endif

#endif
