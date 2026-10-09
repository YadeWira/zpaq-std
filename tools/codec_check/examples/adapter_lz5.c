/* codec_check adapter for LZ5 / lz5-ex, as bundled in compressors/lz5. Build from the
   repository root:
     cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Icompressors/lz5 \
        -Itools/codec_check tools/codec_check/codec_check.c \
        tools/codec_check/examples/adapter_lz5.c \
        compressors/lz5/lz5.c compressors/lz5/lz5hc.c -o codec_check_lz5 */
#include "codec_check.h"
#include "lz5.h"
#include "lz5hc.h"

const char* cc_name = "lz5 (level 0 = LZ5_compress_fast, 1-15 = HC)";
const int cc_levels[] = { 0, 1, 3, 4, 5, 9, 11, 15 };
const int cc_nlevels = sizeof(cc_levels) / sizeof(cc_levels[0]);

size_t cc_bound(size_t n) { return (size_t)LZ5_compressBound((int)n); }

long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
  int r = level == 0 ? LZ5_compress_fast((const char*)src, (char*)dst, (int)n, (int)cap, 1)
                     : LZ5_compress_HC((const char*)src, (char*)dst, (int)n, (int)cap, level);
  return r > 0 ? r : -1;
}

long cc_decompress(const void* src, size_t n, void* dst, size_t cap) {
  int r = LZ5_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
  return r >= 0 ? r : -1;
}
