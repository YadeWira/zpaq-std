/* Standalone self-test for the vendored preflate library + the PCF file container.
   For each input file: run pcf_file_encode (gzip/zlib/raw-deflate detection +
   preflate) then pcf_file_decode, and assert the result is BYTE-IDENTICAL to the
   original. Proves the whole -pc whole-file path in isolation, before it is wired
   into add()/extract(). Not part of the zpaq-std build. */
#include <cstdio>
#include <cstdint>
#include <vector>
#include "pcf_wrapper.h"

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
  int failures = 0, encoded = 0, skipped = 0;
  for (int i = 1; i < argc; ++i) {
    std::vector<unsigned char> orig;
    if (!loadfile(orig, argv[i])) { printf("LOAD FAIL %s\n", argv[i]); failures++; continue; }

    std::vector<unsigned char> pcf;
    if (!pcf_file_encode(orig, pcf)) {
      printf("%-28s orig=%-9zu  NOT-RECOMPRESSIBLE -> store verbatim\n", argv[i], orig.size());
      skipped++;
      continue;
    }
    std::vector<unsigned char> back;
    bool dec = pcf_file_decode(pcf, back);
    bool identical = dec && (back == orig);
    printf("%-28s orig=%-9zu pcf=%-9zu (%+5.1f%%)  %s\n",
           argv[i], orig.size(), pcf.size(),
           100.0 * ((double)pcf.size() - orig.size()) / (orig.size() ? orig.size() : 1),
           identical ? "ROUND-TRIP BIT-EXACT OK" : "MISMATCH!!!");
    if (!identical) failures++; else encoded++;
  }
  printf("\nSELFTEST: %d ok, %d skipped, %d FAILURE(S)\n", encoded, skipped, failures);
  return failures ? 1 : 0;
}
