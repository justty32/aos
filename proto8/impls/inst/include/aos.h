/* aos.h：libaos 的公開介面。
 * 主要函數 aos_inst_exec：起一個子程式、等它結束、把結果填好。
 * 要在子程式跑的期間做別的事（例如轉送訊號），改用兩步：
 *   aos_inst_start（起好就回，拿到 pid）→ aos_inst_wait（等到結束）。
 *
 * 白話：你填一張單子（aos_inst_input_t）：
 *   要跑什麼、在哪跑、環境、三個串流接哪個檔、最多跑多久；
 * 它 fork＋exec 那個程式，等它結束（或時間到把它收掉），
 * 把「回了幾號、跑了多久」填進 aos_inst_result_t。
 * 對應 Python 版 proto8/lib/aos_inst.py 的 run()，
 * 但不讀 JSON、沒有命令列、不解指示詞。
 *
 * 型別只用 C 基本型別、bool（<stdbool.h>）和三個平的結構體，
 * 給其他語言用 C FFI 呼叫（ctypes、cffi、Rust、Go…）。
 *
 * 訊號：lib 完全不碰訊號處理。
 *   不裝 handler、不改呼叫者的訊號遮罩、不轉送訊號給子程式。
 *   呼叫者收到 Ctrl-C 要怎麼辦是呼叫者的事；
 *   子程式跟呼叫者在同一個行程群組，終端機的 Ctrl-C 會一起送到它
 *   （new_session＝true 時不會：子程式自成一個 session，見下面）。
 *   子程式那一側在 exec 前把訊號處置恢復預設、遮罩清空，
 *   所以呼叫者忽略的訊號不會傳下去。
 *   注意：呼叫者若把 SIGCHLD 設成 SIG_IGN，
 *   或另有執行緒用 waitpid(-1) 搶收子程式，
 *   lib 會收不到結果（回 AOS_INST_ERR_WAIT_FAILED）。
 *
 * 執行緒：沒有全域狀態，可以在多條執行緒同時呼叫。
 *   極端情況：別的執行緒剛好同時 fork 的話，那個子行程會短暫繼承
 *   lib 用來回報 exec 失敗的 pipe（帶 CLOEXEC，它 exec 後就關），
 *   這段期間 lib 會多等一下才知道 exec 成功。
 *
 * 收掉只管直接子程式：timeout 到了，SIGTERM／SIGKILL 只送給 lib 起的那個
 *   子程式。它自己再起的孫程式（例如 sh -c 裡背景跑的 sleep）會留著；
 *   要整群收掉是外層的事（例如讓子程式自己開新的行程群組再整群送）。
 *   new_session＝true 時整群：子程式 exec 前 setsid() 自成一個行程群組，
 *   timeout 的 SIGTERM／SIGKILL 改對整個群組送（kill(-pid, …)），
 *   孫程式一起收掉（自己又另開群組的不算）。
 *
 * ABI 尚未凍結：三個結構體沒有版本欄位，日後加欄位時，
 *   用 FFI 的呼叫端（例如 ctypes 的 Structure）要跟著改。
 *
 * 怎麼等子程式：Linux 5.3+ 用 pidfd＋poll，子程式一結束就醒；
 *   拿不到 pidfd（核心太舊、被 seccomp 擋）就退回每 1 毫秒看一次。
 *   結果的 ms 以毫秒為單位（無條件捨去）：pidfd 路幾乎沒延遲，
 *   退路最多多算約 1 毫秒。
 */
#ifndef AOS_H
#define AOS_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 只有標了 AOS_API 的符號會匯出（其他都是 hidden）。 */
#if defined(__GNUC__)
#define AOS_API __attribute__((visibility("default")))
#else
#define AOS_API
#endif

/* aos_inst_exec 的回傳值。
 * 函數型別寫 int（FFI 比較好接），值就是這些。
 *   0＝成功跑完（子程式回幾號、被限時收掉都算成功）
 *   非 0＝lib 自己出錯，子程式沒跑或沒收到結果
 * 每個值的名字對應 Python 版 InstError 的 code，
 * aos_inst_strerror 回的就是那個名字。 */
typedef enum aos_inst_error {
  AOS_INST_OK = 0,
  /* InputBad：in／out 是 NULL、argv 是 NULL 或空 */
  AOS_INST_ERR_INPUT_BAD = 1,
  /* PathConflict：merge＝true 又給了 paths[2] 或 inherits[2]；
   * 或 inherits[i] 與 paths[i] 同時給 */
  AOS_INST_ERR_PATH_CONFLICT = 2,
  /* PathNotAbsolute：cwd 或 paths 有一個不是 '/' 開頭 */
  AOS_INST_ERR_PATH_NOT_ABSOLUTE = 3,
  /* CwdMissing：cwd 不存在、不是資料夾、或沒有進去的權限（x） */
  AOS_INST_ERR_CWD_MISSING = 4,
  /* OpenFailed：串流的檔開不了（上層資料夾不存在、是資料夾…） */
  AOS_INST_ERR_OPEN_FAILED = 5,
  /* CommandMissing：argv[0] 那個檔不存在（或照 PATH 找不到） */
  AOS_INST_ERR_COMMAND_MISSING = 6,
  /* CommandBad：檔在，但不能執行 */
  AOS_INST_ERR_COMMAND_BAD = 7,
  /* LaunchFailed：其他起不來的原因（fork 失敗…） */
  AOS_INST_ERR_LAUNCH_FAILED = 8,
  /* WaitFailed：waitpid 失敗，收不到結果（見上面訊號那段） */
  AOS_INST_ERR_WAIT_FAILED = 9,
  /* KillFailed：時間到要收子程式，kill 卻失敗
   * （例如 EPERM：子程式 exec 了 setuid 程式）。lib 不再等它，
   * 子程式可能還在跑、也還沒收屍；out->pid 有填，呼叫者自己處理。 */
  AOS_INST_ERR_KILL_FAILED = 10
} aos_inst_error_t;

/* 要跑什麼、怎麼跑。
 * 全零（aos_inst_input_t in = {0};）＝每一欄都用預設，
 * 只有 argv 一定要填。
 * 每欄註解的「零＝」是這欄為 NULL／false／0 時的意思。
 *
 * 路徑一律絕對路徑：cwd 和 paths[i] 不是 NULL 就要以 '/' 開頭，
 * 否則回 AOS_INST_ERR_PATH_NOT_ABSOLUTE。
 * lib 不幫忙建資料夾、不配記憶體（不 malloc）。 */
typedef struct aos_inst_input {
  /* ---- 要跑什麼、在哪跑 ---- */

  /* NULL 結尾的字串陣列，至少一個（必填）。
   * 交給 glibc 的 execvp 跑，所以：
   *   有 '/'（"/bin/ls"、"./x"）＝直接用；相對的從 cwd 算
   *   沒有 '/'（"ls"）＝照子程式那份環境的 PATH 找：
   *     envs 不是 NULL 就看 envs 裡的 PATH；
   *     環境裡沒有 PATH 時，用 glibc 自己的預設路徑
   *     PATH 是空字串＝只在 cwd 找（空的一段＝目前資料夾；實測如此）
   * 檔案有執行權限但不是可執行格式（例如沒有 #! 的腳本），
   * glibc 會改用 /bin/sh 跑它：回 OK，code 由 sh 決定
   * （內容不是 shell 指令的話通常是 126 或 127），不是 LaunchFailed。 */
  const char *const *argv;
  /* 在哪個資料夾跑：絕對路徑，要已經存在、而且進得去（x 權限）。
   * 零＝呼叫者現在的 cwd。 */
  const char *cwd;

  /* ---- 環境 ---- */

  /* 子程式的完整環境：NULL 結尾的 "KEY=VALUE" 陣列，原樣給，
   * lib 不接、不去重、不補。找程式用的 PATH 也看它。
   * 要在呼叫者的環境上改一點，自己組好一份完整的再給。
   * 零＝沿用呼叫者現在的 environ。 */
  const char *const *envs;

  /* ---- 三個串流 ---- */

  /* [0]stdin [1]stdout [2]stderr 接哪個檔（絕對路徑）。
   * stdin 開來讀；stdout／stderr 開來寫，檔不在就建，
   * 但上層資料夾要已經存在。零＝/dev/null（inherits[i] 為 true 時見下）。
   * 要接呼叫者自己的 stdout／stderr：寫 "/dev/stdout"／"/dev/stderr"，
   *   並把 appends 設 true（不然呼叫者的輸出若是檔案，會被清空）；
   *   呼叫者的輸出是 socket 時這招開不了。
   * 不要給沒人接的 FIFO：open 會一直卡住，timeout_ms 管不到。
   * 路徑是捷徑（symlink）會照著走，跟 shell 的 > 一樣
   *   （/dev/stdout 本身就是捷徑）；斷掉的捷徑會建出它指向的檔。
   *   多人可寫的資料夾（如 /tmp）小心別人事先放好的捷徑。
   * stdout 和 stderr 給同一個路徑又沒設 merge：兩邊各開一次、
   *   各自從頭寫，會互相蓋掉。要合在一起請用 merge。 */
  const char *paths[3];
  /* [1][2] true＝附加在檔尾；[0] 不看。零＝清空再寫。 */
  bool appends[3];
  /* true＝stderr 併進 stdout，這時 paths[2] 要是 NULL、inherits[2] 要是
   * false，否則回 AOS_INST_ERR_PATH_CONFLICT。零＝分開。 */
  bool merge;

  /* ---- 時間 ---- */

  /* 最多跑幾毫秒。零＝不限時。
   * 大到「現在＋它」溢位（例如 FFI 傳 -1）也當成不限時。 */
  unsigned long long timeout_ms;
  /* 時間到了先送 SIGTERM，過 grace_ms 還沒結束再 SIGKILL。
   * 零＝直接 SIGKILL。大到溢位（例如 -1）＝一直等 SIGTERM 生效。 */
  unsigned long long grace_ms;

  /* ---- 後加的兩個選項（放在尾端；全零＝照上面的舊行為） ---- */

  /* [0]stdin [1]stdout [2]stderr：true＝那個串流直接用呼叫者自己的
   * fd 0／1／2（不開檔、不換成 /dev/null；呼叫者的那個 fd 是什麼就是什麼，
   * 關著就是關著）。這時 paths[i] 要是 NULL，否則回
   * AOS_INST_ERR_PATH_CONFLICT；appends[i] 不看。
   * merge＝true 又 inherits[1]＝true：stderr 併進呼叫者的 fd 1。
   * 零＝照 paths[i]（NULL＝/dev/null）。 */
  bool inherits[3];
  /* true＝子程式 exec 前 setsid()，自成一個 session／行程群組：
   * timeout 的 SIGTERM／SIGKILL 對整個群組送，孫程式一起收掉；
   * 終端機的 Ctrl-C 不會再自動送到它（要轉送是呼叫者的事，
   * 對 -proc->pid 送就是整群）；它也沒有控制終端，讀不了終端。
   * 零＝跟呼叫者同一個群組，收掉只管直接子程式。 */
  bool new_session;
} aos_inst_input_t;

/* 跑完的結果。 */
typedef struct aos_inst_result {
  /* 子程式的退出碼；被訊號停掉＝128＋訊號號碼。
   * WaitFailed／KillFailed 時是 -1。 */
  int code;
  /* 被哪個訊號停掉；0＝沒有（自己結束的）。
   * timed_out＝true 時也可能是 0：子程式在送訊號前剛好結束，
   * 或收到 SIGTERM 後自己 exit。是不是被收掉，以 timed_out 為準。 */
  int signal;
  /* true＝時間到了，lib 動手收它（不管它最後怎麼結束的） */
  bool timed_out;
  /* 子程式的 pid。子程式一起來就填好，WaitFailed／KillFailed 時也有 */
  long pid;
  /* 從起子程式到收完，跑了幾毫秒（精度見檔頭「怎麼等子程式」） */
  unsigned long long ms;
} aos_inst_result_t;

/* 起好、還沒等完的子程式（aos_inst_start 填、aos_inst_wait 用）。
 * 呼叫者自己配置（放 stack 就好，lib 不 malloc）。
 * 呼叫者只讀 pid；其他欄位是 aos_inst_wait 要用的，別碰。 */
typedef struct aos_inst_proc {
  /* 子程式的 pid（可以拿來送訊號） */
  long pid;
  /* ---- 以下別碰 ---- */
  /* 代表子程式的 pidfd；-1＝沒有（核心太舊等），wait 改走輪詢 */
  int pidfd;
  /* 起子程式前一刻的單調時鐘毫秒數（算 ms 用） */
  unsigned long long t0_ms;
  /* timeout 的期限（單調時鐘毫秒數）；0＝不限時 */
  unsigned long long deadline_ms;
  /* 單子上的 grace_ms */
  unsigned long long grace_ms;
  /* 單子上的 new_session（true＝收掉時對整群送） */
  bool group;
} aos_inst_proc_t;

/* 兩步用法的第一步：照 *in 起一個子程式就回來，不等它。
 * 回 AOS_INST_OK＝子程式已經 exec 成功，pid 在 proc->pid。
 * timeout_ms 從這裡開始算。
 * 非 0＝子程式沒起來（InputBad、PathConflict、PathNotAbsolute、
 *   CwdMissing、OpenFailed、CommandMissing、CommandBad、
 *   LaunchFailed），這時不用、也不能呼叫 aos_inst_wait。
 * 一定要配 aos_inst_wait：回 OK 之後呼叫者必須呼叫一次 aos_inst_wait，
 *   否則子程式結束後會變殭屍（沒人收屍），pidfd 也會漏掉。
 * 要在子程式跑的期間做別的事（例如轉送訊號給 proc->pid），就用這兩步；
 *   不用的話直接呼叫 aos_inst_exec。
 * in 和 proc 都不能是 NULL。*in 只讀不改，回來之後就可以丟掉。 */
AOS_API int aos_inst_start(const aos_inst_input_t *in, aos_inst_proc_t *proc);

/* 兩步用法的第二步：等 aos_inst_start 起的子程式結束（時間到就
 * SIGTERM，過 grace_ms 再 SIGKILL），收屍、關 pidfd，把結果填進 *out。
 * 回 AOS_INST_OK、AOS_INST_ERR_WAIT_FAILED 或 AOS_INST_ERR_KILL_FAILED
 * （這兩個的 out 跟 aos_inst_exec 一樣：pid、timed_out、ms 有填，
 *  code＝-1、signal＝0）。
 * 每個 proc 只能呼叫一次。可以在別條執行緒呼叫（例如主執行緒 start、
 * 工人執行緒 wait）。proc 或 out 是 NULL 回 InputBad（子程式就沒人收了）。 */
AOS_API int aos_inst_wait(aos_inst_proc_t *proc, aos_inst_result_t *out);

/* 一步做完＝aos_inst_start＋aos_inst_wait：
 * 照 *in 起一個子程式、等它結束，把結果填進 *out。
 * 回 aos_inst_error_t 的值（0＝成功）。
 * 子程式沒起來就出錯的話，*out 不會被動到。
 * 子程式起來之後出錯（WaitFailed／KillFailed）：pid、timed_out、ms 有填，
 * code＝-1、signal＝0。
 * in 和 out 都不能是 NULL。*in 只讀不改。 */
AOS_API int aos_inst_exec(const aos_inst_input_t *in, aos_inst_result_t *out);

/* 錯誤代號 → 名字（"CommandMissing" 這種，跟 Python 版一樣）。
 * 不認得的代號回 "Unknown"。字串是常數，不用 free。 */
AOS_API const char *aos_inst_strerror(int code);

#ifdef __cplusplus
}
#endif

#endif
