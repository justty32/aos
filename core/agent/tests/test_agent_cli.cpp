/* 頂層 CLI（say／listen／state／talk）與 agent init 的回歸案例。
 * 由「修 bug 隊」在 2026-08-30 建立，對應 trial 的 L1-02／L1-06／L1-08／
 * L1-14／L1-31／L1-32／L2-01／L2-08／L2-09／L2-10／L2-12。 */

#include <aos/agent.hpp>
#include <aos/tool.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <filesystem>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <sys/file.h>
#include <unistd.h>
#include <vector>

extern "C" int aos_say_cli_main(int, char **);
extern "C" int aos_listen_cli_main(int, char **);
extern "C" int aos_talk_cli_main(int, char **);
extern "C" int aos_state_cli_main(int, char **);
extern "C" int aos_agent_cli_main(int, char **);

namespace {

using CliMain = int (*)(int, char **);

class TempWorld {
public:
    TempWorld() {
        const auto stamp =
            std::chrono::steady_clock::now().time_since_epoch().count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-cli-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
    }
    ~TempWorld() { std::filesystem::remove_all(path); }

    std::filesystem::path path;
};

class ScopedCurrentPath {
public:
    explicit ScopedCurrentPath(const std::filesystem::path &path)
        : original_(std::filesystem::current_path()) {
        std::filesystem::current_path(path);
    }
    ~ScopedCurrentPath() { std::filesystem::current_path(original_); }

private:
    std::filesystem::path original_;
};

class ScopedUnsetFolder {
public:
    ScopedUnsetFolder() {
        if (const char *value = std::getenv("AOS_FOLDER"))
            original_ = value;
        unsetenv("AOS_FOLDER");
    }
    ~ScopedUnsetFolder() {
        if (original_)
            setenv("AOS_FOLDER", original_->c_str(), 1);
        else
            unsetenv("AOS_FOLDER");
    }

private:
    std::optional<std::string> original_;
};

class ScopedFolder {
public:
    explicit ScopedFolder(const std::filesystem::path &path) {
        if (const char *value = std::getenv("AOS_FOLDER"))
            original_ = value;
        if (setenv("AOS_FOLDER", path.c_str(), 1) != 0) {
            throw std::runtime_error("無法設定測試用 AOS_FOLDER");
        }
    }
    ~ScopedFolder() {
        if (original_)
            setenv("AOS_FOLDER", original_->c_str(), 1);
        else
            unsetenv("AOS_FOLDER");
    }

private:
    std::optional<std::string> original_;
};

class ScopedCapture {
public:
    explicit ScopedCapture(int descriptor) : descriptor_(descriptor) {
        std::fflush(nullptr);
        saved_ = dup(descriptor_);
        file_ = std::tmpfile();
        if (saved_ < 0 || file_ == nullptr ||
            dup2(fileno(file_), descriptor_) < 0) {
            throw std::runtime_error("無法建立 CLI 輸出擷取檔");
        }
    }

    ~ScopedCapture() { restore(); }

    std::string finish() {
        std::fflush(nullptr);
        std::rewind(file_);
        std::string text;
        char buffer[4096];
        while (const std::size_t size =
                   std::fread(buffer, 1, sizeof(buffer), file_)) {
            text.append(buffer, size);
        }
        restore();
        return text;
    }

private:
    void restore() {
        if (saved_ >= 0) {
            dup2(saved_, descriptor_);
            close(saved_);
            saved_ = -1;
        }
        if (file_ != nullptr) {
            std::fclose(file_);
            file_ = nullptr;
        }
    }

    int descriptor_;
    int saved_ = -1;
    FILE *file_ = nullptr;
};

class ScopedInput {
public:
    explicit ScopedInput(std::string_view text) {
        saved_ = dup(STDIN_FILENO);
        file_ = std::tmpfile();
        if (saved_ < 0 || file_ == nullptr) {
            throw std::runtime_error("無法建立 CLI 輸入檔");
        }
        std::fwrite(text.data(), 1, text.size(), file_);
        std::rewind(file_);
        if (dup2(fileno(file_), STDIN_FILENO) < 0) {
            throw std::runtime_error("無法切換 CLI 輸入");
        }
        std::cin.clear();
    }

    ~ScopedInput() {
        dup2(saved_, STDIN_FILENO);
        close(saved_);
        std::fclose(file_);
        std::cin.clear();
    }

private:
    int saved_ = -1;
    FILE *file_ = nullptr;
};

class ScopedRunnerLock {
public:
    explicit ScopedRunnerLock(const std::filesystem::path &world) {
        descriptor_ =
            open((world / ".aos" / "run.lock").c_str(), O_CREAT | O_RDWR, 0644);
        if (descriptor_ < 0 || flock(descriptor_, LOCK_EX | LOCK_NB) != 0) {
            throw std::runtime_error("無法取得測試用 run.lock");
        }
    }
    ~ScopedRunnerLock() {
        flock(descriptor_, LOCK_UN);
        close(descriptor_);
    }

private:
    int descriptor_ = -1;
};

int run_cli(CliMain main, const std::vector<std::string> &arguments) {
    std::vector<std::string> storage = arguments;
    std::vector<char *> argv;
    argv.reserve(storage.size() + 1);
    for (std::string &argument : storage)
        argv.push_back(argument.data());
    argv.push_back(nullptr);
    return main(static_cast<int>(storage.size()), argv.data());
}

struct CliResult {
    int code = 0;
    std::string text;
};

CliResult capture_stdout(CliMain main,
                         const std::vector<std::string> &arguments) {
    ScopedCapture capture(STDOUT_FILENO);
    const int code = run_cli(main, arguments);
    return {code, capture.finish()};
}

CliResult capture_stderr(CliMain main,
                         const std::vector<std::string> &arguments) {
    ScopedCapture capture(STDERR_FILENO);
    const int code = run_cli(main, arguments);
    return {code, capture.finish()};
}

std::size_t message_count(const std::filesystem::path &world,
                          std::string_view name) {
    const std::filesystem::path say =
        world / ".aos" / "agents" / std::string(name) / "say";
    std::size_t count = 0;
    if (!std::filesystem::is_directory(say))
        return count;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            ++count;
        }
    }
    return count;
}

}  // namespace

TEST_CASE("say help prints usage without queuing a message") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");
    ScopedFolder folder(world.path);

    const CliResult result =
        capture_stdout(aos_say_cli_main, {"aos say", "--help"});
    CHECK(result.code == 0);
    CHECK(result.text.starts_with("usage: aos say"));
    CHECK(result.text.find("通訊錄") != std::string::npos);
    CHECK(message_count(world.path, "worker") == 0);
}

TEST_CASE("top-level and agent help options all return success") {
    for (const auto &[main, program] :
         std::vector<std::pair<CliMain, std::string>>{
             {aos_listen_cli_main, "aos listen"},
             {aos_state_cli_main, "aos state"},
             {aos_talk_cli_main, "aos talk"},
             {aos_agent_cli_main, "aos agent"}}) {
        const CliResult result = capture_stdout(main, {program, "--help"});
        CHECK(result.code == 0);
        CHECK(result.text.starts_with("usage: " + program));
    }
}

TEST_CASE("say to reports the real destination inbox") {
    TempWorld source;
    TempWorld target;
    aos::agent::initialize(source.path, "source");
    aos::agent::initialize(target.path, "target");
    aos::tool::add_contact(
        source.path,
        aos::tool::Contact{"target", target.path.string(), {}, ""});
    ScopedFolder folder(source.path);

    const CliResult result =
        capture_stdout(aos_say_cli_main, {"aos say", "--to", "target", "你好"});
    const std::filesystem::path inbox =
        target.path / ".aos" / "agents" / "target" / "say";
    CHECK(result.code == 0);
    CHECK(result.text.find(inbox.string()) != std::string::npos);
    CHECK(std::filesystem::is_directory(inbox));
    CHECK(message_count(target.path, "target") == 1);
}

TEST_CASE("say to distinguishes a missing contact folder") {
    TempWorld source;
    aos::agent::initialize(source.path, "source");
    const std::filesystem::path missing = source.path / "missing";
    aos::tool::add_contact(
        source.path, aos::tool::Contact{"ghost", missing.string(), {}, ""});
    ScopedFolder folder(source.path);

    const CliResult result =
        capture_stderr(aos_say_cli_main, {"aos say", "--to", "ghost", "你好"});
    CHECK(result.code == 1);
    CHECK(result.text.find("聯絡人 ghost") != std::string::npos);
    CHECK(result.text.find(aos::agent::absolute_folder(missing).string()) !=
          std::string::npos);
    CHECK(result.text.find("資料夾不存在") != std::string::npos);
}

TEST_CASE("state changes idle to pending when three messages are unread") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");
    for (const char *text : {"第一封", "第二封", "第三封"}) {
        aos::agent::say(world.path, "worker", text);
    }
    ScopedFolder folder(world.path);

    const CliResult result = capture_stdout(aos_state_cli_main, {"aos state"});
    CHECK(result.code == 0);
    CHECK(result.text.find("\"status\": \"idle\"") == std::string::npos);
    CHECK(result.text.find("\"status\": \"pending\"") != std::string::npos);
    CHECK(result.text.find("\"unread\": 3") != std::string::npos);
}

TEST_CASE("agent state keeps idle and reports zero unread") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");

    const CliResult result =
        capture_stdout(aos_agent_cli_main,
                       {"aos agent", "state", world.path.string(), "worker"});
    CHECK(result.code == 0);
    CHECK(result.text.find("\"status\": \"idle\"") != std::string::npos);
    CHECK(result.text.find("\"unread\": 0") != std::string::npos);
}

TEST_CASE("listen once prints unread message bodies without sender headers") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");
    aos::agent::say(world.path, "worker", "第一行\n第二行", "/sender");
    ScopedFolder folder(world.path);

    const CliResult result =
        capture_stdout(aos_listen_cli_main, {"aos listen", "--once"});
    CHECK(result.code == 0);
    CHECK(result.text.find("## 未讀 (1)") != std::string::npos);
    CHECK(result.text.find("- 第一行 第二行") != std::string::npos);
    CHECK(result.text.find("from:") == std::string::npos);
    CHECK(message_count(world.path, "worker") == 1);
}

TEST_CASE("talk detects runner lock before reading or queuing input") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");
    ScopedFolder folder(world.path);

    {
        ScopedInput input("不該寄出\n");
        const CliResult result =
            capture_stderr(aos_talk_cli_main, {"aos talk"});
        CHECK(result.code == 1);
        CHECK(result.text.find("沒有 aos run") != std::string::npos);
        CHECK(message_count(world.path, "worker") == 0);
    }
    {
        ScopedRunnerLock runner(world.path);
        ScopedInput input("");
        CHECK(run_cli(aos_talk_cli_main, {"aos talk"}) == 0);
    }
}

TEST_CASE("agent talk without a runner leaves the inbox untouched") {
    TempWorld world;
    aos::agent::initialize(world.path, "worker");
    ScopedInput input("不該寄出\n");

    const CliResult result =
        capture_stderr(aos_agent_cli_main,
                       {"aos agent", "talk", world.path.string(), "worker"});
    CHECK(result.code == 1);
    CHECK(result.text.find(aos::agent::absolute_folder(world.path).string()) !=
          std::string::npos);
    CHECK(message_count(world.path, "worker") == 0);
}

TEST_CASE("talk pi interface reports that the adapter is not built in") {
    const CliResult result =
        capture_stderr(aos_talk_cli_main, {"aos talk", "--interface", "pi"});
    CHECK(result.code == 2);
    CHECK(result.text.find("尚未內建") != std::string::npos);
}

TEST_CASE("state includes engine and model fields") {
    TempWorld world;
    aos::agent::Engine engine;
    engine.kind = "pi";
    engine.provider = "test-provider";
    engine.model = "test-model";
    aos::agent::initialize(world.path, "worker", "測試 agent", engine);
    ScopedFolder folder(world.path);

    const CliResult result = capture_stdout(aos_state_cli_main, {"aos state"});
    REQUIRE(result.code == 0);
    const nlohmann::json state = nlohmann::json::parse(result.text);
    CHECK(state["engine"] == "pi");
    CHECK(state["model"] == "test-model");
}

TEST_CASE(
    "agent init without folder creates a world in the current directory") {
    TempWorld sandbox;
    const std::filesystem::path parent = sandbox.path / "parent";
    const std::filesystem::path child = parent / "worker";
    std::filesystem::create_directories(parent / ".aos");
    std::filesystem::create_directories(child);
    ScopedUnsetFolder folder_environment;
    ScopedCurrentPath current_path(child);

    CHECK(run_cli(aos_agent_cli_main,
                  {"aos agent", "init", "--name", "worker"}) == 0);
    CHECK(std::filesystem::is_directory(child / ".aos" / "agents" / "worker"));
    CHECK_FALSE(std::filesystem::exists(parent / ".aos" / "agents" / "worker"));
}
