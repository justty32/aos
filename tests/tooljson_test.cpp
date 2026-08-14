// tooljson 的離線檢查：載入期驗證、argv 展開、輸出收尾。
//
// 「怎麼展開」是格式契約的一部分（別的語言的實作要展開成一模一樣的東西），
// 所以它是純函式，測它不需要真的跑一個程式。只有最後兩項會開子行程，
// 而且跑的是 /bin/cat 與 /bin/sh 這種一定在的東西，不連任何網路。
#include "check.hpp"

#include "aos/tooljson/exec.hpp"
#include "aos/tooljson/spec.hpp"

#include <unistd.h>

#include <cstdlib>
#include <filesystem>
#include <format>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

using namespace aos::tooljson;

namespace {

// 每個檢查各自寫一份 .json 到暫存資料夾。相對路徑要以 .json 為中心解析，
// 所以檔案真的得存在。
class Scratch {
public:
    Scratch()
        : directory_{std::filesystem::temp_directory_path() /
                     std::format("aos-tooljson-{}", ::getpid())} {
        std::filesystem::create_directories(directory_);
    }
    ~Scratch() {
        std::error_code ignored;
        std::filesystem::remove_all(directory_, ignored);
    }
    Scratch(const Scratch&) = delete;
    Scratch& operator=(const Scratch&) = delete;

    [[nodiscard]] std::filesystem::path write(std::string_view name,
                                              std::string_view content) const {
        const auto path = directory_ / name;
        std::ofstream file{path};
        file << content;
        return path;
    }

private:
    std::filesystem::path directory_;
};

// 一份最小可用的 spec，參數綁定隨呼叫端替換。
[[nodiscard]] std::string spec_text(std::string_view properties,
                                    std::string_view required,
                                    std::string_view extra_tail) {
    return std::format(R"({{
      "type": "function",
      "function": {{
        "name": "demo",
        "description": "示範",
        "parameters": {{"type": "object",
                        "properties": {{{}}},
                        "required": [{}]}}
      }},
      "_extra": {{"_version": "0.1.0", "_type": "exec", "exec": ["cat"]{}}}
    }})",
                       properties, required, extra_tail);
}

void test_missing_extra_is_rejected() {
    const Scratch scratch;
    const auto path = scratch.write("bare.json", R"({
      "type": "function",
      "function": {"name": "x", "parameters": {"type": "object"}}
    })");
    // 沒有 _extra 的話，這份 JSON 只是 schema，跑不起來。
    AOS_CHECK(!load(path).has_value());
}

void test_unknown_version_is_refused_not_guessed() {
    const Scratch scratch;
    const auto path = scratch.write("old.json", R"({
      "type": "function",
      "function": {"name": "x", "parameters": {"type": "object"}},
      "_extra": {"_version": "0.9.0", "_type": "exec", "exec": ["cat"]}
    })");
    AOS_CHECK(!load(path).has_value());
}

void test_unknown_type_names_what_is_registered() {
    const Scratch scratch;
    const auto path = scratch.write("weird.json", R"({
      "type": "function",
      "function": {"name": "x", "parameters": {"type": "object"}},
      "_extra": {"_version": "0.1.0", "_type": "telepathy"}
    })");
    const auto loaded = load(path);
    AOS_CHECK(!loaded.has_value());
    AOS_CHECK(loaded.error().contains("exec"));  // 錯誤訊息要說得出認得哪些

    const auto types = registered_types();
    AOS_CHECK(types.size() == 1 && types[0] == "exec");
}

void test_argv_binding_must_name_a_real_parameter() {
    const Scratch scratch;
    const auto path = scratch.write(
        "typo.json",
        spec_text(R"("path": {"type": "string"})", R"("path")",
                  R"(, "argv": {"paht": {"position": 1}})"));
    // 綁到一個不存在的參數 = 打錯字。載入時就該講，不是等第一次呼叫。
    AOS_CHECK(!load(path).has_value());
}

void test_required_must_exist_in_properties() {
    const Scratch scratch;
    const auto path = scratch.write(
        "req.json", spec_text(R"("a": {"type": "string"})", R"("b")", ""));
    AOS_CHECK(!load(path).has_value());
}

void test_duplicate_names_in_one_file_are_an_error() {
    const Scratch scratch;
    const auto one = spec_text("", "", "");
    const auto path = scratch.write("pair.json", std::format("[{},{}]", one, one));
    AOS_CHECK(!load_all(path).has_value());
}

void test_argv_expansion_follows_the_declared_types() {
    const Scratch scratch;
    const auto path = scratch.write(
        "resize.json",
        spec_text(R"("path": {"type": "string"},
                    "width": {"type": "integer"},
                    "force": {"type": "boolean"})",
                  R"("path")",
                  R"(, "argv": {"path": {"position": 1},
                                "width": {"position": 2, "flag": "-w"},
                                "force": {"position": 3, "flag": "--force"}})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    // 沒 flag → 位置參數；有 flag → 旗標加值；boolean 加 flag → 開關。
    // 順序完全照 position 小到大（同號才照參數名排），因為那是格式契約的一部分：
    // **沒寫 position 就是 0**，會排到所有有寫的前面。
    const auto plan = plan_exec(
        *spec, R"({"path": "a.png", "width": 800, "force": true})");
    AOS_CHECK(plan.has_value());
    const std::vector<std::string> expected{"a.png", "-w", "800", "--force"};
    AOS_CHECK(std::vector<std::string>(plan->argv.begin() + 1,
                                       plan->argv.end()) == expected);

    // 假值連旗標都不放，不會產生 --no-force 這種東西。
    const auto off = plan_exec(*spec, R"({"path": "a.png", "force": false})");
    AOS_CHECK(off.has_value());
    AOS_CHECK(off->argv.size() == 2);

    // 缺席的參數整條跳過，不產生空字串。
    const auto sparse = plan_exec(*spec, R"({"path": "a.png"})");
    AOS_CHECK(sparse.has_value() && sparse->argv.size() == 2);
}

void test_string_numbers_are_coerced_because_small_models_send_them() {
    const Scratch scratch;
    const auto path = scratch.write(
        "n.json", spec_text(R"("width": {"type": "integer"})", "",
                            R"(, "argv": {"width": {"position": 1}})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    const auto plan = plan_exec(*spec, R"({"width": "800"})");
    AOS_CHECK(plan.has_value());
    AOS_CHECK(plan->argv.back() == "800");

    // 但真的轉不過去就要講，不能安靜地送一個 "八百" 出去。
    AOS_CHECK(!plan_exec(*spec, R"({"width": "八百"})").has_value());
}

void test_missing_and_unknown_arguments_are_told_to_the_model() {
    const Scratch scratch;
    const auto path = scratch.write(
        "r.json", spec_text(R"("path": {"type": "string"})", R"("path")", ""));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    const auto missing = plan_exec(*spec, "{}");
    AOS_CHECK(!missing.has_value() && missing.error().contains("path"));

    // 安靜丟掉模型明明有給的東西，是最難查的那種錯。
    const auto unknown = plan_exec(*spec, R"({"path": "a", "colour": "red"})");
    AOS_CHECK(!unknown.has_value() && unknown.error().contains("colour"));

    // 明確的 null 等於「這個我不給」，跟沒送是同一件事。
    const auto explicit_null = plan_exec(*spec, R"({"path": null})");
    AOS_CHECK(!explicit_null.has_value());
}

void test_broken_json_from_the_model_is_handed_back_verbatim() {
    const Scratch scratch;
    const auto path = scratch.write("b.json", spec_text("", "", ""));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    // 被 max_tokens 切斷的一步就長這樣。原文要留著，模型才知道自己寫壞了什麼。
    const auto plan = plan_exec(*spec, R"({"path": "a.pn)");
    AOS_CHECK(!plan.has_value());
    AOS_CHECK(plan.error().contains("a.pn"));
}

void test_limits_are_checked_before_running() {
    const Scratch scratch;
    const auto path = scratch.write(
        "l.json", spec_text(R"("text": {"type": "string"})", "",
                            R"(, "argv": {"text": {"position": 1}},
                               "limits": {"text": {"max_bytes": 4}})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    AOS_CHECK(plan_exec(*spec, R"({"text": "abcd"})").has_value());
    const auto over = plan_exec(*spec, R"({"text": "abcde"})");
    AOS_CHECK(!over.has_value() && over.error().contains("4"));
}

void test_stdin_parameter_leaves_the_command_line() {
    const Scratch scratch;
    const auto path = scratch.write(
        "s.json", spec_text(R"("text": {"type": "string"})", R"("text")",
                            R"(, "argv": {"text": {"position": 1}},
                               "stdin": {"param": "text"})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    const auto plan = plan_exec(*spec, R"({"text": "餵給 stdin"})");
    AOS_CHECK(plan.has_value());
    AOS_CHECK(plan->argv.size() == 1);  // 沒有上命令列
    AOS_CHECK(plan->stdin_text == "餵給 stdin");
}

void test_output_decoding_and_clipping() {
    AOS_CHECK(decode_output("hi") == "hi");
    // 含 NUL 的輸出不該變成幾萬個替代字元灌爆 context。
    AOS_CHECK(decode_output(std::string_view{"a\0b", 3}).contains("二進位"));

    // 截掉多少要寫在截斷處，不然沒人知道自己看的是不是全部。
    const auto head = clip_output("abcdef", "head", 3);
    AOS_CHECK(head.starts_with("abc") && head.contains("3"));
    const auto tail = clip_output("abcdef", "tail", 3);
    AOS_CHECK(tail.ends_with("def") && tail.contains("3"));
}

void test_a_real_subprocess_round_trips_stdin_to_stdout() {
    const Scratch scratch;
    const auto path = scratch.write(
        "cat.json", spec_text(R"("text": {"type": "string"})", R"("text")",
                              R"(, "stdin": {"param": "text"})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    // 真的 fork + execvp 一次 /bin/cat。這是唯一能證明 stdin 那條管線
    // 沒有互相等死的檢查。
    AOS_CHECK(spec->run(R"({"text": "來回一趟"})") == "來回一趟");
}

void test_shell_metacharacters_stay_as_characters() {
    const Scratch scratch;
    const auto path = scratch.write(
        "echo.json", std::format(R"({{
      "type": "function",
      "function": {{"name": "e",
                    "parameters": {{"type": "object",
                                    "properties": {{"word": {{"type": "string"}}}},
                                    "required": ["word"]}}}},
      "_extra": {{"_version": "0.1.0", "_type": "exec", "exec": ["echo"],
                  "argv": {{"word": {{"position": 1}}}}}}
    }})"));
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());

    // 不經過 shell，所以 $(...) 只是字元，不會被重新解析執行。
    // 自訂分隔符：內容裡有 )" 這兩個字元，用預設的分隔符會提早結束。
    const auto output = spec->run(R"json({"word": "$(id -u)"})json");
    AOS_CHECK(output == "$(id -u)\n");
}

void test_exit_code_outside_ok_exit_is_labelled() {
    const Scratch scratch;
    const auto path = scratch.write("false.json", R"({
      "type": "function",
      "function": {"name": "f", "parameters": {"type": "object"}},
      "_extra": {"_version": "0.1.0", "_type": "exec", "exec": ["false"]}
    })");
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());
    AOS_CHECK(spec->run("{}").starts_with("exit 1"));

    // 宣告 1 也算成功之後就不再標 —— grep 沒找到是 exit 1，那不是失敗。
    const auto tolerant = scratch.write("false2.json", R"({
      "type": "function",
      "function": {"name": "f", "parameters": {"type": "object"}},
      "_extra": {"_version": "0.1.0", "_type": "exec", "exec": ["false"],
                 "ok_exit": [0, 1]}
    })");
    const auto lenient = load(tolerant);
    AOS_CHECK(lenient.has_value());
    AOS_CHECK(!lenient->run("{}").starts_with("exit"));
}

void test_missing_executable_is_reported_not_crashed() {
    const Scratch scratch;
    const auto path = scratch.write("nope.json", R"({
      "type": "function",
      "function": {"name": "n", "parameters": {"type": "object"}},
      "_extra": {"_version": "0.1.0", "_type": "exec",
                 "exec": ["aos-definitely-not-a-real-program"]}
    })");
    const auto spec = load(path);
    AOS_CHECK(spec.has_value());  // 載入得起來：檔案不見是執行期的事
    AOS_CHECK(spec->run("{}").contains("找不到"));
}

void test_load_tools_produces_a_matched_toolset() {
    const Scratch scratch;
    const auto path = scratch.write(
        "cat.json", spec_text(R"("text": {"type": "string"})", R"("text")",
                              R"(, "stdin": {"param": "text"})"));
    const std::vector<std::filesystem::path> sources{path};
    const auto tools = load_tools(sources);
    AOS_CHECK(tools.has_value());

    AOS_CHECK(tools->schemas.size() == 1);
    AOS_CHECK(tools->schemas[0].name == "demo");
    // 送給模型的 schema 一定要剝掉 _extra。
    AOS_CHECK(!tools->schemas[0].json.contains("_extra"));

    // schema 與 dispatch 名稱配得起來，而且叫得動。
    const auto* function = tools->find("demo");
    AOS_CHECK(function != nullptr);
    AOS_CHECK((*function)(R"({"text": "嗨"})") == "嗨");
}

}  // namespace

int main() {
    test_missing_extra_is_rejected();
    test_unknown_version_is_refused_not_guessed();
    test_unknown_type_names_what_is_registered();
    test_argv_binding_must_name_a_real_parameter();
    test_required_must_exist_in_properties();
    test_duplicate_names_in_one_file_are_an_error();
    test_argv_expansion_follows_the_declared_types();
    test_string_numbers_are_coerced_because_small_models_send_them();
    test_missing_and_unknown_arguments_are_told_to_the_model();
    test_broken_json_from_the_model_is_handed_back_verbatim();
    test_limits_are_checked_before_running();
    test_stdin_parameter_leaves_the_command_line();
    test_output_decoding_and_clipping();
    test_a_real_subprocess_round_trips_stdin_to_stdout();
    test_shell_metacharacters_stay_as_characters();
    test_exit_code_outside_ok_exit_is_labelled();
    test_missing_executable_is_reported_not_crashed();
    test_load_tools_produces_a_matched_toolset();
    return aos::testing::report();
}
