#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
void* __wrap_malloc(size_t size) {
    size_t aligned = (size + 511UL) & ~511UL;
    void *p = sbrk(aligned);
    return p;
}
void __wrap_free(void *ptr) { return; }
float X_spad[16] __attribute__ ((section(".spad")));
float W_spad[8] __attribute__ ((section(".spad")));
float Y_spad[16] __attribute__ ((section(".spad")));
int spad_end[0] __attribute__ ((section(".spad")));
int spad_section_end[0] __attribute__ ((section(".spad"), aligned(16777216)));