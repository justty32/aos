// main.cpp：aos-directive 命令列——讀一份 JSON、解開所有指示詞、印出來。
//
//     aos-directive < 設定.json
//
// stdin 一份 JSON（空的＝{}、多份＝InputExtra），以呼叫者的 cwd 為基準解開指示詞（見 aos/directive.hpp），
// stdout 印一行解好的 JSON、退出 0；出錯 stderr 印一行 {"error": {"code", "msg"}}、退出 1。不收任何參數。
#include "aos/directive.hpp"
#include "aos/io.hpp"

#include <exception>
#include <filesystem>

int main(int argc, char** argv) {
    try {
        if (argc > 1) {
            throw aos::Error{aos::code::ArgumentsBad, std::string("aos-directive 不收參數（從 stdin 讀），多了 ") + argv[1]};
        }
        aos::Json doc = aos::read_stdin();
        return aos::emit(aos::resolve(doc, std::filesystem::current_path()));
    } catch (const aos::Error& e) {
        return aos::emit_error(e);
    } catch (const std::exception& e) {
        return aos::emit_error(aos::Error{aos::code::Internal, e.what()});
    }
}
