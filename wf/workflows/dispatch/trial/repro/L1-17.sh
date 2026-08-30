#!/usr/bin/env bash
# pi 跑失敗，但世界照樣報成功：status 仍是 idle、batch out 記 exit 0、run 印一條正常的 turn 行
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
export PATH="$(dirname "$AOS"):$PATH"
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
"$AOS" agent init --name w --engine pi >/dev/null
"$AOS" say "在這個資料夾建一個 hello.txt 內容是 hi"
echo "--- 拿掉 DEEPSEEK_API_KEY 推一回合："
env -u DEEPSEEK_API_KEY timeout 300 "$AOS" run . --step 1; echo "run exit=$?"
echo "--- aos state 說："; "$AOS" state
echo "--- 這一回合的 out（loop 眼中的成敗）："; cat .aos/batch/1/out/*.json
echo "--- hello.txt 建出來了嗎： $([ -f hello.txt ] && echo yes || echo no)"
echo "--- 只有 listen 進 log 才看得到失敗原文："; "$AOS" listen --once | tail -5
echo
echo "EXPECT: pi 失敗時 aos run 要以非 0 結束、status 要是 error 之類，且訊息要說「請設定 DEEPSEEK_API_KEY」"
echo "ACTUAL: run 印一條正常的 turn 行、exit 0；batch/1/out/*.json 記 exit: 0；status 仍是 status=idle"
echo "        （只有 detail 變成「pi 失敗」）。錯誤原文只在 log.md／listen 裡，而且是 pi 自己的話："
echo "        「No API key found for deepseek. Use /login ...」——叫人去 pi 裡面跑 /login，"
echo "        沒有提到 aos 文件寫的 DEEPSEEK_API_KEY 環境變數。agent init --engine pi 當下也完全沒提過需要 key。"
rm -rf "$W"
