/* Minimal one-shot buffer<->buffer wrapper around the public-domain Ppmd7
   (PPMd var.H, 7-Zip / LZMA SDK). For use as a zpaq-std -ma:ppmd codec.
   `order` (2..64) and `mem_mb` MUST match between compress and decompress. */
#ifndef PPMD_WRAPPER_H
#define PPMD_WRAPPER_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Compress src[0..srclen) into dst (capacity dstcap). Returns the compressed
   size, or 0 on failure / if it would not fit in dstcap. */
size_t ppmd_compress(const unsigned char* src, size_t srclen,
                     unsigned char* dst, size_t dstcap,
                     unsigned order, unsigned mem_mb);

/* Decompress srclen bytes into dst[0..dstlen). Returns 1 on success, 0 on error. */
int ppmd_decompress(const unsigned char* src, size_t srclen,
                    unsigned char* dst, size_t dstlen,
                    unsigned order, unsigned mem_mb);

#ifdef __cplusplus
}
#endif
#endif
