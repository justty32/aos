#pragma once

#include "../src/run.hpp"

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <cstdio>

#include <fcntl.h>
#include <unistd.h>

namespace aos::test {

inline std::string read_file(const std::string &path) {
    std::ifstream input(path);
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

inline void write_file(const std::string &path, const std::string &content) {
    std::ofstream output(path, std::ios::out | std::ios::trunc);
    output << content;
}

inline std::string make_temp_dir() {
    std::string pattern = "/tmp/aos_run_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    REQUIRE(mkdtemp(buffer.data()) != nullptr);
    return buffer.data();
}

struct TempDir {
    TempDir() : path(make_temp_dir()) {}
    ~TempDir() { std::filesystem::remove_all(path); }
    std::string path;
};

// CLI 直接寫真的 fd（讀 stdin、印 stdout／stderr），而測試跟它在同一個 process 裡，
// 所以只能把描述子暫時換成檔案、離開範圍再換回來。
class ScopedFd {
public:
    ScopedFd(int target, const std::string &path, int flags)
        : target_(target), saved_(dup(target)) {
        REQUIRE(saved_ >= 0);
        const int fd = open(path.c_str(), flags, 0666);
        REQUIRE(fd >= 0);
        std::fflush(nullptr);
        REQUIRE(dup2(fd, target_) >= 0);
        close(fd);
    }
    ~ScopedFd() {
        std::fflush(nullptr);
        dup2(saved_, target_);
        close(saved_);
    }

private:
    int target_;
    int saved_;
};

class ScopedCwd {
public:
    explicit ScopedCwd(const std::string &path)
        : saved_(open(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC)) {
        REQUIRE(saved_ >= 0);
        REQUIRE(chdir(path.c_str()) == 0);
    }
    ~ScopedCwd() {
        if (saved_ >= 0) {
            fchdir(saved_);
            close(saved_);
        }
    }

private:
    int saved_;
};

inline int init_world(std::string &path) {
    char program[] = "aos init";
    char *argv[] = {program, path.data()};
    return aos::run_init(2, argv);
}

inline int exec_world(std::string &path) {
    char program[] = "aos exec";
    char *argv[] = {program, path.data()};
    return aos::run_exec(2, argv);
}

inline int loop_world(std::string &path, char *interval) {
    char program[] = "aos exec";
    char option[] = "--loop";
    char *argv[] = {program, option, interval, path.data()};
    return aos::run_exec(4, argv);
}

inline bool wait_for_file(const std::string &path) {
    for (int attempt = 0; attempt < 300; ++attempt) {
        if (std::filesystem::exists(path)) return true;
        usleep(10000);
    }
    return false;
}

inline void write_inst(const TempDir &dir, const std::string &content) {
    write_file(dir.path + "/.aos/inst.json", content);
}

}  // namespace aos::test
