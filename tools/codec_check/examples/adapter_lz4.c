/* codec_check adapter for LZ4, as bundled in compressors/lz4 (-ma:lz4, lz4hc, lz4f). Build
   from the repository root:
     cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Icompressors/lz4 \
        -Itools/codec_check tools/codec_check/codec_check.c \
        tools/codec_check/examples/adapter_lz4.c \
        compressors/lz4/lz4.c compressors/lz4/lz4hc.c -o codec_check_lz4 */
#include "codec_check.h"
#include "lz4.h"
#include "lz4hc.h"

/* as zpaq-std writes them: 0 = LZ4_compress_default, 1-12 = HC level, 100+N = fast with
   acceleration N (-ma:lz4f) */
const char* cc_name = "lz4 (0 = default, 1-12 = HC, 100+N = fast, acceleration N)";
const int cc_levels[] = { 0, 101, 109, 1, 4, 9, 12 };
const int cc_nlevels = sizeof(cc_levels) / sizeof(cc_levels[0]);

size_t cc_bound(size_t n) { return (size_t)LZ4_compressBound((int)n); }

long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
  int r;
  if (level == 0)
    r = LZ4_compress_default((const char*)src, (char*)dst, (int)n, (int)cap);
  else if (level >= 100)
    r = LZ4_compress_fast((const char*)src, (char*)dst, (int)n, (int)cap, level - 100);
  else
    r = LZ4_compress_HC((const char*)src, (char*)dst, (int)n, (int)cap, level);
  return r > 0 ? r : -1;
}

long cc_decompress(const void* src, size_t n, void* dst, size_t cap) {
  int r = LZ4_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
  return r >= 0 ? r : -1;
}
