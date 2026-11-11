// help.cpp：【help】aos-json 各子命令的英文說明與旗標解析。
#include "help/help.hpp"

namespace aos::json {

namespace {

const std::map<std::string, std::string> SUB_USAGE = {
    {"get", "aos-json get [--follow] [--resolve] [--str] FILE#/POINTER"},
    {"peek", "aos-json peek [--follow] [--depth N] FILE#/POINTER"},
    {"where", "aos-json where FILE#/POINTER"},
    {"set", "aos-json set [--check] [--follow] [--parents] [--str] FILE#/POINTER [VALUE]"},
    {"batch", "aos-json batch [--check] [--follow] [--parents] FILE"},
    {"del", "aos-json del [--follow] FILE#/POINTER"},
    {"append", "aos-json append [--check] [--follow] [--str] FILE#/POINTER [VALUE]"},
    {"merge", "aos-json merge [--check] [--follow] FILE#/POINTER [OBJECT]"},
    {"env", "aos-json env [--path SUBPATH] [--prefix PREFIX] [--parents] FILE#/POINTER NAME"},
    {"ref", "aos-json ref [--move] [--parents] FILE#/POINTER TARGET"},
    {"check", "aos-json check [--env] FILE[#/POINTER]..."},
};

const std::map<std::string, std::string> SUB_HELP = {
    {"get", R"(aos-json get - Read a JSON value.

usage: aos-json get [--follow] [--resolve] [--str] FILE#/POINTER
       aos-json get --help

flags:
  --follow     follow $ref on the path to the value
  --resolve    resolve directives inside the result
  --str        print a string without JSON quotes
  -h, --help   show this help

Print the selected value as one JSON line, or as text with --str.

exit codes: 0 read; 1 error.
more: aos-json/README.md
)"},
    {"peek", R"(aos-json peek - Inspect a JSON value with large children folded.

usage: aos-json peek [--follow] [--depth N] FILE#/POINTER
       aos-json peek --help

flags:
  --follow     follow $ref on the path and at the selected value
  --depth N    expand N levels, from 0 to 999 (default: 1)
  -h, --help   show this help

Print the location and a text summary; expand children up to the chosen depth.

exit codes: 0 shown; 1 error.
more: aos-json/README.md
)"},
    {"where", R"(aos-json where - Locate the source of a JSON value.

usage: aos-json where FILE#/POINTER
       aos-json where --help

flags:
  -h, --help   show this help

Print one FILE#/POINTER per $ref hop; the final line is the source.
An environment value ends with $env NAME.

exit codes: 0 located; 1 error.
more: aos-json/README.md
)"},
    {"set", R"(aos-json set - Set a JSON value.

usage: aos-json set [--check] [--follow] [--parents] [--str] FILE#/POINTER [VALUE]
       aos-json set --help

flags:
  --check      validate before writing; reject changes that add problems
  --follow     follow $ref to the value being replaced
  --parents    create missing parent objects
  --str        treat VALUE or stdin as a literal string
  -h, --help   show this help

Read VALUE from argv, or stdin when omitted; write changed files atomically.

exit codes: 0 updated; 1 error.
more: aos-json/README.md
)"},
    {"batch", R"(aos-json batch - Set several JSON values together.

usage: aos-json batch [--check] [--follow] [--parents] FILE
       aos-json batch --help

flags:
  --check      validate before writing; reject changes that add problems
  --follow     follow $ref to the values being replaced
  --parents    create missing parent objects
  -h, --help   show this help

Read {"/POINTER": VALUE, ...} from stdin; an empty pointer replaces the file.
Apply every change in memory before writing changed files atomically.

exit codes: 0 updated; 1 error.
more: aos-json/README.md
)"},
    {"del", R"(aos-json del - Delete a JSON key or array element.

usage: aos-json del [--follow] FILE#/POINTER
       aos-json del --help

flags:
  --follow     follow $ref; remove matching keys from merged parts
  -h, --help   show this help

Write changed files atomically; deleting a whole file is not supported.

exit codes: 0 deleted; 1 error.
more: aos-json/README.md
)"},
    {"append", R"(aos-json append - Append a value to a JSON array.

usage: aos-json append [--check] [--follow] [--str] FILE#/POINTER [VALUE]
       aos-json append --help

flags:
  --check      validate before writing; reject changes that add problems
  --follow     follow $ref to the target array
  --str        treat VALUE or stdin as a literal string
  -h, --help   show this help

Read VALUE from argv, or stdin when omitted; write changed files atomically.

exit codes: 0 appended; 1 error.
more: aos-json/README.md
)"},
    {"merge", R"(aos-json merge - Merge keys into a JSON object.

usage: aos-json merge [--check] [--follow] FILE#/POINTER [OBJECT]
       aos-json merge --help

flags:
  --check      validate before writing; reject changes that add problems
  --follow     follow $ref to the target object
  -h, --help   show this help

Read OBJECT from argv, or stdin when omitted. Replace matching keys at one level.

exit codes: 0 merged; 1 error.
more: aos-json/README.md
)"},
    {"env", R"(aos-json env - Write an environment directive.

usage: aos-json env [--path SUBPATH] [--prefix PREFIX] [--parents] FILE#/POINTER NAME
       aos-json env --help

flags:
  --path SUBPATH    add the directive's $path
  --prefix PREFIX   add the directive's $prefix
  --parents         create missing parent objects
  -h, --help        show this help

Replace the selected value with {"$env": NAME, ...}; write changed files atomically.

exit codes: 0 updated; 1 error.
more: aos-json/README.md
)"},
    {"ref", R"(aos-json ref - Write a reference directive.

usage: aos-json ref [--move] [--parents] FILE#/POINTER TARGET
       aos-json ref --help

flags:
  --move       move the current value to TARGET before replacing it
  --parents    create missing parent objects
  -h, --help   show this help

Replace the selected value with {"$ref": TARGET}; TARGET is relative to its file.

exit codes: 0 updated; 1 error.
more: aos-json/README.md
)"},
    {"check", R"(aos-json check - Check aos JSON files.

usage: aos-json check [--env] FILE[#/POINTER]...
       aos-json check --help

flags:
  --env        also report unset environment variables
  -h, --help   show this help

Check references, directive forms and exec forms; print one problem per line.

exit codes: 0 no problems; 10 problems found; 1 error.
more: aos-json/README.md
)"},
};

}  // namespace

const std::string& cli_usage(const std::string& command) {
    return SUB_USAGE.at(command);
}

const std::string& cli_help(const std::string& command) {
    return SUB_HELP.at(command);
}

Cli parse_args(const std::vector<std::string>& args,
               const std::map<std::string, std::string>& flags,
               const std::map<std::string, std::string>& switches,
               const std::string& command) {
    // 11-11 P-44 續：旗標寫在位置參數前後都收。set／append／merge 照舊規則（keep＝1，旗標只在 FILE 前）：
    // 它們的值什麼字都可以（--str 時 -x、--check 也是合法的值），FILE 後再認旗標會把值吃掉
    size_t keep = command == "set" || command == "append" || command == "merge" ? 1 : 0;
    return aos::parse_cli(args, flags, switches, cli_help(command), {}, {}, keep);
}

}  // namespace aos::json
