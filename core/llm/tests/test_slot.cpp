#include <aos/slot.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <sys/wait.h>
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

class ScopedEnv {
public:
    ScopedEnv(const char *name, const std::string &value) : name_(name) {
        if (const char *old = std::getenv(name)) old_ = old;
        if (::setenv(name, value.c_str(), 1) != 0) {
            throw std::runtime_error("無法設定測試環境變數");
        }
    }

    ~ScopedEnv() {
        if (old_) {
            (void)::setenv(name_.c_str(), old_->c_str(), 1);
        } else {
            (void)::unsetenv(name_.c_str());
        }
    }

private:
    std::string name_;
    std::optional<std::string> old_;
};

std::filesystem::path make_temp_directory() {
    std::array<char, 64> pattern{};
    const std::string text = "/tmp/aos-slot-test-XXXXXX";
    std::copy(text.begin(), text.end(), pattern.begin());
    if (::mkdtemp(pattern.data()) == nullptr) {
        throw std::runtime_error("無法建立測試暫存目錄");
    }
    return pattern.data();
}

class TestHome {
public:
    TestHome()
        : root_(make_temp_directory()), world_(root_ / "world"),
          home_env_("AOS_HOME", root_.string()),
          folder_env_("AOS_FOLDER", world_.string()) {
        std::filesystem::create_directories(world_);
    }

    ~TestHome() { std::filesystem::remove_all(root_); }

    const std::filesystem::path &root() const { return root_; }
    const std::filesystem::path &world() const { return world_; }

private:
    std::filesystem::path root_;
    std::filesystem::path world_;
    ScopedEnv home_env_;
    ScopedEnv folder_env_;
};

void write_json(const std::filesystem::path &path,
                const nlohmann::json &value) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    if (!output) throw std::runtime_error("無法寫入測試設定");
    output << value;
    if (!output) throw std::runtime_error("無法寫入測試設定");
}

std::size_t file_count(const std::filesystem::path &directory) {
    if (!std::filesystem::is_directory(directory)) return 0;
    return static_cast<std::size_t>(
        std::distance(std::filesystem::directory_iterator(directory),
                      std::filesystem::directory_iterator{}));
}

bool write_all(int descriptor, const std::string &text) {
    std::size_t written = 0;
    while (written < text.size()) {
        const ssize_t result =
            ::write(descriptor, text.data() + written, text.size() - written);
        if (result <= 0) return false;
        written += static_cast<std::size_t>(result);
    }
    return true;
}

std::vector<std::string> read_lines(const std::filesystem::path &path) {
    std::ifstream input(path);
    std::vector<std::string> lines;
    for (std::string line; std::getline(input, line);) lines.push_back(line);
    return lines;
}

}  // namespace

TEST_CASE("llm slot stays disabled without a user limit") {
    TestHome home;

    const aos::llm::Slot slot = aos::llm::acquire("lmstudio");

    CHECK_FALSE(slot.held());
    CHECK(slot.index() == -1);
    CHECK_FALSE(std::filesystem::exists(home.root() / "slots"));
}

TEST_CASE("llm slot merges user and world limits") {
    TestHome home;
    const auto user_path = home.root() / "cpus.json";
    const auto world_path = home.world() / ".aos" / "llm.json";
    write_json(user_path,
               {{"lmstudio", {{"max_inflight", 1}, {"wait_ms", 2000}}}});

    write_json(world_path, {{"lmstudio", {{"max_inflight", 0}}}});
    auto limit = aos::llm::read_limit("lmstudio", home.world());
    REQUIRE(limit.max_inflight);
    CHECK(*limit.max_inflight == 0);
    CHECK(limit.wait_ms == 2000);

    write_json(world_path, {{"lmstudio", {{"max_inflight", 5}}}});
    limit = aos::llm::read_limit("lmstudio", home.world());
    REQUIRE(limit.max_inflight);
    CHECK(*limit.max_inflight == 1);

    write_json(world_path, {{"lmstudio", {{"wait_ms", 50}}}});
    limit = aos::llm::read_limit("lmstudio", home.world());
    REQUIRE(limit.max_inflight);
    CHECK(*limit.max_inflight == 1);
    CHECK(limit.wait_ms == 50);

    write_json(world_path, {{"foo", {{"max_inflight", 2}}}});
    const auto world_only = aos::llm::read_limit("foo", home.world());
    CHECK_FALSE(world_only.max_inflight);
}

TEST_CASE("llm slot limit zero returns immediately") {
    TestHome home;
    write_json(home.root() / "cpus.json",
               {{"lmstudio", {{"max_inflight", 1}, {"wait_ms", 5000}}}});
    write_json(home.world() / ".aos" / "llm.json",
               {{"lmstudio", {{"max_inflight", 0}}}});

    const auto start = std::chrono::steady_clock::now();
    CHECK_THROWS_AS(aos::llm::acquire("lmstudio", 0, home.world()),
                    aos::llm::WaitingLlm);
    const auto elapsed = std::chrono::steady_clock::now() - start;
    CHECK(elapsed < std::chrono::milliseconds(500));
}

TEST_CASE("one llm slot excludes a second holder") {
    TestHome home;
    write_json(home.root() / "cpus.json",
               {{"lmstudio", {{"max_inflight", 1}, {"wait_ms", 100}}}});

    aos::llm::Slot first = aos::llm::acquire("lmstudio");
    REQUIRE(first.held());
    CHECK(first.index() == 0);
    CHECK_THROWS_AS(aos::llm::acquire("lmstudio"),
                    aos::llm::WaitingLlm);

    first.release();
    aos::llm::Slot next = aos::llm::acquire("lmstudio");
    CHECK(next.held());
    CHECK(next.index() == 0);
}

TEST_CASE("waiting llm slots honor numeric priority") {
    TestHome home;
    write_json(home.root() / "cpus.json",
               {{"priority", {{"max_inflight", 1}, {"wait_ms", 5000}}}});
    aos::llm::Slot parent_slot = aos::llm::acquire("priority");
    REQUIRE(parent_slot.held());

    const auto result_path = home.root() / "priority-results";
    const int result_descriptor =
        ::open(result_path.c_str(), O_CREAT | O_WRONLY | O_APPEND, 0666);
    REQUIRE(result_descriptor >= 0);

    const std::array<int, 3> priorities = {1, 5, 3};
    std::vector<pid_t> children;
    for (const int priority : priorities) {
        const std::string line = std::to_string(priority) + "\n";
        const pid_t child = ::fork();
        if (child < 0) {
            parent_slot.release();
            for (const pid_t started : children) {
                (void)::kill(started, SIGKILL);
                (void)::waitpid(started, nullptr, 0);
            }
            FAIL("無法 fork 測試子行程");
        }
        if (child == 0) {
            // fork 會繼承父行程的槽 fd，子行程先關掉自己這份。
            parent_slot.release();
            try {
                aos::llm::Slot slot =
                    aos::llm::acquire("priority", priority, home.world());
                const bool wrote = write_all(result_descriptor, line);
                slot.release();
                ::_exit(wrote ? 0 : 3);
            } catch (...) {
                ::_exit(2);
            }
        }
        children.push_back(child);
    }
    (void)::close(result_descriptor);

    const auto deadline =
        std::chrono::steady_clock::now() + std::chrono::seconds(3);
    const auto wait_directory = home.root() / "slots" / "priority" / "wait";
    while (file_count(wait_directory) < 3 &&
           std::chrono::steady_clock::now() < deadline) {
        (void)::usleep(20000);
    }
    const bool all_waiting = file_count(wait_directory) == 3;
    parent_slot.release();

    bool children_ok = true;
    for (const pid_t child : children) {
        int status = 0;
        pid_t result;
        do {
            result = ::waitpid(child, &status, 0);
        } while (result < 0 && errno == EINTR);
        children_ok = children_ok && result == child && WIFEXITED(status) &&
                      WEXITSTATUS(status) == 0;
    }

    REQUIRE(all_waiting);
    REQUIRE(children_ok);
    CHECK(read_lines(result_path) ==
          std::vector<std::string>{"5", "3", "1"});
}

TEST_CASE("dead llm wait ticket does not block the queue") {
    TestHome home;
    write_json(home.root() / "cpus.json",
               {{"lmstudio", {{"max_inflight", 1}, {"wait_ms", 500}}}});
    const auto wait_directory =
        home.root() / "slots" / "lmstudio" / "wait";
    std::filesystem::create_directories(wait_directory);
    const auto dead_ticket =
        wait_directory / "0000000000-00000000000000000000-0";
    {
        std::ofstream output(dead_ticket);
        REQUIRE(output.good());
    }

    const auto statuses = aos::llm::slot_status();
    REQUIRE(statuses.size() == 1);
    CHECK(statuses[0].waiting == 0);
    CHECK(std::filesystem::exists(dead_ticket));

    aos::llm::Slot slot = aos::llm::acquire("lmstudio");

    CHECK(slot.held());
    CHECK_FALSE(std::filesystem::exists(dead_ticket));
}

TEST_CASE("llm slot status reports held slots") {
    TestHome home;
    write_json(home.root() / "cpus.json",
               {{"status-cpu", {{"max_inflight", 2}, {"wait_ms", 700}}}});
    aos::llm::Slot slot = aos::llm::acquire("status-cpu");

    auto statuses = aos::llm::slot_status();
    REQUIRE(statuses.size() == 1);
    CHECK(statuses[0].cpu == "status-cpu");
    CHECK(statuses[0].max_inflight == 2);
    CHECK(statuses[0].held == 1);
    CHECK(statuses[0].waiting == 0);
    CHECK(statuses[0].wait_ms == 700);

    slot.release();
    statuses = aos::llm::slot_status();
    REQUIRE(statuses.size() == 1);
    CHECK(statuses[0].held == 0);
}
