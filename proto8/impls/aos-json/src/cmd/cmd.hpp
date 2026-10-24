// cmd.hpp：【cmd】每個子命令一個函數：拿到子命令後面的參數（不含 `aos-json 子命令`），回退出碼；錯丟 aos::Error。
//
//   read.cpp   get、where
//   peek.cpp   peek（漸進展開：一次只看一層，大的值摺起來）
//   write.cpp  set、batch、del、append、merge、env、ref（寫入共用：找位置 → 改 → 有變才原子寫回）
//   check.cpp  check
#pragma once

#include "doc/doc.hpp"

#include <string>
#include <vector>

namespace aos::json {

using Args = std::vector<std::string>;

int cmd_get(const Args& args);
int cmd_peek(const Args& args);
int cmd_where(const Args& args);
int cmd_set(const Args& args);
int cmd_batch(const Args& args);
int cmd_del(const Args& args);
int cmd_append(const Args& args);
int cmd_merge(const Args& args);
int cmd_env(const Args& args);
int cmd_ref(const Args& args);
int cmd_check(const Args& args);

// check 的本體：從 spec 往下驗（docs 裡已經讀的檔用記憶體裡的版本，set --check 拿來驗改完、還沒寫的樣子）。回每個問題一行。
std::vector<std::string> problems_of(Docs& docs, const std::string& spec, bool env);

}  // namespace aos::json
