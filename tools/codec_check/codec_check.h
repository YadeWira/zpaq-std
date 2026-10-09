/* The four things codec_check needs from a codec: fill them in an adapter file (see
   adapter_template.c). Return values follow one rule: the number of bytes written,
   or a negative number on any error. */
#ifndef CODEC_CHECK_H
#define CODEC_CHECK_H
#include <stddef.h>

/* the codec's name, printed in the report */
extern const char* cc_name;
/* the levels to check */
extern const int cc_levels[];
extern const int cc_nlevels;

/* worst-case compressed size of n bytes */
size_t cc_bound(size_t n);
/* compresses n bytes into dst, writing at most cap bytes */
long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level);
/* decompresses n bytes into dst, writing at most cap bytes; cap is the original size */
long cc_decompress(const void* src, size_t n, void* dst, size_t cap);

#ifndef CC_TIMEOUT
#define CC_TIMEOUT 20   /* seconds a single call may take before it counts as a hang */
#endif
#ifndef CC_DAMAGE
#define CC_DAMAGE 200   /* damaged copies per block (an eighth of that for blocks >= 1 MB) */
#endif
#endif
