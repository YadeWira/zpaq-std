/* codec_check adapter for LZAV, as bundled in compressors/lzav (-ma:lzav). Build from the
   repository root (LZAV is one header):
     cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Icompressors/lzav \
        -Itools/codec_check tools/codec_check/codec_check.c \
        tools/codec_check/examples/adapter_lzav.c -o codec_check_lzav */
#include "codec_check.h"
#include "lzav.h"

/* as zpaq-std writes them: 0 = lzav_compress_default, 1 = lzav_compress_hi */
const char* cc_name = "lzav (0 = default, 1 = hi)";
const int cc_levels[] = { 0, 1 };
const int cc_nlevels = sizeof(cc_levels) / sizeof(cc_levels[0]);

size_t cc_bound(size_t n) { return (size_t)lzav_compress_bound_hi((int)n) > (size_t)lzav_compress_bound((int)n)
                                   ? (size_t)lzav_compress_bound_hi((int)n) : (size_t)lzav_compress_bound((int)n); }

long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
  int r = level == 0 ? lzav_compress_default(src, dst, (int)n, (int)cap)
                     : lzav_compress_hi(src, dst, (int)n, (int)cap);
  return r > 0 ? r : -1;
}

long cc_decompress(const void* src, size_t n, void* dst, size_t cap) {
  int r = lzav_decompress(src, dst, (int)n, (int)cap);
  return r >= 0 ? r : -1;
}
