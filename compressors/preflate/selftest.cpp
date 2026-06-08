/* Phase-0 self-test for the vendored preflate library.
   Proves the core -pc guarantee in isolation: a raw DEFLATE stream can be
   decoded to {unpacked, recon-diff} and then re-encoded BYTE-IDENTICALLY.
   Not part of the zpaq-std build; compiled standalone (see selftest command). */
#include <cstdio>
#include <cstdint>
#include <vector>
#include <string>
#include "preflate_decoder.h"
#include "preflate_reencoder.h"

static bool loadfile(std::vector<unsigned char>& out, const char* fn) {
  FILE* f = fopen(fn, "rb");
  if (!f) return false;
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  out.resize(n);
  bool ok = (n == 0) || (fread(out.data(), 1, n, f) == (size_t)n);
  fclose(f);
  return ok;
}

int main(int argc, char** argv) {
  int failures = 0;
  for (int i = 1; i < argc; ++i) {
    std::vector<unsigned char> deflate_in;
    if (!loadfile(deflate_in, argv[i])) { printf("LOAD FAIL %s\n", argv[i]); failures++; continue; }

    std::vector<unsigned char> unpacked, diff;
    bool dec = preflate_decode(unpacked, diff, deflate_in);
    if (!dec) { printf("DECODE-UNSUPPORTED %s (size=%zu) -> would fall back verbatim\n", argv[i], deflate_in.size()); continue; }

    std::vector<unsigned char> reencoded;
    bool re = preflate_reencode(reencoded, diff, unpacked);
    bool identical = re && (reencoded == deflate_in);

    printf("%s: orig_deflate=%zu unpacked=%zu recon_diff=%zu  reencode=%s  %s\n",
           argv[i], deflate_in.size(), unpacked.size(), diff.size(),
           re ? "ok" : "FAIL",
           identical ? "BIT-EXACT OK" : "MISMATCH!!!");
    if (!identical) failures++;
  }
  printf(failures ? "\nSELFTEST: %d FAILURE(S)\n" : "\nSELFTEST: ALL BIT-EXACT\n", failures);
  return failures ? 1 : 0;
}
