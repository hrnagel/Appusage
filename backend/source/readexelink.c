#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>

int main(int argc, char *argv[]) {
    pid_t pid;
    char path[PATH_MAX];
    char proc_path[64];
    ssize_t len;

    // Use PID from command-line argument, or default to current process (/proc/self/exe)
    if (argc > 1) {
        pid = (pid_t)atoi(argv[1]);
    } else {
        pid = getpid();
    }

    // Build the /proc/pid/exe path
    snprintf(proc_path, sizeof(proc_path), "/proc/%d/exe", pid);

    // Read the symbolic link
    len = readlink(proc_path, path, sizeof(path) - 1);
    if (len == -1) {
        perror("readlink");
        return EXIT_FAILURE;
    }

    // Null-terminate the string returned by readlink
    path[len] = '\0';

    printf("%s\n", path);
    return EXIT_SUCCESS;
}
