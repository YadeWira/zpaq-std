/* codec_check adapter for heatshrink-ex, as bundled in compressors/hs (-ma:hs), through
   zpaq-std's own hs_wrapper.c. Build from the repository root:
     cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Icompressors/hs \
        -Itools/codec_check tools/codec_check/codec_check.c \
        tools/codec_check/examples/adapter_hs.c compressors/hs/hs_wrapper.c \
        compressors/hs/heatshrink_encoder.c compressors/hs/heatshrink_decoder.c \
        -o codec_check_hs
   hs_compress_wrapper gives an error when the result is not smaller than the block
   (zpaq-std then stores it), so run it on files that compress: text, executables. */
#include "codec_check.h"
#include "hs_wrapper.h"

/* the -ma:hs levels: window and lookahead bits chosen by hs_wrapper.c */
const char* cc_name = "heatshrink-ex (-ma:hs 0-2)";
const int cc_levels[] = { 0, 1, 2 };
const int cc_nlevels = sizeof(cc_levels) / sizeof(cc_levels[0]);

/* one header byte; heatshrink never grows data by more than one bit in eight */
size_t cc_bound(size_t n) { return n + n / 8 + 16; }

long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
  size_t out = 0;
  if (hs_compress_wrapper((const uint8_t*)src, n, (uint8_t*)dst, cap, &out, level)) return -1;
  return out > 0 ? (long)out : -1;
}

long cc_decompress(const void* src, size_t n, void* dst, size_t cap) {
  size_t out = 0;
  if (hs_decompress_wrapper((const uint8_t*)src, n, (uint8_t*)dst, cap, &out)) return -1;
  return (long)out;
}
