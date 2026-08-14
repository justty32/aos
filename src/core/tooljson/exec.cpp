// `_type: "exec"`：解析 `_extra`、把模型給的參數展開成 argv、真的去跑。
//
// 三件事分得很開：解析（ExecBody 的建構）在載入時做一次，展開（plan_exec）是
// 純函式，執行（capture）才碰 process。中間那層純函式是刻意的 —— 「怎麼展開」
// 是格式契約的一部分，測它不該需要真的跑一個程式。
#include "aos/tooljson/exec.hpp"

#include "tooljson/exec_body.hpp"

#include <nlohmann/json.hpp>

#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cstring>
#include <format>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <utility>
#include <vector>

namespace aos::tooljson {
namespace {

using nlohmann::json;

// Linux 的 MAX_ARG_STRLEN。單一 argv 項目超過就 E2BIG，
// 這是物理限制，不用在 spec 裡宣告就該擋。
constexpr std::size_t max_argument_bytes = 128U * 1024U;

Approver& approver() {
    static Approver current;
    return current;
}

struct Binding {
    int position = 0;
    std::string flag;
    bool separate = true;
    bool repeat = false;
};

struct Limit {
    std::optional<std::size_t> max_bytes;
    std::optional<double> minimum;
    std::optional<double> maximum;
};

class ExecBody : public Body {
public:
    std::vector<std::string> program;  // argv 的前綴，第一項是程式本身
    std::vector<std::pair<std::string, Binding>> order;
    std::map<std::string, Limit, std::less<>> limits;
    std::optional<std::string> stdin_param;
    std::string clip = "head";
    std::string stderr_mode = "merge";
    std::vector<int> ok_exit{0};
    std::filesystem::path resolved;  // 找得到才有；找不到是 nullopt 的意思
    std::string tool_name;

    [[nodiscard]] std::string run(const Spec& spec,
                                  std::string_view arguments_json) const override;
    [[nodiscard]] std::filesystem::path target() const override {
        return resolved;
    }
};

// ── 解析 ────────────────────────────────────────────────────────────────

[[nodiscard]] const Property* find_property(const Spec& spec,
                                            std::string_view name) {
    const auto match = std::ranges::find(spec.properties(), name, &Property::name);
    return match == spec.properties().end() ? nullptr : &*match;
}

// 照 execvp 的老規矩看斜線：不含 / 的留給 $PATH，其餘以這份 .json 為中心。
[[nodiscard]] std::filesystem::path locate(const std::string& program,
                                           const std::filesystem::path& directory) {
    if (program.contains('/')) {
        auto path = std::filesystem::absolute(directory / program);
        return ::access(path.c_str(), X_OK) == 0 ? path : std::filesystem::path{};
    }
    const char* raw_path = std::getenv("PATH");
    std::string_view search{raw_path == nullptr ? "/usr/bin:/bin" : raw_path};
    while (!search.empty()) {
        const auto colon = search.find(':');
        const auto piece = search.substr(0, colon);
        if (!piece.empty()) {
            std::filesystem::path candidate =
                std::filesystem::path{piece} / program;
            if (::access(candidate.c_str(), X_OK) == 0) {
                return candidate;
            }
        }
        if (colon == std::string_view::npos) {
            break;
        }
        search.remove_prefix(colon + 1);
    }
    return {};
}

}  // namespace

std::expected<std::shared_ptr<Body>, std::string> make_exec_body(
    const Spec& spec) {
    const json extra = json::parse(spec.extra_json(), nullptr, false);
    if (extra.is_discarded() || !extra.is_object()) {
        return std::unexpected{"_extra 不是 object"};
    }
    auto body = std::make_shared<ExecBody>();
    body->tool_name = spec.name();

    const auto fail = [](std::string message) {
        return std::unexpected<std::string>{std::move(message)};
    };

    // exec
    const auto exec = extra.find("exec");
    if (exec == extra.end() || !exec->is_array() || exec->empty()) {
        return fail("_extra.exec 要是非空的 array，第一項是程式本身");
    }
    for (const json& entry : *exec) {
        if (!entry.is_string() || entry.get<std::string>().empty()) {
            return fail("_extra.exec 裡每一項都要是非空字串");
        }
        body->program.push_back(entry.get<std::string>());
    }
    body->resolved = locate(body->program.front(), spec.directory());
    if (!body->resolved.empty()) {
        body->program.front() = body->resolved.string();
    }

    // argv 綁定
    if (const auto argv = extra.find("argv"); argv != extra.end()) {
        if (!argv->is_object()) {
            return fail("_extra.argv 要是 object，key 是參數名");
        }
        static constexpr std::array<std::string_view, 4> allowed{
            "position", "flag", "separate", "repeat"};
        for (const auto& [name, rule] : argv->items()) {
            if (!rule.is_object()) {
                return fail(std::format("_extra.argv[{}] 要是 object", name));
            }
            if (find_property(spec, name) == nullptr) {
                return fail(std::format(
                    "_extra.argv 綁了 {}，但 parameters 裡沒這個參數", name));
            }
            Binding binding;
            for (const auto& [key, value] : rule.items()) {
                if (std::ranges::find(allowed, key) == allowed.end()) {
                    return fail(std::format("_extra.argv[{}] 有不認得的鍵 {}",
                                            name, key));
                }
                if (key == "position") {
                    if (!value.is_number_integer()) {
                        return fail(std::format("{} 的 position 要是整數", name));
                    }
                    binding.position = value.get<int>();
                } else if (key == "flag") {
                    if (!value.is_string()) {
                        return fail(std::format("{} 的 flag 要是字串", name));
                    }
                    binding.flag = value.get<std::string>();
                } else if (key == "separate") {
                    if (!value.is_boolean()) {
                        return fail(std::format("{} 的 separate 要是 boolean", name));
                    }
                    binding.separate = value.get<bool>();
                } else {
                    if (!value.is_boolean()) {
                        return fail(std::format("{} 的 repeat 要是 boolean", name));
                    }
                    binding.repeat = value.get<bool>();
                }
            }
            body->order.emplace_back(name, binding);
        }
    }
    // 排序規則寫死才跨得了語言：position 小到大，同號的照參數名排。
    std::ranges::sort(body->order, [](const auto& left, const auto& right) {
        if (left.second.position != right.second.position) {
            return left.second.position < right.second.position;
        }
        return left.first < right.first;
    });

    // stdin
    if (const auto input = extra.find("stdin");
        input != extra.end() && !input->is_null()) {
        const auto param = input->find("param");
        if (!input->is_object() || param == input->end() || !param->is_string()) {
            return fail("_extra.stdin 要嘛是 null，要嘛是 {\"param\": \"...\"}");
        }
        if (input->size() != 1) {
            return fail("_extra.stdin 只能有 param");
        }
        auto name = param->get<std::string>();
        if (find_property(spec, name) == nullptr) {
            return fail(std::format(
                "_extra.stdin 指了 {}，但 parameters 裡沒這個參數", name));
        }
        body->stdin_param = std::move(name);
    }

    // stdout / stderr
    if (const auto out = extra.find("stdout"); out != extra.end()) {
        if (!out->is_object()) {
            return fail("_extra.stdout 要是 object");
        }
        if (const auto clip = out->find("clip"); clip != out->end()) {
            body->clip = clip->is_string() ? clip->get<std::string>() : "";
            if (body->clip != "head" && body->clip != "tail") {
                return fail("_extra.stdout.clip 只認得 \"head\" 或 \"tail\"");
            }
        }
    }
    if (const auto err = extra.find("stderr"); err != extra.end()) {
        if (!err->is_object()) {
            return fail("_extra.stderr 要是 object");
        }
        if (const auto mode = err->find("mode"); mode != err->end()) {
            body->stderr_mode = mode->is_string() ? mode->get<std::string>() : "";
            if (body->stderr_mode != "merge" && body->stderr_mode != "ignore" &&
                body->stderr_mode != "only") {
                return fail(
                    "_extra.stderr.mode 只認得 \"merge\"、\"ignore\"、\"only\"");
            }
        }
    }

    // ok_exit
    if (const auto codes = extra.find("ok_exit"); codes != extra.end()) {
        if (!codes->is_array()) {
            return fail("_extra.ok_exit 要是整數 array");
        }
        body->ok_exit.clear();
        for (const json& entry : *codes) {
            if (!entry.is_number_integer()) {
                return fail("_extra.ok_exit 裡要是整數");
            }
            body->ok_exit.push_back(entry.get<int>());
        }
    }

    // limits
    if (const auto limits = extra.find("limits"); limits != extra.end()) {
        if (!limits->is_object()) {
            return fail("_extra.limits 要是 object");
        }
        for (const auto& [name, rule] : limits->items()) {
            if (!rule.is_object()) {
                return fail(std::format("_extra.limits[{}] 要是 object", name));
            }
            if (find_property(spec, name) == nullptr) {
                return fail(std::format(
                    "_extra.limits 限制了 {}，但 parameters 裡沒這個參數", name));
            }
            Limit limit;
            if (const auto cap = rule.find("max_bytes");
                cap != rule.end() && cap->is_number_unsigned()) {
                limit.max_bytes = cap->get<std::size_t>();
            }
            if (const auto low = rule.find("min");
                low != rule.end() && low->is_number()) {
                limit.minimum = low->get<double>();
            }
            if (const auto high = rule.find("max");
                high != rule.end() && high->is_number()) {
                limit.maximum = high->get<double>();
            }
            body->limits.emplace(name, limit);
        }
    }

    return body;
}

namespace {

// ── 展開 ────────────────────────────────────────────────────────────────

// 值 → 命令列上的字串。照 JSON 的字面寫法，別的語言的實作才對得起來。
[[nodiscard]] std::string render(const json& value) {
    if (value.is_string()) {
        return value.get<std::string>();
    }
    if (value.is_boolean()) {
        return value.get<bool>() ? "true" : "false";
    }
    return value.dump();
}

// 小模型很常把 800 送成 "800"。schema 說要什麼就當場轉，轉不動回 false。
// 就地改而不是回 std::optional<json>，因為 nlohmann 的隱式轉換太多，
// 那個回傳型別會讓多載解析變成一團模糊。
[[nodiscard]] bool coerce(json& value, std::string_view want) {
    if (!value.is_string()) {
        return true;
    }
    const auto text = value.get<std::string>();
    try {
        if (want == "integer") {
            std::size_t used = 0;
            const long long parsed = std::stoll(text, &used);
            if (used != text.size()) {
                return false;
            }
            value = parsed;
            return true;
        }
        if (want == "number") {
            std::size_t used = 0;
            const double parsed = std::stod(text, &used);
            if (used != text.size()) {
                return false;
            }
            value = parsed;
            return true;
        }
    } catch (const std::exception&) {
        return false;  // stoll/stod 轉不動
    }
    if (want == "boolean") {
        if (text != "true" && text != "false") {
            return false;
        }
        value = (text == "true");
    }
    return true;
}

[[nodiscard]] std::optional<std::string> check_limit(const std::string& name,
                                                     const json& value,
                                                     const Limit& limit) {
    if (limit.max_bytes && value.is_string()) {
        const auto size = value.get<std::string>().size();
        if (size > *limit.max_bytes) {
            return std::format("Error: 參數 {} 有 {} 個位元組，超過上限 {}", name,
                               size, *limit.max_bytes);
        }
    }
    if (value.is_number() && !value.is_boolean()) {
        const double number = value.get<double>();
        if (limit.minimum && number < *limit.minimum) {
            return std::format("Error: 參數 {} 是 {}，低於最小值 {}", name, number,
                               *limit.minimum);
        }
        if (limit.maximum && number > *limit.maximum) {
            return std::format("Error: 參數 {} 是 {}，高於最大值 {}", name, number,
                               *limit.maximum);
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<std::string> expand_one(const std::string& name,
                                                    const json& value,
                                                    const Binding& binding,
                                                    bool boolean,
                                                    std::vector<std::string>& argv) {
    if (boolean && !binding.flag.empty()) {
        if (value.is_boolean() ? value.get<bool>() : true) {
            argv.push_back(binding.flag);  // 開關本身不帶值
        }
        return std::nullopt;  // 假值連旗標都不放
    }
    const auto text = render(value);
    if (text.size() > max_argument_bytes) {
        return std::format("Error: 參數 {} 太長了（{} 個位元組，命令列上限 {}）",
                           name, text.size(), max_argument_bytes);
    }
    if (binding.flag.empty()) {
        argv.push_back(text);
    } else if (binding.separate) {
        argv.push_back(binding.flag);
        argv.push_back(text);
    } else {
        argv.push_back(std::format("{}={}", binding.flag, text));
    }
    return std::nullopt;
}

}  // namespace

std::expected<ExecPlan, std::string> plan_exec(const Spec& spec,
                                               std::string_view arguments_json) {
    const auto* body = dynamic_cast<const ExecBody*>(spec.body());
    if (body == nullptr) {
        return std::unexpected{
            std::format("Error: 工具 {} 不是 exec 型的", spec.name())};
    }

    json given = json::parse(arguments_json, nullptr, false);
    if (given.is_discarded()) {
        // 小模型和被 max_tokens 切斷的一步都會吐出壞掉的 JSON。
        // 把原文回給模型，它才知道自己寫壞了什麼。
        return std::unexpected{std::format(
            "Error: 參數不是合法的 JSON：{}", arguments_json.substr(0, 200))};
    }
    if (!given.is_object()) {
        return std::unexpected{"Error: 參數要是一個 JSON object"};
    }

    // 型別轉換 + 丟掉明確的 null（那等於「這個我不給」）。
    std::map<std::string, json, std::less<>> args;
    std::vector<std::string> wrong_type;
    for (const auto& [name, value] : given.items()) {
        if (value.is_null()) {
            continue;
        }
        const Property* property = find_property(spec, name);
        json converted = value;
        if (!coerce(converted,
                    property == nullptr ? std::string_view{} : property->type)) {
            wrong_type.push_back(name);
            continue;
        }
        args.emplace(name, std::move(converted));
    }
    if (!wrong_type.empty()) {
        std::string names;
        for (const std::string& name : wrong_type) {
            names += names.empty() ? name : "、" + name;
        }
        return std::unexpected{std::format("Error: 參數 {} 的型別不對", names)};
    }

    // 少了必填的。
    std::string missing;
    for (const std::string& name : spec.required()) {
        if (!args.contains(name)) {
            missing += missing.empty() ? name : "、" + name;
        }
    }
    if (!missing.empty()) {
        return std::unexpected{std::format("Error: 少了必填參數 {}", missing)};
    }

    // 多給了不認得的。安靜丟掉模型明明有給的東西，是最難查的那種錯。
    std::string unknown;
    for (const auto& [name, ignored] : args) {
        if (find_property(spec, name) == nullptr) {
            unknown += unknown.empty() ? name : "、" + name;
        }
    }
    if (!unknown.empty()) {
        std::string accepted;
        for (const Property& property : spec.properties()) {
            accepted += accepted.empty() ? property.name : "、" + property.name;
        }
        return std::unexpected{
            std::format("Error: 不認得的參數 {}。這個工具收的是：{}", unknown,
                        accepted.empty() ? "（沒有參數）" : accepted)};
    }

    for (const auto& [name, limit] : body->limits) {
        const auto found = args.find(name);
        if (found == args.end()) {
            continue;
        }
        if (auto bad = check_limit(name, found->second, limit)) {
            return std::unexpected{*bad};
        }
    }

    ExecPlan plan;
    plan.argv = body->program;
    for (const auto& [name, binding] : body->order) {
        if (body->stdin_param == name) {
            continue;  // 走 stdin，不上命令列
        }
        const auto found = args.find(name);
        if (found == args.end()) {
            continue;  // 缺席的參數整條跳過，不產生空字串也不產生 --no-xxx
        }
        const Property* property = find_property(spec, name);
        const bool boolean = property != nullptr && property->type == "boolean";

        if (found->second.is_array() && !binding.repeat) {
            return std::unexpected{
                std::format("Error: 參數 {} 不接受一串值", name)};
        }
        if (binding.repeat && found->second.is_array()) {
            for (const json& item : found->second) {
                if (auto bad = expand_one(name, item, binding, boolean, plan.argv)) {
                    return std::unexpected{*bad};
                }
            }
        } else if (auto bad = expand_one(name, found->second, binding, boolean,
                                         plan.argv)) {
            return std::unexpected{*bad};
        }
    }

    if (body->stdin_param) {
        if (const auto found = args.find(*body->stdin_param); found != args.end()) {
            plan.stdin_text = render(found->second);
        }
    }
    return plan;
}

// ── 收尾 ────────────────────────────────────────────────────────────────

std::string decode_output(std::string_view raw) {
    if (raw.empty()) {
        return {};
    }
    if (raw.contains('\0')) {
        return std::format("（二進位輸出，{} 個位元組，不顯示）", raw.size());
    }
    return std::string{raw};
}

std::string clip_output(std::string text, std::string_view where,
                        std::size_t limit) {
    if (text.size() <= limit) {
        return text;
    }
    const std::size_t cut = text.size() - limit;
    if (where == "tail") {
        return std::format("…（前面省略 {} 個字元）\n{}", cut,
                           text.substr(text.size() - limit));
    }
    return std::format("{}\n…（後面還有 {} 個字元）", text.substr(0, limit), cut);
}

void set_approver(Approver value) { approver() = std::move(value); }

// ── 執行 ────────────────────────────────────────────────────────────────

namespace {

struct Capture {
    int exit_code = 0;
    std::string output;
    std::string failure;  // 非空代表連跑都沒跑起來
};

void close_if_open(int& descriptor) {
    if (descriptor >= 0) {
        ::close(descriptor);
        descriptor = -1;
    }
}

// fork + execvp，不經過 shell。同時讀 stdout、寫 stdin，
// 因為只做一邊會在對方的管線塞滿時互相等到天荒地老。
[[nodiscard]] Capture capture_process(const std::vector<std::string>& argv,
                                      const std::optional<std::string>& input,
                                      const std::string& stderr_mode) {
    Capture result;

    std::array<int, 2> out_pipe{-1, -1};
    std::array<int, 2> in_pipe{-1, -1};
    if (::pipe(out_pipe.data()) != 0) {
        result.failure = "開不了管線";
        return result;
    }
    if (input && ::pipe(in_pipe.data()) != 0) {
        ::close(out_pipe[0]);
        ::close(out_pipe[1]);
        result.failure = "開不了管線";
        return result;
    }

    const pid_t child = ::fork();
    if (child < 0) {
        close_if_open(out_pipe[0]);
        close_if_open(out_pipe[1]);
        close_if_open(in_pipe[0]);
        close_if_open(in_pipe[1]);
        result.failure = "fork 失敗";
        return result;
    }

    if (child == 0) {
        // 子行程。這裡只能用 async-signal-safe 的東西，所以不配置記憶體、
        // 不丟例外，出錯就直接 _exit。
        const int null_fd = ::open("/dev/null", O_RDWR);
        if (stderr_mode == "only") {
            ::dup2(out_pipe[1], STDERR_FILENO);
            ::dup2(null_fd, STDOUT_FILENO);
        } else {
            ::dup2(out_pipe[1], STDOUT_FILENO);
            // merge 是**真的重導向**，兩條管子共用一個，時序才對，
            // 不是事後把兩個字串接起來。
            ::dup2(stderr_mode == "ignore" ? null_fd : out_pipe[1], STDERR_FILENO);
        }
        if (input) {
            ::dup2(in_pipe[0], STDIN_FILENO);
            ::close(in_pipe[1]);
        } else {
            ::dup2(null_fd, STDIN_FILENO);
        }
        ::close(out_pipe[0]);
        ::close(out_pipe[1]);
        if (null_fd >= 0) {
            ::close(null_fd);
        }

        std::vector<char*> raw;
        raw.reserve(argv.size() + 1);
        for (const std::string& one : argv) {
            raw.push_back(const_cast<char*>(one.c_str()));
        }
        raw.push_back(nullptr);
        ::execvp(raw[0], raw.data());
        ::_exit(127);  // execvp 回來就是失敗
    }

    // 父行程。
    close_if_open(out_pipe[1]);
    close_if_open(in_pipe[0]);

    std::string_view pending = input ? std::string_view{*input} : std::string_view{};
    if (in_pipe[1] >= 0) {
        ::fcntl(in_pipe[1], F_SETFL, O_NONBLOCK);
    }

    while (out_pipe[0] >= 0) {
        std::array<::pollfd, 2> fds{};
        int count = 0;
        fds[count++] = {.fd = out_pipe[0], .events = POLLIN, .revents = 0};
        if (in_pipe[1] >= 0) {
            fds[count++] = {.fd = in_pipe[1], .events = POLLOUT, .revents = 0};
        }
        if (::poll(fds.data(), static_cast<::nfds_t>(count), -1) < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }

        if ((fds[0].revents & (POLLIN | POLLHUP)) != 0) {
            std::array<char, 64U * 1024U> buffer{};
            const ssize_t read_bytes =
                ::read(out_pipe[0], buffer.data(), buffer.size());
            if (read_bytes > 0) {
                result.output.append(buffer.data(),
                                     static_cast<std::size_t>(read_bytes));
            } else if (read_bytes == 0 || errno != EINTR) {
                close_if_open(out_pipe[0]);
            }
        }

        if (count > 1 && (fds[1].revents & (POLLOUT | POLLERR | POLLHUP)) != 0) {
            if (pending.empty() || (fds[1].revents & (POLLERR | POLLHUP)) != 0) {
                close_if_open(in_pipe[1]);  // 餵完了就關，子行程才讀得到 EOF
            } else {
                const ssize_t written =
                    ::write(in_pipe[1], pending.data(), pending.size());
                if (written > 0) {
                    pending.remove_prefix(static_cast<std::size_t>(written));
                } else if (errno != EINTR && errno != EAGAIN) {
                    close_if_open(in_pipe[1]);
                }
            }
        }
    }

    close_if_open(out_pipe[0]);
    close_if_open(in_pipe[1]);

    int status = 0;
    while (::waitpid(child, &status, 0) < 0 && errno == EINTR) {
    }
    if (WIFEXITED(status)) {
        result.exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        result.exit_code = 128 + WTERMSIG(status);
    }
    return result;
}

}  // namespace

std::string ExecBody::run(const Spec& spec,
                          std::string_view arguments_json) const {
    // 這裡的每一條錯誤都是**要回給模型的那句話**，不是給人看的日誌。
    // 模型讀得懂「少了必填參數 path」，然後自己補上再叫一次。
    auto plan = plan_exec(spec, arguments_json);
    if (!plan) {
        return plan.error();
    }
    if (resolved.empty()) {
        // 分開講：找不到檔案跟跑起來失敗，模型該做的事不一樣。
        return std::format("Error: 找不到工具 {} 要跑的執行檔 {}", tool_name,
                           program.front());
    }
    if (const Approver& gate = approver(); gate && !gate(tool_name, plan->argv)) {
        return "Error: 使用者沒有放行這次呼叫";
    }

    const Capture captured =
        capture_process(plan->argv, plan->stdin_text, stderr_mode);
    if (!captured.failure.empty()) {
        return std::format("Error: 跑不起來 {}：{}", tool_name, captured.failure);
    }

    auto text = clip_output(decode_output(captured.output), clip);
    if (std::ranges::find(ok_exit, captured.exit_code) == ok_exit.end()) {
        // grep 沒找到是 exit 1，那不是失敗 —— 所以只有 ok_exit 之外的才標。
        return std::format("exit {}\n{}", captured.exit_code, text);
    }
    return text;
}

}  // namespace aos::tooljson
