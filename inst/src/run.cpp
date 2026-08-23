#define _POSIX_C_SOURCE 200809L

#include "run.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace aos {
namespace {

int open_input(const char *path) {
    int fd;
    do {
        fd = open(path, O_RDONLY | O_CLOEXEC);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

bool read_input(int fd, std::string &buffer, int &error) {
    char chunk[64 * 1024];
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, chunk, sizeof(chunk));
        } while (count < 0 && errno == EINTR);

        if (count < 0) {
            error = errno;
            return false;
        }
        if (count == 0) {
            return true;
        }

        const auto size = static_cast<std::size_t>(count);
        buffer.append(chunk, size);
    }
}

}  // namespace

int run(int argc, char *argv[]) {
    if (argc < 1 || argc > 2) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos inst";
        std::fprintf(stderr, "usage: %s [file]\n", program);
        return 2;
    }

    const bool from_file = argc == 2;
    const char *source = from_file ? argv[1] : "standard input";
    int fd = STDIN_FILENO;
    if (from_file) {
        fd = open_input(source);
        if (fd < 0) {
            std::fprintf(stderr, "aos inst: cannot open %s: %s\n", source,
                         std::strerror(errno));
            return 1;
        }
    }

    std::string buffer;
    int read_error = 0;
    bool read_ok = false;
    bool out_of_memory = false;
    try {
        read_ok = read_input(fd, buffer, read_error);
    } catch (const std::bad_alloc &) {
        out_of_memory = true;
    } catch (const std::length_error &) {
        out_of_memory = true;
    }

    int close_error = 0;
    if (from_file && close(fd) != 0) {
        close_error = errno;
    }
    if (out_of_memory) {
        std::fprintf(stderr, "aos inst: cannot read %s: out of memory\n", source);
        return 1;
    }
    if (!read_ok) {
        std::fprintf(stderr, "aos inst: cannot read %s: %s\n", source,
                     std::strerror(read_error));
        return 1;
    }
    if (close_error != 0) {
        std::fprintf(stderr, "aos inst: cannot close %s: %s\n", source,
                     std::strerror(close_error));
        return 1;
    }

    std::vector<inst_t> instructions;
    std::size_t error_record = 0;
    const char empty = '\0';
    const char *data = buffer.empty() ? &empty : buffer.data();
    /* format 與 exec 兩層都以「配置失敗就丟例外」為契約——C ABI 那側在每個
     * extern "C" 進入點把它們接成錯誤碼，原生 CLI 這側就得自己接。少了這幾個
     * catch，一份夠大的指令檔會讓整個行程 SIGABRT，而不是像讀檔階段那樣印一
     * 行訊息後乾淨地回 1。 */
    InstState parse_state = InstState::Ok;
    bool parse_out_of_memory = false;
    try {
        parse_state = read_all(data, buffer.size(), instructions, &error_record);
    } catch (const std::bad_alloc &) {
        parse_out_of_memory = true;
    } catch (const std::length_error &) {
        parse_out_of_memory = true;
    }
    if (parse_out_of_memory) {
        std::fprintf(stderr, "aos inst: cannot parse %s: out of memory\n",
                     source);
        return 1;
    }
    if (parse_state != InstState::Ok) {
        if (error_record != 0) {
            std::fprintf(stderr, "aos inst: %s: record %zu: %s\n", source,
                         error_record, to_string(parse_state));
        } else {
            std::fprintf(stderr, "aos inst: %s: %s\n", source,
                         to_string(parse_state));
        }
        return 1;
    }

    bool failed = false;
    for (std::size_t index = 0; index < instructions.size(); ++index) {
        ExecResult result;
        /* execute() 在 fork 之前要合併環境變數、解析 PATH，一樣會配置記憶體。
         * 這裡把配置失敗當成「這一筆失敗」而不是整批中止，跟其他 exec 錯誤
         * 的處理方式一致。 */
        ExecState state = ExecState::Ok;
        try {
            state = execute(instructions[index], result);
        } catch (const std::bad_alloc &) {
            state = ExecState::SpawnFailed;
            result.error = ENOMEM;
        } catch (const std::length_error &) {
            state = ExecState::SpawnFailed;
            result.error = ENOMEM;
        }
        if (state != ExecState::Ok) {
            failed = true;
            if (result.error != 0) {
                std::fprintf(stderr, "aos inst: record %zu: %s: %s\n",
                             index + 1, to_string(state),
                             std::strerror(result.error));
            } else {
                std::fprintf(stderr, "aos inst: record %zu: %s\n", index + 1,
                             to_string(state));
            }
        }
    }
    return failed ? 1 : 0;
}

}  // namespace aos

/* aos 執行檔的 `inst` 子命令從這裡進來。名字要跟 inst/CMakeLists.txt 裡
 * aos_add_subcommand(ENTRY ...) 登記的一致；用 C 連結是為了讓 CMake 產生的
 * 那張表可以直接寫出宣告，不必知道 C++ 的名稱修飾規則。 */
extern "C" int aos_inst_cli_main(int argc, char *argv[]) {
    return aos::run(argc, argv);
}
