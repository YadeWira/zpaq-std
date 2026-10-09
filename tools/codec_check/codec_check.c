/* codec_check: the checks zpaq-std runs on a compressor before bundling it, packaged
   so that a codec's author can run them first.

   Fill in an adapter (see adapter_template.c) with four functions, build it together
   with your library under AddressSanitizer and UndefinedBehaviorSanitizer, and run it
   on a few files:

     cc -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
        codec_check.c my_adapter.c <your library's sources> -o codec_check
     ./codec_check file1 file2 ...

   Every buffer handed to the codec is allocated at its exact size, so a read or write
   one byte past the end is caught by AddressSanitizer (zpaq-std's own buffers have
   spare room, which hides such bugs: two bundled libraries had them).

   For each file, each block size and each level it checks:
     round trip   the block decompresses to the original, from exact-size buffers;
     determinism  two compressions into differently pre-filled buffers give the same
                  bytes (catches uninitialised memory reaching the output);
     output cap   compressing into a buffer one byte smaller than the result fails
                  without writing past it; decompressing into a buffer one byte smaller
                  than the original does too;
     damage       a few hundred damaged copies of the block (flipped bits, overwritten
                  bytes, truncation) decompress without a memory error and without
                  hanging; returning garbage is allowed, crashing is not.

   The exit code is 0 when everything passes. A memory error stops the program with
   AddressSanitizer's report, followed by the check, level and block it happened in.
   This file is part of zpaq-std (MIT license). */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#ifndef _WIN32
#include <unistd.h>
#endif
#include "codec_check.h"

static unsigned long long rng = 0x9E3779B97F4A7C15ULL;
static unsigned rnd(void) {
  rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
  return (unsigned)(rng >> 32);
}

static const char* cur_check = "";
static int cur_level = 0;
static size_t cur_offset = 0;
static const char* cur_file = "";

#ifndef _WIN32
static void on_alarm(int sig) {
  (void)sig;
  printf("\nHANG: %s, level %d, block at %lu of %s: the call did not return in %d s\n",
         cur_check, cur_level, (unsigned long)cur_offset, cur_file, CC_TIMEOUT);
  fflush(stdout);
  _exit(3);
}
#define ARM()    alarm(CC_TIMEOUT)
#define DISARM() alarm(0)
#else
#define ARM()
#define DISARM()
#endif

static unsigned char* xmalloc(size_t n) {
  unsigned char* p = (unsigned char*)malloc(n ? n : 1);
  if (!p) { printf("out of memory (%lu bytes)\n", (unsigned long)n); exit(2); }
  return p;
}

/* Under AddressSanitizer, say where it happened before its report ends the program. */
#if defined(__GNUC__) && !defined(_WIN32)
void __sanitizer_set_death_callback(void (*)(void)) __attribute__((weak));
static void on_death(void) {
  printf("\nMEMORY ERROR: %s, level %d, block at %lu of %s (report above)\n",
         cur_check, cur_level, (unsigned long)cur_offset, cur_file);
  fflush(stdout);
}
#endif

static long failures = 0;
static void fail(const char* what) {
  printf("\nFAIL: %s, level %d, block at %lu of %s\n", what, cur_level,
         (unsigned long)cur_offset, cur_file);
  failures++;
}

/* compresses src into a buffer of exactly the codec's bound; returns an exact-size copy */
static unsigned char* compress_exact(const unsigned char* src, size_t n, int level,
                                     int fill, long* clen) {
  size_t cap = cc_bound(n);
  unsigned char* tmp = xmalloc(cap);
  memset(tmp, fill, cap);
  ARM(); *clen = cc_compress(src, n, tmp, cap, level); DISARM();
  if (*clen <= 0 || (size_t)*clen > cap) { free(tmp); return NULL; }
  unsigned char* out = xmalloc((size_t)*clen);
  memcpy(out, tmp, (size_t)*clen);
  free(tmp);
  return out;
}

static void check_block(const unsigned char* src, size_t n, int level, int damage) {
  long c1, c2;
  cur_level = level;

  cur_check = "round trip (compress)";
  unsigned char* a = compress_exact(src, n, level, 0x00, &c1);
  if (!a) { fail("compression returned an error"); return; }

  cur_check = "round trip (decompress)";
  unsigned char* d = xmalloc(n);
  ARM(); long r = cc_decompress(a, (size_t)c1, d, n); DISARM();
  if (r != (long)n || memcmp(d, src, n)) fail("round trip gives different data");

  cur_check = "determinism";
  unsigned char* b = compress_exact(src, n, level, 0xFF, &c2);
  if (!b || c1 != c2 || memcmp(a, b, (size_t)c1))
    fail("two compressions of the same block differ");
  free(b);

  cur_check = "output cap (compress)";
  if (c1 > 1) {
    unsigned char* small = xmalloc((size_t)c1 - 1);
    ARM(); long s = cc_compress(src, n, small, (size_t)c1 - 1, level); DISARM();
    if (s > 0 && (size_t)s > (size_t)c1 - 1) fail("compression reported more bytes than the cap");
    free(small);
  }
  cur_check = "output cap (decompress)";
  if (n > 1) {
    unsigned char* small = xmalloc(n - 1);
    ARM(); long s = cc_decompress(a, (size_t)c1, small, n - 1); DISARM();
    if (s == (long)n) fail("decompression reported more bytes than the cap");
    free(small);
  }

  cur_check = "damage";
  for (int i = 0; i < damage; i++) {
    size_t len = (size_t)c1;
    int kind = (int)(rnd() % 4);
    if (kind == 3 && len > 1) len = 1 + rnd() % (len - 1);       /* truncated */
    unsigned char* m = xmalloc(len);
    memcpy(m, a, len);
    if (kind == 0 || kind == 3) {                                  /* 1-3 flipped bits */
      int k = 1 + (int)(rnd() % 3);
      while (k--) m[rnd() % len] ^= (unsigned char)(1u << (rnd() % 8));
    } else if (kind == 1) {                                        /* overwritten bytes */
      int k = 1 + (int)(rnd() % 8);
      while (k--) m[rnd() % len] = (unsigned char)rnd();
    } else {                                                       /* damaged header */
      size_t h = len < 16 ? len : 16;
      m[rnd() % h] ^= (unsigned char)(1u << (rnd() % 8));
    }
    ARM(); cc_decompress(m, len, d, n); DISARM();
    free(m);
  }
  free(d);
  free(a);
}

int main(int argc, char** argv) {
  if (argc < 2) {
    printf("usage: %s file...   (codec: %s)\n", argv[0], cc_name);
    return 2;
  }
#ifndef _WIN32
  signal(SIGALRM, on_alarm);
#endif
#if defined(__GNUC__) && !defined(_WIN32)
  if (__sanitizer_set_death_callback) __sanitizer_set_death_callback(on_death);
#endif
  static const size_t sizes[] = { 1, 7, 100, 4096, 65536, 1u << 20, 16u << 20 };
  long blocks = 0;
  for (int f = 1; f < argc; f++) {
    FILE* in = fopen(argv[f], "rb");
    if (!in) { printf("cannot open %s\n", argv[f]); return 2; }
    fseek(in, 0, SEEK_END);
    long fl = ftell(in);
    fseek(in, 0, SEEK_SET);
    if (fl <= 0) { fclose(in); continue; }
    if (fl > (long)(16u << 20)) fl = (long)(16u << 20);
    unsigned char* data = xmalloc((size_t)fl);
    if (fread(data, 1, (size_t)fl, in) != (size_t)fl) { printf("cannot read %s\n", argv[f]); return 2; }
    fclose(in);
    cur_file = argv[f];
    printf("%s (%ld bytes):", argv[f], fl);
    for (unsigned s = 0; s < sizeof(sizes) / sizeof(sizes[0]); s++) {
      size_t bs = sizes[s];
      if (bs > (size_t)fl) bs = (size_t)fl;
      /* small blocks: a few spread over the file; big ones: from the start */
      int count = bs <= 4096 ? 8 : 1;
      for (int k = 0; k < count; k++) {
        size_t off = (count > 1 && (size_t)fl > bs) ? (size_t)(rnd() % ((size_t)fl - bs + 1)) : 0;
        cur_offset = off;
        unsigned char* blk = xmalloc(bs);                      /* exact size */
        memcpy(blk, data + off, bs);
        for (int l = 0; l < cc_nlevels; l++) {
          int dmg = bs >= (1u << 20) ? CC_DAMAGE / 8 : CC_DAMAGE;
          check_block(blk, bs, cc_levels[l], dmg);
          blocks++;
        }
        free(blk);
      }
      printf(" %lu", (unsigned long)bs);
      fflush(stdout);
      if (bs == (size_t)fl) break;
    }
    printf("\n");
    free(data);
  }
  printf("%s: %ld blocks checked at %d level(s), %ld failure(s)\n",
         cc_name, blocks, cc_nlevels, failures);
  return failures ? 1 : 0;
}
