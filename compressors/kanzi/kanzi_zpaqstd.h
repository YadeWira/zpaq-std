/* zpaq-std's C wrapper around kanzi (not part of kanzi). */
#ifndef KANZI_ZPAQSTD_H
#define KANZI_ZPAQSTD_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Compresses src[0..n) at level 1, 2, 5 or 6 into dst: kanzi's headerless stream (one
   thread, no checksum, a single kanzi block). Returns its size, or 0 on failure or
   if it does not fit in dstcap. */
size_t kanzi_zs_compress(const void* src, size_t n, void* dst, size_t dstcap, int level);
/* Decompresses a stream written by kanzi_zs_compress. Returns 0 on success. */
int kanzi_zs_decompress(const void* src, size_t srclen, void* dst, size_t n, int level);
/* preTransformLength of the stream's first block (0 if none). */
size_t kanzi_zs_first_pre(const void* src, size_t srclen);
#ifdef __cplusplus
}
#endif
#endif
