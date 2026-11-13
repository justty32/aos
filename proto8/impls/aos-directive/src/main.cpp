// main.cpp：aos-directive 命令列——讀一份 JSON、解開所有指示詞、印出來。
//
//     aos-directive [--file 檔 [--at 指標]] < 設定.json
//
// stdin 一份 JSON（空的＝{}、多份＝InputBad），以呼叫者的 cwd 為基準解開指示詞（見 aos/directive.hpp）；
// --file 檔＝這份 JSON 是從那份檔讀的（11-12）：相對 $ref 從它的資料夾算、`#…` 開頭的 $ref 取它（沒給＝`#…` 原封不動）；
// --at 指標＝這份 JSON 是那份檔的哪一格（11-13，`#./`、`#../` 從那裡算；沒給＝整份檔的根），要跟 --file 一起給；
// stdout 印一行解好的 JSON、退出 0；出錯 stderr 印一行「aos-directive: error: 代號 原因」、退出 1（11-05 stdio-unify R1）。
// `--help`＝英文說明印 stdout、退 0（R3）。不收位置參數：命令列照 P-44 用 aos::parse_cli 解（不認得的旗標＝FlagUnknown、位置參數＝ArgumentsBad）。
#include "aos/util/cli.hpp"
#include "aos/directive.hpp"
#include "aos/util/files.hpp"
#include "aos/util/io.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>

static const char* USAGE = "aos-directive [--file FILE [--at POINTER]] < CONFIG.json";

static const char* HELP = R"(usage: aos-directive [--file FILE [--at POINTER]] < CONFIG.json

Read one JSON document from stdin (empty = {}), resolve every directive in it
($ref, $env, $path, ...; relative paths from the current directory) and print the
result as one line.

A $ref path: left of # is the file system (from the folder of the file it is
written in), right of # is inside JSON:
  "x.json", "../x.json"  that whole file      "x.json#/a/b"  /a/b of x.json
  "#/a/b"   /a/b of this file                 "#" or "#/"    this whole file
  "#./b"    b of the object this $ref is in   "#../c"        c one level up
"x.json#./b", "x.json#../c", "#b" and "x.json#b" are errors (DirectiveBad).

flags:
  --file FILE     the JSON on stdin was read from FILE: relative paths count from
                  FILE's directory, and "#..." points into FILE itself (without
                  --file such a $ref is left as it is)
  --at POINTER    the JSON on stdin is POINTER of FILE (default: the whole file);
                  "#./" and "#../" count from there. Needs --file
  -h, --help      show this help

exit codes: 0 ok; 1 error ("aos-directive: error: CODE ..." on stderr).
)";

static int fail(const aos::Error& e) {
    return aos::fail("aos-directive", e);
}

int main(int argc, char** argv) {
    try {
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {{"--file", "file"}, {"--at", "at"}}, {}, HELP);
        } catch (const aos::Error& e) {
            throw aos::usage_error(e.code, e.msg, USAGE);
        }
        if (!cli.rest.empty()) {
            throw aos::usage_error(aos::code::ArgumentsBad, "takes no arguments, reads stdin; got extra " + cli.rest[0], USAGE);
        }
        aos::Json doc = aos::read_stdin();
        aos::RefBase base{std::filesystem::current_path()};
        if (cli.opts.count("file") != 0) {
            std::string f = aos::abspath(cli.opts["file"]);
            base = aos::RefBase{aos::dirname(f), f};
        }
        if (cli.opts.count("at") != 0) {
            const std::string& at = cli.opts["at"];
            if (cli.opts.count("file") == 0) {
                throw aos::usage_error(aos::code::ArgumentsBad, "--at needs --file (which file the pointer is in)", USAGE);
            }
            if (!at.empty() && !at.starts_with("/")) {
                throw aos::usage_error(aos::code::ArgumentsBad, "--at must be a JSON pointer (\"\" or /a/b), got " + at, USAGE);
            }
            base.at = aos::pointer_tokens(at);
        }
        return aos::emit(aos::resolve(doc, base));
    } catch (const aos::Error& e) {
        return fail(e);
    } catch (const std::exception& e) {
        return fail(aos::Error{aos::code::Internal, e.what()});
    }
}
