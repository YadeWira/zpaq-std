/* pcf_wrapper.cpp — implementation of the collision-free preflate bridge.
   This is the ONLY translation unit that includes preflate headers. */
#include "pcf_wrapper.h"
#include <cstdint>
#include <algorithm>
#include <utility>
#include "preflate_decoder.h"
#include "preflate_reencoder.h"
#include "support/memstream.h"
#include "support/task_pool.h"
#include "zlib.h"   // vendored stock zlib (Z_PREFIX => z_* symbols). Included LAST so its
                    // function-like macros (deflate/inflate/compress...) don't rewrite any
                    // identifiers in the preflate headers above.
#include "packjpglib.h"   // vendored packJPG (LGPL, -DBUILD_LIB): extern "C" pjglib_* API
#include <cstring>
#include <cstdlib>
#include <mutex>
#include <atomic>
#ifdef PACKPNG_AVAILABLE
#include "../packpng/packpng.h"   // vendored packPNG SDK (MIT): extern "C" packpng_* API.
                                   // 64-bit only (see compressors/packpng/README.md); the
                                   // header declares no zlib types, so no symbol exposure
                                   // risk despite this TU's Z_PREFIX zlib above.
#endif

void pcf_set_internal_threads(int extra_threads) {
  globalTaskPool.setExtraThreadLimit(extra_threads < 0 ? 0 : (size_t)extra_threads);
}

bool pcf_deflate_decode(const unsigned char* dfl, size_t deflate_len,
                        std::vector<unsigned char>& unpacked,
                        std::vector<unsigned char>& recon) {
  unpacked.clear();
  recon.clear();
  if (dfl == 0 || deflate_len == 0) return false;
  std::vector<unsigned char> in(dfl, dfl + deflate_len);
  try {
    if (!preflate_decode(unpacked, recon, in)) return false;
  } catch (...) {
    return false;
  }
  return true;
}

bool pcf_deflate_reencode(const std::vector<unsigned char>& unpacked,
                          const std::vector<unsigned char>& recon,
                          std::vector<unsigned char>& deflate_out) {
  deflate_out.clear();
  try {
    if (!preflate_reencode(deflate_out, recon, unpacked)) return false;
  } catch (...) {
    return false;
  }
  return true;
}

/* ---------------- zlib fast-path (stock zlib re-deflate) ----------------

   Most real-world DEFLATE streams (PNG IDAT, PDF FlateDecode, gzip, ZIP) were
   produced by stock zlib. Re-deflating the inflated bytes at the right
   level/memLevel/strategy reproduces the original byte-for-byte and is far cheaper
   than preflate's statistical analysis — so we try it FIRST and only fall back to
   preflate for streams no standard config reproduces. Reconstruction stores just the
   3-byte config + the inflated bytes; on decode we re-deflate with that config. */

/* Inflate a raw (headerless, wbits=-15) DEFLATE stream into raw_out. `n` is the max
   bytes available; the actual DEFLATE may be shorter (e.g. a PNG IDAT has a trailing
   adler32). On success *consumed (if non-NULL) = exact DEFLATE byte length used. */
static bool zlib_inflate_raw(const unsigned char* d, size_t n, std::vector<unsigned char>& raw_out,
                             size_t* consumed = NULL) {
  raw_out.clear();
  z_stream s; memset(&s, 0, sizeof s);
  if (inflateInit2(&s, -15) != Z_OK) return false;
  size_t in_off = 0;
  unsigned char buf[1 << 16];
  int ret = Z_OK;
  do {
    if (s.avail_in == 0 && in_off < n) {
      size_t chunk = n - in_off; if (chunk > (1u << 30)) chunk = (1u << 30);
      s.next_in = (Bytef*)(d + in_off); s.avail_in = (uInt)chunk; in_off += chunk;
    }
    s.next_out = buf; s.avail_out = sizeof buf;
    ret = inflate(&s, Z_NO_FLUSH);
    if (ret != Z_OK && ret != Z_STREAM_END && ret != Z_BUF_ERROR) { inflateEnd(&s); return false; }
    raw_out.insert(raw_out.end(), buf, buf + (sizeof buf - s.avail_out));
    if (ret == Z_BUF_ERROR && s.avail_in == 0 && in_off >= n) { inflateEnd(&s); return false; } // truncated
  } while (ret != Z_STREAM_END);
  if (consumed) *consumed = (size_t)s.total_in;
  inflateEnd(&s);
  return true;
}

/* Deflate `raw` raw (wbits=-15) at one config into out. */
static bool zlib_deflate_raw(const std::vector<unsigned char>& raw,
                             int level, int memLevel, int strategy,
                             std::vector<unsigned char>& out) {
  out.clear();
  if (raw.size() >= (size_t)0x7fffffffu) return false;   // one-shot deflate is uInt-bounded
  z_stream s; memset(&s, 0, sizeof s);
  if (deflateInit2(&s, level, Z_DEFLATED, -15, memLevel, strategy) != Z_OK) return false;
  out.resize((size_t)deflateBound(&s, (uLong)raw.size()) + 64);
  s.next_in = (Bytef*)(raw.empty() ? (const Bytef*)"" : raw.data()); s.avail_in = (uInt)raw.size();
  s.next_out = out.data(); s.avail_out = (uInt)out.size();
  int ret = deflate(&s, Z_FINISH);
  size_t olen = out.size() - s.avail_out;
  deflateEnd(&s);
  if (ret != Z_STREAM_END) return false;
  out.resize(olen);
  return true;
}

/* Try to reproduce the raw DEFLATE stream [d,d+dn) by inflating it and re-deflating
   at stock-zlib configs (curated by real-world frequency, early-exit on byte match).
   On success: raw_out = inflated bytes, *_out = the winning config. */
/* Size gate: only attempt the fast-path on streams whose inflated size is <= this.
   A MISS re-deflates the inflated data once per config tried; on a large stream that
   is far costlier than just running preflate. Small streams (the bulk of PNG IDAT /
   PDF FlateDecode members) keep miss cost tiny; large streams go straight to preflate. */
static const size_t PCF_ZLIB_MAX_RAW = 1u << 20;   /* 1 MiB inflated */

/* Core: inflate up to `avail` bytes (DEFLATE may be shorter), then re-deflate at the
   curated config grid; on byte-exact match set consumed = exact DEFLATE length used. */
static bool zlib_match_sized(const unsigned char* d, size_t avail, size_t& consumed,
                             std::vector<unsigned char>& raw_out,
                             int& level_out, int& memLevel_out, int& strategy_out) {
  consumed = 0;
  if (!zlib_inflate_raw(d, avail, raw_out, &consumed)) return false;
  if (raw_out.size() > PCF_ZLIB_MAX_RAW) return false;                  // size gate: bound miss cost
  /* curated grid (~12 configs): only levels/strategies that win in practice
     (RLE/Huffman-only never reproduce real streams). Early-exit on first byte match. */
  static const int levels[]     = {6, 9, 7, 8, 5, 1};
  static const int strategies[] = {Z_DEFAULT_STRATEGY, Z_FILTERED};
  std::vector<unsigned char> out;
  for (size_t li = 0; li < sizeof(levels) / sizeof(levels[0]); ++li)
    for (size_t si = 0; si < sizeof(strategies) / sizeof(strategies[0]); ++si) {
      if (!zlib_deflate_raw(raw_out, levels[li], 8, strategies[si], out)) continue;
      if (out.size() == consumed && memcmp(out.data(), d, consumed) == 0) {
        level_out = levels[li]; memLevel_out = 8; strategy_out = strategies[si];
        return true;
      }
    }
  return false;
}

/* Whole-region match: the slice [d,d+dn) is exactly one DEFLATE stream. */
static bool zlib_match(const unsigned char* d, size_t dn,
                       std::vector<unsigned char>& raw_out,
                       int& level_out, int& memLevel_out, int& strategy_out) {
  if (dn > (PCF_ZLIB_MAX_RAW + (PCF_ZLIB_MAX_RAW >> 1))) return false;  // deflate can't be >> raw; cheap pre-gate (skip inflate)
  size_t consumed = 0;
  if (!zlib_match_sized(d, dn, consumed, raw_out, level_out, memLevel_out, strategy_out)) return false;
  return consumed == dn;   // must consume the whole slice (no trailing bytes)
}

/* ---------------- packJPG (lossless JPEG recompression, -sa) ----------------
   packJPG converts jpg<->pjg in memory (direction auto-detected from content). Its
   engine uses file-scope (static) globals per conversion, so it is NOT reentrant:
   all pjglib calls are serialised on one mutex (encode at add time, decode in the
   parallel extract reverse). packJPG's own intra-file (Y/Cb/Cr) threads still run
   inside the lock, so a single large JPEG is not single-threaded. */
static std::mutex g_pjg_mx;

/* one-time, single-threaded init of packJPG threading + bomb guard. */
void pcf_packjpg_init(int intra_threads, int max_output_mb) {
  std::lock_guard<std::mutex> lk(g_pjg_mx);
  pjglib_set_inter_file_threads(1);                 // WE serialise across files (mutex)
  pjglib_set_intra_file_threads(intra_threads);     // 0=auto, 1=off, >=3 = N within one file
  if (max_output_mb > 0) pjglib_set_max_output_size((unsigned int)max_output_mb << 20);
}

/* mem->mem packJPG (jpg->pjg at encode, pjg->jpg at decode). Serialised. */
static bool pjg_convert(const unsigned char* in, size_t in_size, std::vector<unsigned char>& out) {
  out.clear();
  if (!in || in_size == 0 || in_size > 0x7fffffffu) return false;
  std::lock_guard<std::mutex> lk(g_pjg_mx);
  pjglib_init_streams((void*)in, 1 /*memory*/, (int)in_size, NULL, 1 /*memory*/);
  unsigned char* o = NULL; unsigned int os = 0; char msg[256] = {0};
  bool ok = pjglib_convert_stream2mem(&o, &os, msg);
  if (!ok || o == NULL || os == 0) { if (o) free(o); return false; }
  out.assign(o, o + os);
  free(o);
  return true;
}

/* ---------------- packPNG (lossless PNG/APNG recompression, -sa) ----------------
   packPNG's vendored SDK (compressors/packpng/, 64-bit only -- see its README) is
   built for AVX2; calling into it on a CPU without AVX2 would SIGILL. Checked via
   CPUID + OSXSAVE + XGETBV -- the same idiom as zpaq-std.cpp's own ihavehw() SHA-NI
   check, duplicated here since this TU is a self-contained bridge that never
   includes zpaq-std.cpp. GCC/Clang inline asm only: this codebase's Windows builds
   are mingw-compiled (g++/gcc), never MSVC, so no intrinsic-based fallback is
   needed. Cached after first call (function-local static = thread-safe one-time
   init, C++11). packPNG's own docs claim its encoder is reentrant/thread-safe
   (unlike packJPG above, no mutex here) -- verified with ThreadSanitizer before
   shipping this. */
#ifdef PACKPNG_AVAILABLE
static bool cpu_has_avx2_uncached() {
  uint32_t eax, ebx, ecx, edx;
  eax = 0; ecx = 0;
  __asm__ __volatile__ ("cpuid" : "+a"(eax), "=b"(ebx), "+c"(ecx), "=d"(edx));
  if (eax < 7) return false;
  eax = 1; ecx = 0;
  __asm__ __volatile__ ("cpuid" : "+a"(eax), "=b"(ebx), "+c"(ecx), "=d"(edx));
  if (!(ecx & (1u << 27))) return false;               /* OSXSAVE */
  uint32_t xcr0_lo, xcr0_hi;
  __asm__ __volatile__ ("xgetbv" : "=a"(xcr0_lo), "=d"(xcr0_hi) : "c"(0));
  if ((xcr0_lo & 0x6u) != 0x6u) return false;           /* OS saves XMM+YMM state */
  eax = 7; ecx = 0;
  __asm__ __volatile__ ("cpuid" : "+a"(eax), "=b"(ebx), "+c"(ecx), "=d"(edx));
  return (ebx & (1u << 5)) != 0;                          /* AVX2 */
}
#endif

bool pcf_packpng_supported(void) {
#ifdef PACKPNG_AVAILABLE
  static const bool ok = cpu_has_avx2_uncached();
  return ok;
#else
  return false;
#endif
}

/* Count of PCF_SEG_PACKPNG segments that could NOT be reversed because this
   build/CPU lacks packPNG support. Lets extraction print one accurate note only
   when such content was actually encountered (not merely because the build is
   incapable -- most archives contain no packPNG content at all). Atomic: the
   extraction reverse pool decodes files from several threads. */
static std::atomic<long> g_packpng_skipped(0);
long pcf_packpng_skipped(void) { return g_packpng_skipped.load(); }

/* Cap packPNG's internal worker threads (0 = its default = hardware threads).
   packPNG multithreads internally by default; when zpaq-std's own pools are the
   parallelism axis (the add()-side prefetch pool, the extraction reverse pool),
   each of up to dozens of pool workers spawning hardware-threads-many internal
   threads oversubscribes the box by orders of magnitude -- same policy problem
   as preflate's globalTaskPool (pcf_set_internal_threads) and packJPG's
   inter-file threads (pcf_packjpg_init). Call single-threaded at setup. */
void pcf_packpng_set_threads(int n) {
#ifdef PACKPNG_AVAILABLE
  packpng_set_threads(n < 0 ? 0 : n);
#else
  (void)n;
#endif
}

/* mem->mem packPNG (png/apng -> .ppg at encode, .ppg -> original at decode). */
#ifdef PACKPNG_AVAILABLE
static bool packpng_compress(const unsigned char* in, size_t in_size,
                             std::vector<unsigned char>& out) {
  out.clear();
  if (!pcf_packpng_supported()) return false;
  unsigned char* o = NULL; size_t osz = 0;
  int rc = packpng_compress_mem(in, in_size, NULL, &o, &osz, PACKPNG_TCIP);
  if (rc != 0 || o == NULL || osz == 0) { if (o) packpng_free(o); return false; }
  out.assign(o, o + osz);
  packpng_free(o);
  return true;
}
static bool packpng_decompress(const unsigned char* in, size_t in_size,
                               std::vector<unsigned char>& out) {
  out.clear();
  if (!pcf_packpng_supported()) return false;
  unsigned char* o = NULL; size_t osz = 0;
  int rc = packpng_decompress_mem(in, in_size, &o, &osz);
  /* osz==0 rejected like in packpng_compress: no valid original PNG is empty
     (the 8-byte signature alone), so an empty "success" is a library anomaly. */
  if (rc != 0 || o == NULL || osz == 0) { if (o) packpng_free(o); return false; }
  out.assign(o, o + osz);
  packpng_free(o);
  return true;
}
#endif

/* ---------------- File-level PCF container ---------------- */

static const unsigned char PCF_MAGIC[4] = { 'z', 'P', 'C', 'F' };
static const unsigned char PCF_VERSION  = 1;
enum { PCF_SEG_LITERAL = 0, PCF_SEG_DEFLATE = 1, PCF_SEG_ZLIBRAW = 3, PCF_SEG_PACKJPG = 4,
       PCF_SEG_PACKPNG = 5 };

/* -pc speed: DEFLATE streams smaller than this (compressed bytes) are NOT
   recompressed — they cost the full preflate analyze + verify pass but save
   almost nothing, so storing them verbatim (literal segment) is much faster at
   negligible ratio cost. Reconstruction is unaffected (these were never
   transformed). */
static const size_t PCF_MIN_DEFLATE = 4096;

static void put_varint(std::vector<unsigned char>& v, uint64_t x) {
  while (x >= 0x80) { v.push_back((unsigned char)(x | 0x80)); x >>= 7; }
  v.push_back((unsigned char)x);
}
/* returns false on malformed/truncated varint */
static bool get_varint(const unsigned char* p, size_t len, size_t& pos, uint64_t& out) {
  out = 0; int shift = 0;
  while (pos < len) {
    unsigned char b = p[pos++];
    out |= (uint64_t)(b & 0x7f) << shift;
    if (!(b & 0x80)) return true;
    shift += 7;
    if (shift > 63) return false;
  }
  return false;
}

bool pcf_is_container(const unsigned char* buf, size_t len) {
  return buf && len >= 5 && buf[0] == PCF_MAGIC[0] && buf[1] == PCF_MAGIC[1]
      && buf[2] == PCF_MAGIC[2] && buf[3] == PCF_MAGIC[3];
}

/* Locate the raw-DEFLATE payload region [d0, d1) inside a gzip/zlib container.
   On success sets d0/d1 and returns true; container header is [0,d0), trailer is
   [d1,len). Returns false if not a recognised wrapper. */
static bool locate_payload(const std::vector<unsigned char>& f, size_t& d0, size_t& d1) {
  const size_t n = f.size();
  /* gzip: 1f 8b 08 */
  if (n >= 18 && f[0] == 0x1f && f[1] == 0x8b && f[2] == 0x08) {
    unsigned char flg = f[3];
    size_t p = 10;
    if (flg & 0x04) { /* FEXTRA */
      if (p + 2 > n) return false;
      size_t xlen = f[p] | (f[p+1] << 8); p += 2 + xlen;
    }
    if (flg & 0x08) { while (p < n && f[p] != 0) ++p; ++p; } /* FNAME */
    if (flg & 0x10) { while (p < n && f[p] != 0) ++p; ++p; } /* FCOMMENT */
    if (flg & 0x02) { p += 2; }                              /* FHCRC */
    if (p + 8 > n) return false;
    d0 = p; d1 = n - 8; /* trailer = CRC32(4)+ISIZE(4) */
    return d1 > d0;
  }
  /* zlib: CMF FLG, CM=8, (CMF<<8|FLG)%31==0 */
  if (n >= 7 && (f[0] & 0x0f) == 0x08 && ((f[0] << 8 | f[1]) % 31) == 0) {
    size_t p = 2;
    if (f[1] & 0x20) p += 4; /* FDICT */
    if (p + 4 > n) return false;
    d0 = p; d1 = n - 4; /* trailer = adler32(4) */
    return d1 > d0;
  }
  return false;
}

/* Build a PCF stream from already-split (header, deflate, trailer). Returns false if
   the deflate payload is not preflate-able. Does NOT verify (caller does). */
static bool build_pcf(const std::vector<unsigned char>& f, size_t d0, size_t d1,
                      std::vector<unsigned char>& pcf_out) {
  if (d1 <= d0 || d1 - d0 < PCF_MIN_DEFLATE) return false;   // -pc: skip tiny streams
  std::vector<unsigned char> dfl(f.begin() + d0, f.begin() + d1);
  /* zlib fast-path first; preflate is the fallback. */
  std::vector<unsigned char> zraw; int zl = 0, zm = 0, zs = 0;
  bool zfast = zlib_match(dfl.data(), dfl.size(), zraw, zl, zm, zs);
  std::vector<unsigned char> unpacked, recon;
  if (!zfast && !pcf_deflate_decode(dfl.data(), dfl.size(), unpacked, recon)) return false;

  pcf_out.clear();
  pcf_out.insert(pcf_out.end(), PCF_MAGIC, PCF_MAGIC + 4);
  pcf_out.push_back(PCF_VERSION);
  /* segment count: header literal (if any) + deflate + trailer literal (if any) */
  uint64_t nseg = 1 + (d0 > 0 ? 1 : 0) + (d1 < f.size() ? 1 : 0);
  put_varint(pcf_out, nseg);
  if (d0 > 0) {
    pcf_out.push_back(PCF_SEG_LITERAL);
    put_varint(pcf_out, d0);
    pcf_out.insert(pcf_out.end(), f.begin(), f.begin() + d0);
  }
  if (zfast) {
    pcf_out.push_back(PCF_SEG_ZLIBRAW);
    pcf_out.push_back((unsigned char)zl);
    pcf_out.push_back((unsigned char)zm);
    pcf_out.push_back((unsigned char)zs);
    put_varint(pcf_out, zraw.size());
    pcf_out.insert(pcf_out.end(), zraw.begin(), zraw.end());
  } else {
    pcf_out.push_back(PCF_SEG_DEFLATE);
    put_varint(pcf_out, recon.size());
    pcf_out.insert(pcf_out.end(), recon.begin(), recon.end());
    put_varint(pcf_out, unpacked.size());
    pcf_out.insert(pcf_out.end(), unpacked.begin(), unpacked.end());
  }
  if (d1 < f.size()) {
    pcf_out.push_back(PCF_SEG_LITERAL);
    put_varint(pcf_out, f.size() - d1);
    pcf_out.insert(pcf_out.end(), f.begin() + d1, f.end());
  }
  return true;
}

/* ---- Phase 2: embedded-stream scanning (ZIP) ---- */

static uint32_t rd32(const unsigned char* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint16_t rd16(const unsigned char* p) { return (uint16_t)(p[0] | (p[1] << 8)); }

/* Find every DEFLATE member in a ZIP via the central directory (authoritative
   offsets/sizes — avoids data-descriptor ambiguity). Fills `regions` with sorted,
   non-overlapping [start,end) byte spans of raw deflate payloads. */
static bool scan_zip(const std::vector<unsigned char>& f,
                     std::vector<std::pair<size_t, size_t> >& regions) {
  const size_t n = f.size();
  if (n < 22) return false;
  if (!(f[0] == 0x50 && f[1] == 0x4b && f[2] == 0x03 && f[3] == 0x04)) return false;
  /* locate End Of Central Directory (PK\x05\x06) scanning back over the 22-byte
     record + up to 65535-byte comment */
  size_t lim = (n >= (size_t)(22 + 65535)) ? n - 22 - 65535 : 0;
  size_t eocd = 0; bool found = false;
  for (size_t i = n - 22;; --i) {
    if (f[i] == 0x50 && f[i + 1] == 0x4b && f[i + 2] == 0x05 && f[i + 3] == 0x06) { eocd = i; found = true; break; }
    if (i == lim) break;
  }
  if (!found) return false;
  uint16_t total = rd16(&f[eocd + 10]);
  uint32_t cdsize = rd32(&f[eocd + 12]);
  uint32_t cdoff = rd32(&f[eocd + 16]);
  if ((size_t)cdoff + cdsize > n) return false;
  size_t p = cdoff;
  for (uint16_t e = 0; e < total; ++e) {
    if (p + 46 > n) return false;
    if (!(f[p] == 0x50 && f[p + 1] == 0x4b && f[p + 2] == 0x01 && f[p + 3] == 0x02)) return false;
    uint16_t method = rd16(&f[p + 10]);
    uint32_t csize  = rd32(&f[p + 20]);
    uint16_t nlen   = rd16(&f[p + 28]);
    uint16_t elen   = rd16(&f[p + 30]);
    uint16_t clen   = rd16(&f[p + 32]);
    uint32_t lho    = rd32(&f[p + 42]);
    p += (size_t)46 + nlen + elen + clen;
    if (method == 8 && csize > 0 && (size_t)lho + 30 <= n
        && f[lho] == 0x50 && f[lho + 1] == 0x4b && f[lho + 2] == 0x03 && f[lho + 3] == 0x04) {
      uint16_t lnlen = rd16(&f[lho + 26]);
      uint16_t lelen = rd16(&f[lho + 28]);
      size_t dstart = (size_t)lho + 30 + lnlen + lelen;
      size_t dend   = dstart + csize;
      if (dstart < dend && dend <= n) regions.push_back(std::make_pair(dstart, dend));
    }
  }
  std::sort(regions.begin(), regions.end());
  /* drop any overlaps defensively */
  for (size_t i = 1; i < regions.size(); ++i)
    if (regions[i].first < regions[i - 1].second) return false;
  return !regions.empty();
}

/* Decode a DEFLATE stream of UNKNOWN length starting at buf, reporting how many
   bytes were consumed. Uses the streaming preflate API (MemStream). For embedded
   scanning where stream boundaries aren't known up front. */
static bool deflate_decode_sized(const unsigned char* buf, size_t len,
                                 std::vector<unsigned char>& unpacked,
                                 std::vector<unsigned char>& recon,
                                 size_t min_size, size_t& consumed) {
  unpacked.clear(); recon.clear(); consumed = 0;
  if (!buf || len < min_size) return false;
  std::vector<uint8_t> in(buf, buf + len);
  MemStream is(in), os;
  uint64_t dsize = 0;
  try {
    if (!preflate_decode(os, recon, dsize, is, [](){}, min_size)) return false;
  } catch (...) { return false; }
  if (dsize == 0) return false;
  unpacked = os.extractData();
  consumed = (size_t)dsize;
  return true;
}

/* Scan a buffer (e.g. a PDF) for embedded zlib streams (CMF/FLG header with
   CM=8 and (CMF<<8|FLG)%31==0), recompressing the DEFLATE payload of each. The
   returned regions are the raw DEFLATE spans [start,end) (the 2-byte zlib header
   and 4-byte adler stay in surrounding literals). Bounded by a decode-attempt cap.
   verify-then-fallback at the file level makes a wrong guess harmless. */
static bool scan_zlib_streams(const std::vector<unsigned char>& f,
                              std::vector<std::pair<size_t, size_t> >& regions) {
  const size_t n = f.size();
  const size_t MINDEF = 64;       /* ignore tiny would-be streams */
  int attempts = 0, kMaxAttempts = 4096;
  size_t i = 0;
  while (i + 2 < n && attempts < kMaxAttempts) {
    bool zlibhdr = ((f[i] & 0x0f) == 0x08) && ((f[i] & 0x80) == 0)
                   && ((((unsigned)f[i] << 8) | f[i + 1]) % 31 == 0);
    if (!zlibhdr) { ++i; continue; }
    ++attempts;
    std::vector<unsigned char> u, r;
    size_t consumed = 0;
    if (deflate_decode_sized(&f[i + 2], n - (i + 2), u, r, MINDEF, consumed)
        && consumed >= MINDEF && (i + 2 + consumed) <= n) {
      regions.push_back(std::make_pair(i + 2, i + 2 + consumed));
      i = i + 2 + consumed + 4; /* skip header+deflate+adler */
    } else {
      ++i;
    }
  }
  return !regions.empty();
}

/* Build a multi-segment PCF: literal gaps interleaved with recompressed DEFLATE
   regions. Regions that do not preflate-decode are left inside literals. */
static bool build_pcf_multi(const std::vector<unsigned char>& f,
                            const std::vector<std::pair<size_t, size_t> >& regions_in,
                            std::vector<unsigned char>& pcf_out) {
  std::vector<std::pair<size_t, size_t> > regs;
  std::vector<std::vector<unsigned char> > unps, recs;       // unps = zraw (fast) OR unpacked (preflate)
  std::vector<unsigned char> zfast, zl_v, zm_v, zs_v;         // per-region: zlib fast-path? + config
  for (size_t i = 0; i < regions_in.size(); ++i) {
    size_t s = regions_in[i].first, e = regions_in[i].second;
    if (s >= e || e > f.size()) continue;
    if (e - s < PCF_MIN_DEFLATE) continue;   // -pc: skip tiny streams (stay literal)
    std::vector<unsigned char> d(f.begin() + s, f.begin() + e), u, r;
    int zl = 0, zm = 0, zs = 0;
    if (zlib_match(&d[0], d.size(), u, zl, zm, zs)) {         // zlib fast-path first
      regs.push_back(regions_in[i]); unps.push_back(u); recs.push_back(std::vector<unsigned char>());
      zfast.push_back(1); zl_v.push_back((unsigned char)zl); zm_v.push_back((unsigned char)zm); zs_v.push_back((unsigned char)zs);
    } else if (pcf_deflate_decode(&d[0], d.size(), u, r)) {   // preflate fallback
      regs.push_back(regions_in[i]); unps.push_back(u); recs.push_back(r);
      zfast.push_back(0); zl_v.push_back(0); zm_v.push_back(0); zs_v.push_back(0);
    }
  }
  if (regs.empty()) return false;

  std::vector<unsigned char> body;
  uint64_t nseg = 0;
  size_t pos = 0;
  for (size_t i = 0; i < regs.size(); ++i) {
    if (regs[i].first > pos) {
      body.push_back(PCF_SEG_LITERAL);
      put_varint(body, regs[i].first - pos);
      body.insert(body.end(), f.begin() + pos, f.begin() + regs[i].first);
      ++nseg;
    }
    if (zfast[i]) {
      body.push_back(PCF_SEG_ZLIBRAW);
      body.push_back(zl_v[i]); body.push_back(zm_v[i]); body.push_back(zs_v[i]);
      put_varint(body, unps[i].size());
      body.insert(body.end(), unps[i].begin(), unps[i].end());
    } else {
      body.push_back(PCF_SEG_DEFLATE);
      put_varint(body, recs[i].size());
      body.insert(body.end(), recs[i].begin(), recs[i].end());
      put_varint(body, unps[i].size());
      body.insert(body.end(), unps[i].begin(), unps[i].end());
    }
    ++nseg;
    pos = regs[i].second;
  }
  if (pos < f.size()) {
    body.push_back(PCF_SEG_LITERAL);
    put_varint(body, f.size() - pos);
    body.insert(body.end(), f.begin() + pos, f.end());
    ++nseg;
  }
  pcf_out.clear();
  pcf_out.insert(pcf_out.end(), PCF_MAGIC, PCF_MAGIC + 4);
  pcf_out.push_back(PCF_VERSION);
  put_varint(pcf_out, nseg);
  pcf_out.insert(pcf_out.end(), body.begin(), body.end());
  return true;
}

bool pcf_file_decode(const std::vector<unsigned char>& pcf,
                     std::vector<unsigned char>& original_out) {
  original_out.clear();
  const unsigned char* p = pcf.data();
  const size_t n = pcf.size();
  if (!pcf_is_container(p, n)) return false;
  size_t pos = 4;
  if (pos >= n || p[pos++] != PCF_VERSION) return false;
  uint64_t nseg = 0;
  if (!get_varint(p, n, pos, nseg)) return false;
  for (uint64_t s = 0; s < nseg; ++s) {
    if (pos >= n) return false;
    unsigned char kind = p[pos++];
    /* All length checks below use the subtraction form `len > n - pos` (never
       `pos + len > n`): get_varint accepts any 64-bit value, and the addition
       form wraps for a huge crafted len, passing the check and then feeding a
       wrapped end pointer to the vector range constructor (UB / uncaught
       std::length_error -> std::terminate). The stored PCF content comes from
       extracted archive data, i.e. attacker-controllable bytes. pos <= n holds
       after every successful get_varint. */
    if (kind == PCF_SEG_LITERAL) {
      uint64_t len = 0;
      if (!get_varint(p, n, pos, len) || len > n - pos) return false;
      original_out.insert(original_out.end(), p + pos, p + pos + len);
      pos += len;
    } else if (kind == PCF_SEG_ZLIBRAW) {
      /* zlib fast-path: re-deflate the stored inflated bytes with the stored config. */
      if (n - pos < 3) return false;
      int zl = p[pos], zm = p[pos + 1], zs = p[pos + 2]; pos += 3;
      uint64_t ulen = 0;
      if (!get_varint(p, n, pos, ulen) || ulen > n - pos) return false;
      std::vector<unsigned char> raw(p + pos, p + pos + ulen); pos += ulen;
      std::vector<unsigned char> dfl;
      if (!zlib_deflate_raw(raw, zl, zm, zs, dfl)) return false;
      original_out.insert(original_out.end(), dfl.begin(), dfl.end());
    } else if (kind == PCF_SEG_DEFLATE) {
      uint64_t rlen = 0;
      if (!get_varint(p, n, pos, rlen) || rlen > n - pos) return false;
      std::vector<unsigned char> recon(p + pos, p + pos + rlen); pos += rlen;
      uint64_t ulen = 0;
      if (!get_varint(p, n, pos, ulen) || ulen > n - pos) return false;
      std::vector<unsigned char> unpacked(p + pos, p + pos + ulen); pos += ulen;
      std::vector<unsigned char> dfl;
      if (!pcf_deflate_reencode(unpacked, recon, dfl)) return false;
      original_out.insert(original_out.end(), dfl.begin(), dfl.end());
    } else if (kind == PCF_SEG_PACKJPG) {
      uint64_t plen = 0;
      if (!get_varint(p, n, pos, plen) || plen > n - pos) return false;
      std::vector<unsigned char> pjg(p + pos, p + pos + plen); pos += plen;
      std::vector<unsigned char> jpg;
      if (!pjg_convert(pjg.data(), pjg.size(), jpg)) return false;  // pjg -> original jpg
      original_out.insert(original_out.end(), jpg.begin(), jpg.end());
    } else if (kind == PCF_SEG_PACKPNG) {
      uint64_t plen = 0;
      if (!get_varint(p, n, pos, plen) || plen > n - pos) return false;
      if (!pcf_packpng_supported()) {
        /* 32-bit / non-Linux build, or a CPU without AVX2: this segment cannot
           be reversed here. Count it so extraction can print ONE accurate note
           (instead of guessing from build capabilities alone). */
        ++g_packpng_skipped;
        return false;
      }
#ifdef PACKPNG_AVAILABLE
      std::vector<unsigned char> ppg(p + pos, p + pos + plen); pos += plen;
      std::vector<unsigned char> png;
      if (!packpng_decompress(ppg.data(), ppg.size(), png)) return false;  // .ppg -> original png
      original_out.insert(original_out.end(), png.begin(), png.end());
#else
      return false;   // unreachable (pcf_packpng_supported() is false here), kept for clarity
#endif
    } else {
      return false;
    }
  }
  return pos == n;
}

/* JPEG -> single PCF_SEG_PACKJPG segment (the packJPG-compressed bytes). */
static bool build_pcf_packjpg(const std::vector<unsigned char>& f,
                              std::vector<unsigned char>& pcf_out) {
  std::vector<unsigned char> pjg;
  if (!pjg_convert(f.data(), f.size(), pjg)) return false;
  if (pjg.empty()) return false;
  pcf_out.clear();
  pcf_out.insert(pcf_out.end(), PCF_MAGIC, PCF_MAGIC + 4);
  pcf_out.push_back(PCF_VERSION);
  put_varint(pcf_out, 1);                 // one segment
  pcf_out.push_back(PCF_SEG_PACKJPG);
  put_varint(pcf_out, pjg.size());
  pcf_out.insert(pcf_out.end(), pjg.begin(), pjg.end());
  /* gain check on the FINAL container (header included): comparing only the
     payload lets a near-break-even conversion store a few bytes MORE than the
     original. No gain -> store the original verbatim. */
  if (pcf_out.size() >= f.size()) { pcf_out.clear(); return false; }
  return true;
}

#ifdef PACKPNG_AVAILABLE
/* PNG/APNG -> single PCF_SEG_PACKPNG segment (packPNG's TCIP: preflate +
   WebP-lossless). Requires AVX2 -- packpng_compress() checks and returns false
   immediately if absent (file stays untransformed; never a crash). */
static bool build_pcf_packpng(const std::vector<unsigned char>& f,
                              std::vector<unsigned char>& pcf_out) {
  std::vector<unsigned char> ppg;
  if (!packpng_compress(f.data(), f.size(), ppg)) return false;
  if (ppg.empty()) return false;
  pcf_out.clear();
  pcf_out.insert(pcf_out.end(), PCF_MAGIC, PCF_MAGIC + 4);
  pcf_out.push_back(PCF_VERSION);
  put_varint(pcf_out, 1);                 // one segment
  pcf_out.push_back(PCF_SEG_PACKPNG);
  put_varint(pcf_out, ppg.size());
  pcf_out.insert(pcf_out.end(), ppg.begin(), ppg.end());
  /* gain check on the FINAL container (header included) -- see build_pcf_packjpg. */
  if (pcf_out.size() >= f.size()) { pcf_out.clear(); return false; }
  return true;
}
#endif

bool pcf_file_encode(const std::vector<unsigned char>& original,
                     std::vector<unsigned char>& pcf_out) {
  pcf_out.clear();
  if (original.size() < 18) return false; /* too small to be worth it */

  bool built = false;
  std::vector<unsigned char> cand;

  /* ZIP container: recompress every embedded DEFLATE member (Phase 2). */
  if (original.size() >= 22 && original[0] == 0x50 && original[1] == 0x4b
      && original[2] == 0x03 && original[3] == 0x04) {
    std::vector<std::pair<size_t, size_t> > regions;
    if (scan_zip(original, regions))
      built = build_pcf_multi(original, regions, cand);
  }

  /* PDF: scan for embedded zlib (FlateDecode) streams. Gated on the %PDF magic
     so the heuristic zlib scan never runs on arbitrary files. */
  if (!built && original.size() >= 5 && original[0] == '%' && original[1] == 'P'
      && original[2] == 'D' && original[3] == 'F') {
    std::vector<std::pair<size_t, size_t> > regions;
    if (scan_zlib_streams(original, regions))
      built = build_pcf_multi(original, regions, cand);
  }

#ifdef PACKPNG_AVAILABLE
  /* PNG/APNG: lossless WebP-based recompression via packPNG (reached only when
     -sa routes a png/apng; requires AVX2, checked inside build_pcf_packpng). */
  if (!built && original.size() >= 8 && original[0] == 0x89 && original[1] == 0x50
      && original[2] == 0x4e && original[3] == 0x47) {
    built = build_pcf_packpng(original, cand);
  }
#endif

  /* JPEG: lossless recompression via packJPG (reached only when -sa routes a jpg). */
  if (!built && original.size() >= 3 && original[0] == 0xFF && original[1] == 0xD8
      && original[2] == 0xFF) {
    built = build_pcf_packjpg(original, cand);
  }

  /* whole-file gzip / zlib, or raw DEFLATE as a last resort. */
  if (!built) {
    size_t d0 = 0, d1 = 0;
    if (locate_payload(original, d0, d1))
      built = build_pcf(original, d0, d1, cand);
  }
  if (!built) {
    if (build_pcf(original, 0, original.size(), cand)) built = true;
  }
  if (!built) return false;

  /* verify-then-fallback: decode must reproduce the original byte-for-byte */
  std::vector<unsigned char> check;
  if (!pcf_file_decode(cand, check)) return false;
  if (check.size() != original.size()) return false;
  for (size_t i = 0; i < check.size(); ++i)
    if (check[i] != original[i]) return false;

  pcf_out.swap(cand);
  return true;
}

int pcf_authentic_reverse2(const std::vector<unsigned char>& stored,
                           std::vector<unsigned char>& original_out) {
  original_out.clear();
  if (!pcf_is_container(stored.data(), stored.size())) return 1;   /* no zPCF magic */
  std::vector<unsigned char> orig;
  if (!pcf_file_decode(stored, orig)) return 1;   /* magic but does not decode: a
      verbatim user file that happens to start with "zPCF" (by design untouched),
      or an unsupported segment (e.g. packPNG on an incapable build -- counted
      separately via pcf_packpng_skipped) */
  /* authenticity: re-encoding the decoded original must reproduce `stored`
     exactly, otherwise this was not a PCF stream we created (do not touch it).
     A file that DECODES as a valid PCF but fails this re-encode is, with
     near-certainty, a real PCF this build can no longer reproduce (e.g. a future
     vendored-codec update changing encoder output) -- callers should surface
     that loudly instead of silently leaving the container on disk. */
  std::vector<unsigned char> re;
  if (!pcf_file_encode(orig, re)) return 2;
  if (re != stored) return 2;
  original_out.swap(orig);
  return 0;
}

bool pcf_authentic_reverse(const std::vector<unsigned char>& stored,
                           std::vector<unsigned char>& original_out) {
  return pcf_authentic_reverse2(stored, original_out) == 0;
}

/* orig=2352 deflate=133 (raw deflate, wbits=-15, zlib level 6) */
static const unsigned char PCF_TEST_DEFLATE[133] = {
  11,112,118,83,200,204,211,77,202,204,75,44,170,84,40,78,205,73,211,45,73,45,46,177,82,40,
  201,72,85,40,44,205,76,206,86,72,42,202,47,207,83,72,203,175,208,83,8,24,85,61,170,122,84,
  245,168,234,81,213,163,170,71,164,106,6,70,38,102,22,86,54,118,14,78,46,110,30,94,62,126,
  1,65,33,97,17,81,49,113,9,73,41,105,25,89,57,121,5,69,37,101,21,85,53,117,13,77,45,109,29,
  93,61,125,3,67,35,99,19,83,51,115,11,75,43,107,27,91,59,251,81,253,67,91,63,0,
};

bool pcf_autotest() {
  std::vector<unsigned char> unpacked, recon, reencoded;
  if (!pcf_deflate_decode(PCF_TEST_DEFLATE, sizeof(PCF_TEST_DEFLATE), unpacked, recon))
    return false;
  if (!pcf_deflate_reencode(unpacked, recon, reencoded))
    return false;
  if (reencoded.size() != sizeof(PCF_TEST_DEFLATE)) return false;
  for (size_t i = 0; i < reencoded.size(); ++i)
    if (reencoded[i] != PCF_TEST_DEFLATE[i]) return false;
  return true;
}
