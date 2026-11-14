#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include "global_var.h"
void wrapper_kernel(float*, float*, int64_t, int64_t, int64_t, float*, float*, int64_t, int64_t, int64_t, float*, float*, int64_t, int64_t, int64_t);


int load_arg(void *arg, size_t size, const char *path) {
    int fd = open(path, 0x00000000);
    if (fd == -1) {
        return -1;
    }
    if (read(fd, arg, size) == -1) {
        return -1;
    }
    close(fd);
    return 0;
}

int dump_arg(void *arg, size_t size, const char *path) {
    int fd = open(path, 0x00000001 | 0x00000040, 0644);
    if (fd == -1) {
        return -1;
    }
    if (write(fd, arg, size) == -1) {
        return -1;
    }
    close(fd);
    return 0;
}

int main(int argc, char *argv[]) {

    int* padding = malloc(0x100000ULL * sizeof(int));
    float* c_arg0_1 = malloc(802816ULL);
    float* c_arg1_1 = malloc(524288ULL);
    float* c_buf0 = malloc(3211264ULL);

    if(load_arg(c_arg0_1, (100352ULL * sizeof(float)), argv[1]) == -1){
        return -1;
    }
    if(load_arg(c_arg1_1, (65536ULL * sizeof(float)), argv[2]) == -1){
        return -1;
    }

    wrapper_kernel(c_arg0_1, c_arg0_1, 0, 100352, 1, c_arg1_1, c_arg1_1, 0, 65536, 1, c_buf0, c_buf0, 0, 401408, 1);

    if(dump_arg(c_buf0, (401408ULL * sizeof(float)), argv[3]) == -1){
        return -1;
    }
    return 0;
}
