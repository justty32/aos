// common.hpp：aos-json 跨元素共用——自己的錯誤代號。
//
// 全家共用的代號（ArgumentsBad、FlagUnknown、WriteFailed、Internal）在 aos-util 的 aos::code；
// DirectiveBad 在 aos-directive。這裡只加 aos-json 自己會吐的（照 C-54：…Missing／…Unknown／…Bad）。
#pragma once

#include "aos/directive.hpp"
#include "aos/error.hpp"
#include "aos/io.hpp"

namespace aos::json {

namespace code {
using namespace aos::code;   // ArgumentsBad、FlagUnknown、WriteFailed、Internal、DirectiveBad…
inline constexpr const char* CommandUnknown = "CommandUnknown"; // 不認得的子命令
inline constexpr const char* FileMissing = "FileMissing";       // 要讀、要改的檔不在
inline constexpr const char* FileBad = "FileBad";               // 檔讀不了（含資料夾）、不是 JSON
inline constexpr const char* SpecBad = "SpecBad";               // `檔#xx`：# 後面不是 /
inline constexpr const char* PointerMissing = "PointerMissing"; // 指標指不到
inline constexpr const char* ValueMissing = "ValueMissing";     // 要寫的值沒給（參數沒有、stdin 空的）
inline constexpr const char* ValueBad = "ValueBad";             // 要寫的值不是一份 JSON；$ref 目標寫法不合
inline constexpr const char* TargetBad = "TargetBad";           // 那個位置不能這樣改（append 不是陣列、merge 不是物件…）
inline constexpr const char* CheckFailed = "CheckFailed";       // --check：改完會多出 check 的問題，沒寫
inline constexpr const char* FollowMissing = "FollowMissing";   // 路上經過指示詞：要穿過去改被參照的檔，得加 --follow
// check 報的問題（印在 stdout，不是 aos-json 自己的錯）
inline constexpr const char* DirectiveFormBad = "DirectiveFormBad"; // 指示詞寫法不合：aos 會原封不動留著，多半是寫錯
inline constexpr const char* ExecBad = "ExecBad";               // exec 的形狀不對
}  // namespace code

}  // namespace aos::json
