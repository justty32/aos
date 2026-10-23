/* inst_exec.c：四個公開函數。
 *   aos_inst_start     起子程式就回（由上往下）：
 *                        1. 檢查參數（路徑一律要是絕對路徑、cwd 要存在）
 *                        2. 環境原樣用
 *                        3. 開三個串流（inherits 的不開）
 *                        4. 起子程式（new_session 就自成群組）、
 *                           拿 pidfd、記下期限
 *   aos_inst_wait      等它、收它、填結果
 *   aos_inst_exec      上面兩個接起來
 *   aos_inst_strerror  錯誤代號 → 名字
 * 細節在其他檔（見 inst_internal.h 開頭的表）。
 *
 * 不用 malloc：路徑、環境都原樣用。
 *
 * 寫法（整個 src/ 都一樣）：一行一件事。不在 if 條件裡賦值，
 * 不串長的 && ／ ||（先算成有名字的 bool，或拆成巢狀 if），
 * 每個 if 都加 {}。排版用 clang-format --style=LLVM。
 */
#include "inst_internal.h"

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

/* ---- 參數 ---- */

/* path 是 NULL（＝用預設）或以 '/' 開頭就算過關。 */
static bool absolute_or_null(const char *path) {
  if (path == NULL) {
    return true;
  }
  return path[0] == '/';
}

/* 檢查單子。過關回 AOS_INST_OK。 */
static int check_input(const aos_inst_input_t *in) {
  if (in->argv == NULL) {
    return AOS_INST_ERR_FIELD_TYPE;
  }
  if (in->argv[0] == NULL) {
    return AOS_INST_ERR_FIELD_TYPE;
  }
  if (in->merge && in->paths[2] != NULL) {
    return AOS_INST_ERR_PATH_CONFLICT;
  }
  if (in->merge && in->inherits[2]) {
    return AOS_INST_ERR_PATH_CONFLICT;
  }
  /* 一個串流不能又接呼叫者的、又接檔 */
  for (int i = 0; i < 3; ++i) {
    if (in->inherits[i] && in->paths[i] != NULL) {
      return AOS_INST_ERR_PATH_CONFLICT;
    }
  }

  /* cwd 和三個串流：一律絕對路徑 */
  if (!absolute_or_null(in->cwd)) {
    return AOS_INST_ERR_PATH_NOT_ABSOLUTE;
  }
  for (int i = 0; i < 3; ++i) {
    if (!absolute_or_null(in->paths[i])) {
      return AOS_INST_ERR_PATH_NOT_ABSOLUTE;
    }
  }

  /* cwd 要是已經存在、而且進得去的資料夾：
   * stat 看是不是資料夾，access(X_OK) 看有沒有進去的權限。
   * 沒先檢查的話，子程式 chdir 失敗會被誤報成別的錯 */
  if (in->cwd != NULL) {
    struct stat st;
    bool ok = stat(in->cwd, &st) == 0;
    bool is_dir = ok && S_ISDIR(st.st_mode);
    if (!is_dir) {
      return AOS_INST_ERR_CWD_MISSING;
    }
    if (access(in->cwd, X_OK) != 0) {
      return AOS_INST_ERR_CWD_MISSING;
    }
  }
  return AOS_INST_OK;
}

/* ---- 公開函數 ---- */

AOS_API int aos_inst_start(const aos_inst_input_t *in, aos_inst_proc_t *proc) {
  /* 1. 參數 */
  if (in == NULL || proc == NULL) {
    return AOS_INST_ERR_FIELD_TYPE;
  }
  int rc = check_input(in);
  if (rc != AOS_INST_OK) {
    return rc;
  }

  /* 2. 環境：envs 原樣交給子行程（NULL＝沿用呼叫者的 environ），
   * lib 不接、不去重、不補 */
  char *const *envp = (char *const *)in->envs;
  /* exec 要的是 char *const *；不會改內容，轉型只是配合老簽名 */
  char *const *argv = (char *const *)in->argv;

  /* 3. 開三個串流；之後出錯一律跳到 done 收拾 */
  int si = -1;
  int so = -1;
  int se = -1;
  int out_mode = O_WRONLY | O_CREAT | O_TRUNC;
  if (in->appends[1]) {
    out_mode = O_WRONLY | O_CREAT | O_APPEND;
  }
  int err_mode = O_WRONLY | O_CREAT | O_TRUNC;
  if (in->appends[2]) {
    err_mode = O_WRONLY | O_CREAT | O_APPEND;
  }
  /* inherits[i]＝不開檔，fd 留 -1（子程式那側不動那個 fd） */
  if (!in->inherits[0]) {
    rc = inst_open_stream(in->paths[0], O_RDONLY, &si);
    if (rc != AOS_INST_OK) {
      goto done;
    }
  }
  if (!in->inherits[1]) {
    rc = inst_open_stream(in->paths[1], out_mode, &so);
    if (rc != AOS_INST_OK) {
      goto done;
    }
  }
  bool open_err = !in->merge && !in->inherits[2];
  if (open_err) {
    rc = inst_open_stream(in->paths[2], err_mode, &se);
    if (rc != AOS_INST_OK) {
      goto done;
    }
  }

  /* 4. 起子程式；成功才填 proc（失敗時 proc 不動） */
  int child_err = se;
  if (in->merge) {
    child_err = so; /* stderr 併進 stdout */
  }
  bool merge_into_caller = in->merge && in->inherits[1];
  if (merge_into_caller) {
    child_err = 1; /* stderr 併進呼叫者的 fd 1 */
  }
  unsigned long long t0 = inst_now_ms();
  pid_t pid;
  rc =
      inst_start(si, so, child_err, in->cwd, argv, envp, in->new_session, &pid);
  if (rc != AOS_INST_OK) {
    goto done;
  }
  proc->pid = (long)pid;
  proc->pidfd = inst_open_pidfd(pid); /* -1＝wait 改走 1 毫秒輪詢 */
  proc->t0_ms = t0;
  proc->deadline_ms = inst_deadline_after(in->timeout_ms); /* 0＝不限 */
  proc->grace_ms = in->grace_ms;
  proc->group = in->new_session;

done:
  /* 串流已經 dup 給子程式了（或根本沒起來），這邊的都關掉 */
  if (si >= 0) {
    close(si);
  }
  if (so >= 0) {
    close(so);
  }
  if (se >= 0) {
    close(se);
  }
  return rc;
}

AOS_API int aos_inst_wait(aos_inst_proc_t *proc, aos_inst_result_t *out) {
  if (proc == NULL || out == NULL) {
    return AOS_INST_ERR_FIELD_TYPE;
  }
  /* 先填好 pid，等待出錯時呼叫者還拿得到 */
  out->pid = proc->pid;
  out->code = -1;
  out->signal = 0;
  out->timed_out = false;
  out->ms = 0;

  int status = 0;
  bool timed_out = false;
  int rc = inst_wait_child((pid_t)proc->pid, proc->pidfd, proc->deadline_ms,
                           proc->grace_ms, proc->group, &status, &timed_out);
  if (proc->pidfd >= 0) {
    close(proc->pidfd);
    proc->pidfd = -1;
  }
  out->timed_out = timed_out;
  out->ms = inst_now_ms() - proc->t0_ms;
  if (rc != AOS_INST_OK) {
    return rc; /* WaitFailed／KillFailed：code 留 -1、signal 留 0 */
  }

  /* 結果：被訊號停掉＝128＋訊號號碼 */
  out->code = WEXITSTATUS(status);
  if (WIFSIGNALED(status)) {
    out->signal = WTERMSIG(status);
    out->code = 128 + WTERMSIG(status);
  }
  return AOS_INST_OK;
}

AOS_API int aos_inst_exec(const aos_inst_input_t *in, aos_inst_result_t *out) {
  /* out 先檢查：不然起了子程式卻沒地方填結果、也沒人收 */
  if (out == NULL) {
    return AOS_INST_ERR_FIELD_TYPE;
  }
  aos_inst_proc_t proc = {0}; /* 全零：start 失敗時不會用到，只是讓編譯器放心 */
  int rc = aos_inst_start(in, &proc);
  if (rc != AOS_INST_OK) {
    return rc; /* 子程式沒起來：out 不動 */
  }
  return aos_inst_wait(&proc, out);
}

AOS_API const char *aos_inst_strerror(int code) {
  switch (code) {
  case AOS_INST_OK:
    return "Ok";
  case AOS_INST_ERR_FIELD_TYPE:
    return "FieldType";
  case AOS_INST_ERR_PATH_CONFLICT:
    return "PathConflict";
  case AOS_INST_ERR_PATH_NOT_ABSOLUTE:
    return "PathNotAbsolute";
  case AOS_INST_ERR_CWD_MISSING:
    return "CwdMissing";
  case AOS_INST_ERR_OPEN_FAILED:
    return "OpenFailed";
  case AOS_INST_ERR_COMMAND_NOT_FOUND:
    return "CommandNotFound";
  case AOS_INST_ERR_COMMAND_NOT_EXECUTABLE:
    return "CommandNotExecutable";
  case AOS_INST_ERR_LAUNCH_FAILED:
    return "LaunchFailed";
  case AOS_INST_ERR_WAIT_FAILED:
    return "WaitFailed";
  case AOS_INST_ERR_KILL_FAILED:
    return "KillFailed";
  default:
    return "Unknown";
  }
}
