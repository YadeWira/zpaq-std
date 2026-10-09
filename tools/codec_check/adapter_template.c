/* Adapter template for codec_check: replace the calls marked "your library" with your
   codec's API. One shot, buffer to buffer, as zpaq-std calls it. */
#include "codec_check.h"
#include "mycodec.h"                      /* your library */

const char* cc_name = "mycodec";
const int cc_levels[] = { 1, 5, 9 };      /* the levels you expose */
const int cc_nlevels = sizeof(cc_levels) / sizeof(cc_levels[0]);

size_t cc_bound(size_t n) {
  return mycodec_bound(n);                /* your library */
}

long cc_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
  long r = mycodec_compress(src, n, dst, cap, level);   /* your library */
  return r > 0 ? r : -1;
}

long cc_decompress(const void* src, size_t n, void* dst, size_t cap) {
  long r = mycodec_decompress(src, n, dst, cap);        /* your library */
  return r >= 0 ? r : -1;
}
