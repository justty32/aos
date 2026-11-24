// ls.cpp：【ls】定位指定或表上唯一的 llm kernel、讀含 backend 的能力包窗並印表，最後一行印整台的格數與信數（說明見 ls.hpp）。
#include "ls/ls.hpp"
#include "send/send.hpp"

#include "aos/util/files.hpp"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <vector>

namespace aos::llm {

namespace {

Json table_rows(const std::string& daemon) {
    auto state = aos::read_json(aos::join(daemon, "procs_state.json"));
    if (!state || !state->is_object() || !state->contains("procs") || !(*state)["procs"].is_object()) {
        throw Error{code::LlmKernelMissing, "cannot read the daemon table at " + daemon + "; use --kernel PATH"};
    }
    Json rows = (*state)["procs"];
    if (!rows.contains("$ref")) {
        return rows;
    }
    if (!rows["$ref"].is_array()) {
        throw Error{code::LlmKernelMissing, "invalid daemon table parts at " + daemon + "; use --kernel PATH"};
    }
    Json joined = Json::object();
    for (const auto& ref : rows["$ref"]) {
        if (!ref.is_string()) {
            throw Error{code::LlmKernelMissing, "invalid daemon table part at " + daemon + "; use --kernel PATH"};
        }
        auto part = aos::read_json(aos::join(daemon, ref.get<std::string>()));
        if (!part || !part->is_object()) {
            throw Error{code::LlmKernelMissing, "cannot read daemon table part " + ref.get<std::string>() + "; use --kernel PATH"};
        }
        joined.update(*part);
    }
    return joined;
}

// 只認 ls 會讀的公開產物，不從啟動方式或定義名字猜 kernel 身分。
bool kernel_stack(const Json& row, const std::string& daemon) {
    if (!row.is_object()) {
        return false;
    }
    auto stack = row.find("stack");
    if (stack == row.end() || !stack->is_string() || stack->get_ref<const std::string&>().empty()) {
        return false;
    }
    std::filesystem::path path = aos::abspath(aos::join(daemon, stack->get<std::string>()));
    std::error_code ec;
    if (!std::filesystem::is_regular_file(path / "endpoints.json", ec)) {
        return false;
    }
    return std::filesystem::is_directory(path / "requests", ec);
}

Mailbox stack_mailbox(const std::string& stack, const std::string& base) {
    std::string path = aos::abspath(aos::join(base, stack));
    std::error_code ec;
    if (!std::filesystem::is_directory(path, ec)) {
        throw Error{code::LlmKernelMissing, "llm kernel stack is not a folder: " + path + "; use --kernel NAME or --kernel PATH"};
    }
    return Mailbox{aos::join(path, "requests")};
}

}  // namespace

Mailbox ls_kernel(const std::optional<std::string>& selection) {
    const char* raw_daemon = std::getenv("AOS_DAEMON");
    std::string daemon = raw_daemon && *raw_daemon ? aos::abspath(raw_daemon) : "";
    if (selection && selection->empty()) {
        throw Error{code::ArgumentsBad, "--kernel must be a row name or stack path"};
    }
    if (selection && selection->find('/') != std::string::npos) {
        return stack_mailbox(*selection, ".");
    }
    const char* env = std::getenv("AOS_LLM_KERNEL");
    if (!selection && env && *env) {
        return kernel();   // 環境變數的相對路徑規則照舊；send／ask／regret 不改。
    }
    if (daemon.empty()) {
        throw Error{code::LlmKernelMissing, "AOS_DAEMON is not set for a kernel table lookup; use --kernel PATH or set AOS_LLM_KERNEL"};
    }
    std::error_code ec;
    auto canonical = std::filesystem::canonical(daemon, ec);
    if (!ec) {
        daemon = canonical.string();   // 同 daemon_ctl：表上的相對路徑以 daemon stack 真實位置為準。
    }
    Json rows = table_rows(daemon);
    std::vector<std::string> candidates;
    if (selection) {
        if (!rows.contains(*selection) || !rows[*selection].is_object()) {
            throw Error{code::LlmKernelMissing, "no kernel row named " + *selection + "; use --kernel NAME or --kernel PATH"};
        }
        candidates.push_back(*selection);
    } else {
        for (auto& [name, row] : rows.items()) {
            if (kernel_stack(row, daemon)) {
                candidates.push_back(name);
            }
        }
    }
    if (candidates.empty()) {
        throw Error{code::LlmKernelMissing, "no llm kernel rows found; use --kernel NAME or --kernel PATH"};
    }
    if (candidates.size() > 1) {
        std::string names;
        for (const auto& name : candidates) {
            names += (names.empty() ? "" : ", ") + name;
        }
        throw Error{code::LlmKernelMissing, "several llm kernel rows found: " + names + "; choose --kernel NAME or --kernel PATH"};
    }
    const Json& row = rows[candidates[0]];
    auto stack = row.find("stack");
    if (stack == row.end() || !stack->is_string() || stack->get_ref<const std::string&>().empty()) {
        throw Error{code::LlmKernelMissing, "kernel row " + candidates[0] + " has no stack; use --kernel PATH"};
    }
    return stack_mailbox(stack->get<std::string>(), daemon);
}

Json ls_window(const Mailbox& mb) {
    std::string path = aos::join(aos::dirname(mb.root), "endpoints.json");
    std::optional<Json> w;
    try {
        w = aos::read_json(path);
    } catch (const std::exception&) {
        w = std::nullopt;
    }
    if (!w || !w->is_object()) {
        throw Error{code::EndpointsMissing, path + " is missing or unreadable (has the llm kernel run yet?)"};
    }
    return *w;
}

// 值原樣印：字串去引號、其他（數字等）用 JSON 寫法；缺＝-。
static std::string cell(const Json& pack, const char* k) {
    if (!pack.contains(k)) {
        return "-";
    }
    const Json& v = pack.at(k);
    return v.is_string() ? v.get<std::string>() : v.dump();
}

// 信箱一格裡的信（每封一個資料夾，. 開頭的是還在建的）；夾不在＝0。
static long letters_in(const std::string& folder) {
    long count = 0;
    std::error_code ec;
    for (std::filesystem::directory_iterator it(folder, ec), end; !ec && it != end; it.increment(ec)) {
        std::string name = it->path().filename().string();
        std::error_code dir_ec;
        if (!name.empty() && name[0] != '.' && it->is_directory(dir_ec)) {
            ++count;
        }
    }
    return count;
}

Json ls_whole(const Mailbox& mb) {
    Json whole = Json::object();
    std::optional<Json> limits;
    try {
        limits = aos::read_json(aos::join(aos::dirname(mb.root), "slots.json"));
    } catch (const std::exception&) {
        limits = std::nullopt;
    }
    if (limits && limits->is_object()) {
        if (limits->contains("slots")) {
            whole["slots"] = (*limits)["slots"];
        }
        if (limits->contains("reserved") && (*limits)["reserved"].is_object() && (*limits)["reserved"].contains("high")) {
            whole["reserved_high"] = (*limits)["reserved"]["high"];
        }
    }
    whole["in_flight"] = letters_in(aos::join(mb.root, "cur"));
    whole["queued"] = letters_in(aos::join(mb.root, "new"));
    return whole;
}

void ls_print(const Json& window, bool json, const Json& whole) {
    if (json) {
        std::printf("%s\n", aos::dumps(window).c_str());
        std::fflush(stdout);
        return;
    }
    for (auto it = window.begin(); it != window.end(); ++it) {
        const Json& p = it.value();
        if (p.is_object() && p.contains("error")) {
            std::printf("%s\terror:\t%s\n", it.key().c_str(), cell(p, "error").c_str());
            continue;
        }
        std::printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\n", it.key().c_str(), cell(p, "speed").c_str(), cell(p, "cost").c_str(),
                    cell(p, "context").c_str(), cell(p, "slots").c_str(), cell(p, "backend").c_str(), cell(p, "summary").c_str());
    }
    std::printf("# kernel: slots %s, reserved for high %s, in flight %s, queued %s\n", cell(whole, "slots").c_str(),
                cell(whole, "reserved_high").c_str(), cell(whole, "in_flight").c_str(), cell(whole, "queued").c_str());
    std::fflush(stdout);
}

}  // namespace aos::llm
