/* ytool_bridge.h — subprocess bridge from zpaq-std to the `ytool` precompressor
   (open-source FPC recreation of xtool; https://github.com/YadeWira/ytool).

   ytool replaces zpaq-std's old preflate-based `-pc`. It is invoked as an external
   process (it is a Free Pascal binary + a stack of codec .so/.dll, with no clean C
   library to link), through a SINGLE call point here so a future CLI change on
   ytool's side (it is pre-1.0, flags not formally frozen) is a one-line edit.

   Agreed contract with ytool (verified against its source, 2026-07-10):
     encode:  <ytool> precomp -l0 -t1 <in> <out>     (-l0 = store, no final lzma2;
              -t1 = single-thread => deterministic; no -dd => dedup left to zpaq's CDC)
     decode:  <ytool> decode <in> <out>
     version: <ytool> --version                       (prints just e.g. "0.9.7")

   Determinism note: ytool precomp is only deterministic at -t1 (a real race exists
   at -t>1). We always pass -t1 for a stable, dedup-friendly output, and recover
   throughput by running many ytool processes in parallel (one per file) from
   zpaq-std's own prefetch worker pool -- so each file is deterministic AND the
   batch is parallel.

   All functions are safe-by-construction: a file is only ever stored as a ytool
   container if decode(encode(x)) == x was proven byte-for-byte at encode time, and
   the container carries the original's size+CRC32 so extraction re-checks the
   reversed bytes (authenticity by stored hash -- NOT by re-encoding, which would be
   fragile given the -t>1 non-determinism). Anything that fails is stored verbatim. */
#ifndef YTOOL_BRIDGE_H
#define YTOOL_BRIDGE_H

#include <vector>
#include <string>
#include <cstddef>
#include <cstdint>

/* Path to the ytool binary. Resolution order (first non-empty wins):
     1. an explicit path set via ytool_set_binary()
     2. the ZPAQ_YTOOL environment variable
     3. "ytool" (found on PATH)
   Call ytool_set_binary() once at startup if a -ytool<path> CLI option is given. */
void ytool_set_binary(const std::string& path);

/* Override the ytool `precomp` argument string (everything between `precomp` and
   the input/output file names), e.g. from a -ytool:<params> CLI option. The
   default (ytool_default_params) is the codec set plus -l0 (store-only) -t1
   (deterministic). Any override is SAFE: encode verify-then-fallback + the stored
   CRC guarantee a byte-exact round-trip no matter what params are passed -- a poor
   choice only costs compression ratio, never correctness. */
void ytool_set_precomp_params(const std::string& params);
std::string ytool_default_params(void);

/* Thread count for ytool's precomp (`-t<N>`). ytool's precomp output is
   THREAD-COUNT-INVARIANT since ytool commit c052153 (an uninitialized SI.Resource
   was writing stack garbage into the .pmp; fixed) -- verified -t1==-t4==-t8
   byte-for-byte -- so varying N changes ONLY throughput, never the stored bytes,
   and therefore never dedup or correctness. Default 1 (one process per file,
   parallelism across files via the caller's worker pool); the caller may raise it
   for the few-large-files case where pool workers would otherwise sit idle. A value
   <= 0 is treated as 1. Ignored when a -ytool:<params> override already fixes -t. */
void ytool_set_precomp_threads(int n);

/* Cheap DETECT-ONLY probe: how many recompressible streams ytool finds in `data`
   (ytool `precomp -scan`), WITHOUT doing the actual precompression or writing any
   output. Returns the stream count (0 = nothing worth precompressing), or -1 if
   ytool is unavailable / the probe errored / no -m codec set is configured. Used to
   gate CONTAINER files (e.g. a .tar whose first bytes are a tar header, not a codec
   magic) so we only pay the full precomp on files that actually contain streams. */
int ytool_scan_streams(const unsigned char* data, size_t len);

/* Same detect-only probe, but on a file PATH directly (ytool reads the file itself)
   -- avoids loading the whole file into RAM just to decide. Same return contract as
   ytool_scan_streams(). Preferred when the bytes are not already buffered. */
int ytool_scan_streams_path(const char* path);

/* True if the configured ytool binary runs and reports a version. Cached after the
   first successful probe. Query before routing files so the caller can cleanly
   fall back to storing verbatim when ytool is absent. */
bool ytool_available(void);

/* ytool's reported version string (e.g. "0.9.7"), or "" if unavailable. Anchored
   into every container so extraction can warn on a producer/consumer version skew
   (ytool's .pmp format has no version field of its own -- we add the guard). */
std::string ytool_version(void);

/* Turn an original file's bytes into a self-describing ytool container:
     "zYTL" | ver(1) | verstr(len8+bytes) | origsize(varint) | origcrc32(4) | pmp
   Runs `precomp -l0 -t1`, then a full byte-exact verify (decode(container)==original)
   before returning true. Returns false (caller stores verbatim) if ytool is absent,
   finds nothing worth precompressing / does not shrink the eventual work, errors,
   or fails the verify. Never throws. */
bool ytool_file_encode(const std::vector<unsigned char>& original,
                       std::vector<unsigned char>& container_out);

/* Reverse a ytool container to the exact original bytes. Returns true only if the
   buffer is an authentic "zYTL" container AND ytool decode reproduces bytes whose
   size+CRC32 match the values stored in the container (so a verbatim file that
   merely starts with "zYTL", or a container this build/ytool cannot decode, is
   rejected and left untouched). Never throws. */
bool ytool_authentic_reverse(const std::vector<unsigned char>& container,
                             std::vector<unsigned char>& original_out);

/* True if buf begins with the ytool-container magic ("zYTL"). Cheap pre-check. */
bool ytool_is_container(const unsigned char* buf, size_t len);

#endif /* YTOOL_BRIDGE_H */
