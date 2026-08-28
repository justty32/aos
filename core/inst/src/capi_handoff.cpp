#define _POSIX_C_SOURCE 200809L

#include <aos/inst.h>

#include <aos/inst.hpp>

#include <cerrno>
#include <cstring>
#include <string>

#include <fcntl.h>
#include <unistd.h>

// deliver 的 C ABI 包裝（SPEC §D-3）。跟其他 capi_*.cpp 一樣只往下看 inst.hpp，
// 例外一律在 extern "C" 邊界接住。static_assert 只鎖 aos_handoff_state 裡鏡射
// aos::HandoffState 的那 10 個值（0-9）；10 以上是 C ABI 專屬的延伸值（見 inst.h
// 的註解），跟 aos_inst_state 的 ALLOC_FAILED／READ_ERROR／BUFFER_TOO_SMALL 同一套
// 做法，不進 static_assert。

static_assert(static_cast<int>(aos::HandoffState::Ok) == AOS_HANDOFF_OK);
static_assert(static_cast<int>(aos::HandoffState::InvalidArgument) ==
              AOS_HANDOFF_INVALID_ARGUMENT);
static_assert(static_cast<int>(aos::HandoffState::Busy) == AOS_HANDOFF_BUSY);
static_assert(static_cast<int>(aos::HandoffState::NoInstruction) ==
              AOS_HANDOFF_NO_INSTRUCTION);
static_assert(static_cast<int>(aos::HandoffState::InboxReadFailed) ==
              AOS_HANDOFF_INBOX_READ_FAILED);
static_assert(static_cast<int>(aos::HandoffState::InstructionReadFailed) ==
              AOS_HANDOFF_INSTRUCTION_READ_FAILED);
static_assert(static_cast<int>(aos::HandoffState::PublishWriteFailed) ==
              AOS_HANDOFF_PUBLISH_WRITE_FAILED);
static_assert(static_cast<int>(aos::HandoffState::RenameFailed) ==
              AOS_HANDOFF_RENAME_FAILED);
static_assert(static_cast<int>(aos::HandoffState::ReleaseFailed) ==
              AOS_HANDOFF_RELEASE_FAILED);
static_assert(static_cast<int>(aos::HandoffState::DeliveryInvalid) ==
              AOS_HANDOFF_DELIVERY_INVALID);

namespace {

aos_handoff_state handoff_state(aos::HandoffState state) {
    return static_cast<aos_handoff_state>(state);
}

void fill_result(aos_deliver_result *out, const aos::DeliverResult &value) {
    if (out == nullptr) return;
    out->count = value.count;
    out->inst_state = static_cast<aos_inst_state>(value.inst_state);
    out->error_record = value.error_record;
    out->error = value.error;
    out->sync_error = value.sync_error;
}

// 核心：真的投遞一次（副作用已經發生），再把結果分裝進 name／needed／result。
// 買賣一次做完——不是「探大小」的兩段式，呼叫端的合約寫在 inst.h。
aos_handoff_state deliver_core(const std::string &instruction_path,
                               const std::string &document, char *name,
                               size_t name_size, size_t *needed,
                               aos_deliver_result *result) {
    aos::DeliverResult value;
    const aos::HandoffState state =
        aos::deliver_instructions(instruction_path, document, value);
    fill_result(result, value);
    if (state != aos::HandoffState::Ok) return handoff_state(state);

    const size_t required = value.name.size();
    *needed = required;
    if (name == nullptr || name_size <= required) {
        return AOS_HANDOFF_BUFFER_TOO_SMALL;
    }
    std::memcpy(name, value.name.data(), required);
    name[required] = '\0';
    return AOS_HANDOFF_OK;
}

int open_retry(const char *path, int flags) {
    int fd;
    do { fd = open(path, flags); } while (fd < 0 && errno == EINTR);
    return fd;
}

bool read_to_eof(int fd, std::string &out) {
    char chunk[8192];
    for (;;) {
        ssize_t count;
        do { count = read(fd, chunk, sizeof(chunk)); }
        while (count < 0 && errno == EINTR);
        if (count < 0) return false;
        if (count == 0) return true;
        out.append(chunk, static_cast<size_t>(count));
    }
}

}  // namespace

extern "C" {

AOS_API aos_handoff_state aos_deliver_buffer(
    const char *instruction_path, const char *data, size_t size, char *name,
    size_t name_size, size_t *needed, aos_deliver_result *result) {
    try {
        if (result != nullptr) *result = aos_deliver_result{};
        if (needed != nullptr) *needed = 0;
        if (instruction_path == nullptr || needed == nullptr ||
            (data == nullptr && size != 0)) {
            return AOS_HANDOFF_INVALID_ARGUMENT;
        }
        const std::string document =
            data == nullptr ? std::string() : std::string(data, size);
        return deliver_core(instruction_path, document, name, name_size,
                            needed, result);
    } catch (...) { return AOS_HANDOFF_ALLOC_FAILED; }
}

AOS_API aos_handoff_state aos_deliver_file(
    const char *instruction_path, const char *path, char *name,
    size_t name_size, size_t *needed, aos_deliver_result *result) {
    try {
        if (result != nullptr) *result = aos_deliver_result{};
        if (needed != nullptr) *needed = 0;
        if (instruction_path == nullptr || path == nullptr || needed == nullptr) {
            return AOS_HANDOFF_INVALID_ARGUMENT;
        }
        const int fd = open_retry(path, O_RDONLY | O_CLOEXEC);
        if (fd < 0) return AOS_HANDOFF_READ_ERROR;
        std::string document;
        const bool read_ok = read_to_eof(fd, document);
        const bool closed = close(fd) == 0;
        if (!read_ok || !closed) return AOS_HANDOFF_READ_ERROR;
        return deliver_core(instruction_path, document, name, name_size,
                            needed, result);
    } catch (...) { return AOS_HANDOFF_ALLOC_FAILED; }
}

AOS_API const char *aos_handoff_state_string(aos_handoff_state state) {
    try {
        switch (state) {
        case AOS_HANDOFF_OK:
        case AOS_HANDOFF_INVALID_ARGUMENT:
        case AOS_HANDOFF_BUSY:
        case AOS_HANDOFF_NO_INSTRUCTION:
        case AOS_HANDOFF_INBOX_READ_FAILED:
        case AOS_HANDOFF_INSTRUCTION_READ_FAILED:
        case AOS_HANDOFF_PUBLISH_WRITE_FAILED:
        case AOS_HANDOFF_RENAME_FAILED:
        case AOS_HANDOFF_RELEASE_FAILED:
        case AOS_HANDOFF_DELIVERY_INVALID:
            return aos::to_string(static_cast<aos::HandoffState>(state));
        case AOS_HANDOFF_ALLOC_FAILED: return "AllocationFailed";
        case AOS_HANDOFF_READ_ERROR: return "ReadError";
        case AOS_HANDOFF_BUFFER_TOO_SMALL: return "BufferTooSmall";
        }
        return "Unknown";
    } catch (...) { return nullptr; }
}

}  // extern "C"
