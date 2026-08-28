#define _POSIX_C_SOURCE 200809L

#include <aos/inst.h>

#include <assert.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* 清掉 aos_deliver_* 測試留下的收件匣：裡面每個投遞都是普通檔案，逐一 unlink
   再把目錄本身刪掉。buffer-too-small 那個案例故意不回報檔名（見下方測試），
   所以不能靠「記得住的名字」逐一 unlink，用列目錄的方式清最直接。 */
static void remove_inbox(const char *inbox_path) {
    DIR *directory = opendir(inbox_path);
    struct dirent *entry;
    char entry_path[600];
    if (directory == NULL) return;
    while ((entry = readdir(directory)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        snprintf(entry_path, sizeof(entry_path), "%s/%s", inbox_path,
                 entry->d_name);
        unlink(entry_path);
    }
    closedir(directory);
    rmdir(inbox_path);
}

int main(void) {
    static const char record[] =
        "{\"argv\":[\"/bin/sh\",\"-c\",\"exit 7\"],"
        "\"cwd\":\"/\",\"env\":{\"AOS_C_TEST\":\"yes\"},"
        "\"timeout_ms\":1000}";
    aos_instruction *instruction = aos_instruction_new();
    aos_instruction *reloaded;
    aos_exec_result result;
    size_t size = 0;
    char *output;
    int fds[2];
    char path[] = "/tmp/aos-capi-XXXXXX";
    int file_fd;

    assert(instruction != NULL);
    assert(strcmp(aos_version_string(), "0.1.0") == 0);

    assert(aos_instruction_read_buffer(record, sizeof(record) - 1,
                                       instruction) == AOS_INST_OK);
    assert(aos_instruction_argc(instruction) == 3);
    assert(strcmp(aos_instruction_arg(instruction, 0), "/bin/sh") == 0);
    assert(strcmp(aos_instruction_field(instruction, AOS_FIELD_CWD), "/") == 0);
    assert(aos_instruction_env_count(instruction) == 1);
    assert(strcmp(aos_instruction_env_key(instruction, 0), "AOS_C_TEST") == 0);
    assert(strcmp(aos_instruction_env_value(instruction, 0), "yes") == 0);
    assert(aos_instruction_timeout_ms(instruction) == 1000);
    assert(aos_instruction_parallel(instruction) == 0);

    assert(aos_instruction_write_buffer(instruction, NULL, 0, &size) ==
           AOS_INST_BUFFER_TOO_SMALL);
    assert(size != 0);
    output = (char *)malloc(size + 1);
    assert(output != NULL);
    assert(aos_instruction_write_buffer(instruction, output, size + 1, &size) ==
           AOS_INST_OK);
    assert(output[size - 1] == '\n');
    assert(output[size] == '\0');
    free(output);

    assert(aos_instruction_execute(instruction, &result) == AOS_EXEC_OK);
    assert(result.status == 7);
    assert(result.signalled == 0);
    assert(result.timed_out == 0);

    aos_instruction_clear(instruction);
    assert(aos_instruction_push_arg(instruction, "echo") == AOS_INST_OK);
    assert(aos_instruction_set_field(instruction, AOS_FIELD_STDIN, "in") == AOS_INST_OK);
    assert(aos_instruction_set_field(instruction, AOS_FIELD_STDOUT, "out") == AOS_INST_OK);
    assert(aos_instruction_set_field(instruction, AOS_FIELD_STDERR, "err") == AOS_INST_OK);
    assert(aos_instruction_stderr_merge(instruction) == 0);
    assert(aos_instruction_set_stderr_merge(instruction, 1) == AOS_INST_OK);
    assert(aos_instruction_stderr_merge(instruction) == 1);
    assert(strcmp(aos_instruction_field(instruction, AOS_FIELD_STDERR), "") == 0);
    assert(aos_instruction_set_stderr_merge(instruction, 0) == AOS_INST_OK);
    assert(aos_instruction_stderr_merge(instruction) == 0);
    assert(aos_instruction_set_field(instruction, AOS_FIELD_EXIT, "status") == AOS_INST_OK);
    assert(aos_instruction_set_field(instruction, AOS_FIELD_CWD, "/tmp") == AOS_INST_OK);
    assert(aos_instruction_set_env(instruction, "KEY", "value") == AOS_INST_OK);
    assert(aos_instruction_set_timeout_ms(instruction, 42) == AOS_INST_OK);
    assert(aos_instruction_set_parallel(instruction, 1) == AOS_INST_OK);
    assert(aos_instruction_parallel(instruction) == 1);
    aos_instruction_clear(instruction);
    assert(aos_instruction_parallel(instruction) == 0);

    assert(pipe(fds) == 0);
    assert(write(fds[1], record, sizeof(record) - 1) == (ssize_t)(sizeof(record) - 1));
    assert(close(fds[1]) == 0);
    assert(aos_instruction_read_fd(fds[0], instruction) == AOS_INST_OK);
    assert(close(fds[0]) == 0);

    file_fd = mkstemp(path);
    assert(file_fd >= 0);
    assert(close(file_fd) == 0);

    assert(aos_instruction_read_buffer(record, sizeof(record) - 1,
                                       instruction) == AOS_INST_OK);
    assert(aos_instruction_write_file(instruction, path) == AOS_INST_OK);

    reloaded = aos_instruction_new();
    assert(reloaded != NULL);
    assert(aos_instruction_read_file(path, reloaded) == AOS_INST_OK);
    assert(aos_instruction_argc(reloaded) == 3);
    assert(strcmp(aos_instruction_arg(reloaded, 2), "exit 7") == 0);
    assert(aos_instruction_timeout_ms(reloaded) == 1000);

    assert(aos_instruction_read_file(NULL, reloaded) == AOS_INST_INVALID_ARGUMENT);
    assert(aos_instruction_read_file("/nonexistent/aos", reloaded) ==
           AOS_INST_READ_ERROR);

    assert(pipe(fds) == 0);
    assert(aos_instruction_write_fd(instruction, fds[1]) == AOS_INST_OK);
    assert(close(fds[1]) == 0);
    aos_instruction_clear(reloaded);
    assert(aos_instruction_read_fd(fds[0], reloaded) == AOS_INST_OK);
    assert(aos_instruction_argc(reloaded) == 3);
    assert(close(fds[0]) == 0);

    aos_instruction_clear(reloaded);
    assert(aos_instruction_write_file(reloaded, path) == AOS_INST_EMPTY_ARGV);
    assert(aos_instruction_read_file(path, reloaded) == AOS_INST_OK);
    assert(aos_instruction_argc(reloaded) == 3);
    aos_instruction_free(reloaded);
    assert(unlink(path) == 0);

    assert(strcmp(aos_inst_state_string(AOS_INST_JSON_SYNTAX), "JsonSyntax") == 0);
    assert(strcmp(aos_inst_state_string(AOS_INST_WRITE_ERROR), "WriteError") == 0);
    assert(strcmp(aos_exec_state_string(AOS_EXEC_OK), "Ok") == 0);
    aos_instruction_free(instruction);

    /* deliver（SPEC §D-3）的 C ABI：投遞→檔案存在→名字回傳。 */
    {
        static const char delivery[] = "{\"argv\":[\"echo\"]}";
        static const char bad_delivery[] = "{\"nope\":1}";
        char world[] = "/tmp/aos-capi-deliver-XXXXXX";
        char missing_world[] = "/tmp/aos-capi-missing-XXXXXX";
        char inbox_path[600];
        char base_path[600];
        char missing_base[700];
        char delivery_file[] = "/tmp/aos-capi-deliver-file-XXXXXX";
        char delivered_path[900];
        char name[AOS_DELIVER_NAME_MAX];
        char tiny[1];
        size_t needed;
        int delivery_fd;
        aos_deliver_result deliver_result;

        assert(mkdtemp(world) != NULL);
        snprintf(inbox_path, sizeof(inbox_path), "%s/inst.tempd", world);
        snprintf(base_path, sizeof(base_path), "%s/inst.json", world);
        assert(mkdir(inbox_path, 0700) == 0);

        /* 缺 instruction_path 是純參數錯誤，不投遞。 */
        needed = 12345;
        assert(aos_deliver_buffer(NULL, delivery, sizeof(delivery) - 1, name,
                                  sizeof(name), &needed, &deliver_result) ==
               AOS_HANDOFF_INVALID_ARGUMENT);
        assert(needed == 0);

        /* 正常投遞一次：狀態、筆數、檔名、檔案都要對得上。 */
        memset(name, 0, sizeof(name));
        assert(aos_deliver_buffer(base_path, delivery, sizeof(delivery) - 1,
                                  name, sizeof(name), &needed,
                                  &deliver_result) == AOS_HANDOFF_OK);
        assert(needed == strlen(name));
        assert(needed > 0);
        assert(deliver_result.count == 1);
        snprintf(delivered_path, sizeof(delivered_path), "%s/%s", inbox_path,
                 name);
        assert(access(delivered_path, F_OK) == 0);

        /* buffer 太小：投遞真的發生了（跟兩段式探大小不同），只是報不出名字。
           不能因為看到 BUFFER_TOO_SMALL 就重打一次，重打會多投一份——這裡驗證
           的是「投遞已完成」這件事，不是重試。 */
        needed = 0;
        assert(aos_deliver_buffer(base_path, delivery, sizeof(delivery) - 1,
                                  tiny, sizeof(tiny), &needed,
                                  &deliver_result) ==
               AOS_HANDOFF_BUFFER_TOO_SMALL);
        assert(needed > 0);
        assert(deliver_result.count == 1);

        /* 壞投遞：唯一 parser 擋下，不寫任何檔案，錯誤原因照實回報。 */
        needed = 12345;
        assert(aos_deliver_buffer(base_path, bad_delivery,
                                  sizeof(bad_delivery) - 1, name, sizeof(name),
                                  &needed, &deliver_result) ==
               AOS_HANDOFF_DELIVERY_INVALID);
        assert(needed == 0);
        assert(deliver_result.inst_state == AOS_INST_UNKNOWN_KEY);
        assert(deliver_result.error_record == 1);

        /* aos_deliver_file：同一份內容改從檔案投遞。 */
        delivery_fd = mkstemp(delivery_file);
        assert(delivery_fd >= 0);
        assert(write(delivery_fd, delivery, sizeof(delivery) - 1) ==
               (ssize_t)(sizeof(delivery) - 1));
        assert(close(delivery_fd) == 0);
        memset(name, 0, sizeof(name));
        assert(aos_deliver_file(base_path, delivery_file, name, sizeof(name),
                                &needed, &deliver_result) == AOS_HANDOFF_OK);
        assert(needed == strlen(name));
        assert(deliver_result.count == 1);
        snprintf(delivered_path, sizeof(delivered_path), "%s/%s", inbox_path,
                 name);
        assert(access(delivered_path, F_OK) == 0);
        assert(unlink(delivery_file) == 0);

        /* 來源檔案讀不到：不是「投遞協定」失敗，是「來源」讀不到，回報要分開。 */
        assert(aos_deliver_file(base_path, "/nonexistent/aos-delivery", name,
                                sizeof(name), &needed, &deliver_result) ==
               AOS_HANDOFF_READ_ERROR);

        /* 收件匣不存在＝世界沒被 aos init 過：deliver MUST NOT 自動建世界。 */
        assert(mkdtemp(missing_world) != NULL);
        snprintf(missing_base, sizeof(missing_base), "%s/inst.json",
                 missing_world);
        assert(aos_deliver_buffer(missing_base, delivery, sizeof(delivery) - 1,
                                  name, sizeof(name), &needed,
                                  &deliver_result) ==
               AOS_HANDOFF_INBOX_READ_FAILED);
        assert(rmdir(missing_world) == 0);

        assert(strcmp(aos_handoff_state_string(AOS_HANDOFF_OK), "Ok") == 0);
        assert(strcmp(aos_handoff_state_string(AOS_HANDOFF_DELIVERY_INVALID),
                      "DeliveryInvalid") == 0);
        assert(strcmp(aos_handoff_state_string(AOS_HANDOFF_BUFFER_TOO_SMALL),
                      "BufferTooSmall") == 0);

        remove_inbox(inbox_path);
        assert(rmdir(world) == 0);
    }

    return 0;
}
