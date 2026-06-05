#ifndef HS_WRAPPER_H_
#define HS_WRAPPER_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int hs_compress_wrapper(const uint8_t* in, size_t inlen,
                        uint8_t* out, size_t outcap, size_t* outlen,
                        int level);

int hs_decompress_wrapper(const uint8_t* in, size_t inlen,
                          uint8_t* out, size_t outcap, size_t* produced);

#ifdef __cplusplus
}
#endif

#endif
