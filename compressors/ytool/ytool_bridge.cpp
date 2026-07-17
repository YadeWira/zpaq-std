/* ytool_bridge.cpp — see ytool_bridge.h. Self-contained: std + popen + a small
   CRC-32; no zpaq-std or codec headers, so it is a leaf TU testable on its own. */
#include "ytool_bridge.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <atomic>

#if defined(_WIN32)
#include <process.h>            /* _getpid */
#define YT_POPEN  _popen
#define YT_PCLOSE _pclose
#define YT_GETPID _getpid
#else
#include <unistd.h>            /* getpid, unlink */
#define YT_POPEN  popen
#define YT_PCLOSE pclose
#define YT_GETPID getpid
#endif

/* ---- configured binary path (set once, single-threaded, before any worker) ---- */
static std::string g_ytool_bin;   /* explicit override; else env; else "ytool" */

/* THE single config point for ytool's detector set. ytool needs -m<codecs> or it
   detects nothing (just wraps the file). Broad set covering what -pc handled
   (deflate: gz/zlib/zip/pdf) plus ytool's extra formats. -t1 => deterministic. */
/* PROVISIONAL default. Which codecs WIN is data-dependent (ytool confirmed: no
   universal -m; the deflate family zlib/reflate/preflate can vary 3x, and a fixed
   internal PRIORITY -- not best-result -- picks the winner when several compete
   for one stream, so passing all 3 is pointless). One deflate handler (preflate:
   accurate, byte-exact, what -pc used); brunsli for JPEG (beats packjpg AND has
   priority per ytool's test); packpng for PNG; flac/wavpack help only RAW WAV/PCM,
   not already-compressed .flac (harmless if absent); packmp3; lzo. FINAL choice is
   to be tuned end-to-end against zpaq-std's own -ma backend on a real corpus at
   wire-in -- the "best -m" for us is min FINAL size after OUR backend, not ytool's
   analyze metric (which measures ytool's own lzma2 stage). Correctness is
   -m-independent (verify-then-fallback + stored-CRC guarantee round-trip). */
static const char* const YT_CODECS = "preflate+brunsli+packpng+flac+packmp3+wavpack+lzo1x";

/* The ytool precomp argument string (everything between `precomp` and the file
   names). Default = the codec set + the correctness/determinism invariants
   (-l0 store-only, -t1 deterministic). Overridable via ytool_set_precomp_params()
   from a -ytool:<params> CLI option -- any params are SAFE because encode
   verify-then-fallback + the stored CRC guarantee round-trip regardless; a bad
   choice only costs ratio, never correctness. */
static std::string g_yt_params;   /* empty => the built-in default below */
static int g_yt_threads = 1;      /* -t<N> for the default params; t-invariant output */

void ytool_set_precomp_threads(int n) { g_yt_threads = (n > 0) ? n : 1; }

std::string ytool_default_params(void) {
  char t[16]; snprintf(t, sizeof t, " -l0 -t%d", g_yt_threads > 0 ? g_yt_threads : 1);
  return std::string("-m") + YT_CODECS + t;
}
void ytool_set_precomp_params(const std::string& params) { g_yt_params = params; }
static std::string yt_params() {
  return g_yt_params.empty() ? ytool_default_params() : g_yt_params;
}

/* Extract the `-m<codecs>` token from a params string (the detector set). ytool's
   `-scan` mode accepts ONLY -m<codecs> (+ optional -t) and REJECTS -l0, so the scan
   command is built from just this token, not the full precomp params. Returns ""
   if there is no -m token (then scan is not meaningful and callers skip it). */
static std::string yt_mtoken(const std::string& params) {
  size_t p = params.find("-m");
  /* accept "-m" at start or after a space; skip a "-maxsize"-style false hit */
  while (p != std::string::npos) {
    bool at_bound = (p == 0 || params[p-1] == ' ');
    if (at_bound) break;
    p = params.find("-m", p + 2);
  }
  if (p == std::string::npos) return "";
  size_t e = params.find(' ', p);
  return params.substr(p, (e == std::string::npos) ? std::string::npos : e - p);
}

void ytool_set_binary(const std::string& path) { g_ytool_bin = path; }

static std::string ytool_bin() {
  if (!g_ytool_bin.empty()) return g_ytool_bin;
  const char* e = getenv("ZPAQ_YTOOL");
  if (e && *e) return std::string(e);
  return "ytool";
}

/* ---- small CRC-32 (IEEE, same polynomial as zlib) for authenticity ---- */
static uint32_t yt_crc32(const unsigned char* p, size_t n) {
  static uint32_t tab[256];
  static bool init = false;
  if (!init) {
    for (uint32_t i = 0; i < 256; ++i) {
      uint32_t c = i;
      for (int k = 0; k < 8; ++k) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
      tab[i] = c;
    }
    init = true;
  }
  uint32_t c = 0xFFFFFFFFu;
  for (size_t i = 0; i < n; ++i) c = tab[(c ^ p[i]) & 0xFF] ^ (c >> 8);
  return c ^ 0xFFFFFFFFu;
}

/* ---- temp files (unique per process+call; parallel-worker safe) ---- */
static std::string yt_tmpdir() {
  const char* v;
  if ((v = getenv("TMPDIR")) && *v) return v;
  if ((v = getenv("TMP"))    && *v) return v;
  if ((v = getenv("TEMP"))   && *v) return v;
#if defined(_WIN32)
  return ".";
#else
  return "/tmp";
#endif
}
static std::atomic<unsigned long> g_tmpctr(0);
static std::string yt_tmpname(const char* tag) {
  unsigned long n = g_tmpctr.fetch_add(1);
  char buf[64];
  snprintf(buf, sizeof buf, "/ytbridge_%ld_%lu_%s.tmp",
           (long)YT_GETPID(), n, tag);
  std::string d = yt_tmpdir();
  if (!d.empty() && (d[d.size()-1] == '/' || d[d.size()-1] == '\\'))
    d.erase(d.size()-1);
  return d + buf;
}
static bool yt_write_file(const std::string& path, const unsigned char* p, size_t n) {
  FILE* f = fopen(path.c_str(), "wb");
  if (!f) return false;
  bool ok = (n == 0) || (fwrite(p, 1, n, f) == n);
  if (fclose(f) != 0) ok = false;
  return ok;
}
static bool yt_read_file(const std::string& path, std::vector<unsigned char>& out) {
  out.clear();
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) return false;
  if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return false; }
  long sz = ftell(f);
  if (sz < 0) { fclose(f); return false; }
  if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return false; }
  out.resize((size_t)sz);
  bool ok = (sz == 0) || (fread(out.empty() ? (unsigned char*)"" : &out[0], 1, (size_t)sz, f) == (size_t)sz);
  fclose(f);
  if (!ok) out.clear();
  return ok;
}
static void yt_unlink(const std::string& path) { remove(path.c_str()); }

/* ---- run a ytool command; return the process exit code (or -1 on spawn error) ----
   stdout is drained and discarded (we only care about the exit code + the output
   FILE the command was told to write). Paths are double-quoted so spaces are safe. */
static int yt_run(const std::string& cmd) {
  FILE* pipe = YT_POPEN(cmd.c_str(), "r");
  if (!pipe) return -1;
  char buf[512];
  while (fgets(buf, sizeof buf, pipe) != NULL) { /* discard */ }
  int status = YT_PCLOSE(pipe);
  return status;   /* 0 == clean exit 0 (matches zpaq-std's own pclose convention) */
}
static std::string yt_q(const std::string& s) { return "\"" + s + "\""; }

/* ---- one cached probe -> {available, version} ----
   Availability and version are DECOUPLED so any ytool that runs is usable, even
   builds older than the one that added a clean `--version` (which printed the
   generic banner instead). `--version` on a current ytool prints just a digit
   version ("0.9.7") on stdout; on an older one it prints the "ytool ... xtool"
   banner. We accept EITHER as "available" (the binary is ytool and runs); the
   version string is best-effort (the digit line, else empty). Correctness never
   depends on the version -- the stored per-file CRC-32 is the real guard. */
static bool yt_str_has(const std::string& s, const char* needle) {
  std::string a = s;
  for (size_t i=0;i<a.size();++i) if (a[i]>='A'&&a[i]<='Z') a[i]=(char)(a[i]-'A'+'a');
  return a.find(needle) != std::string::npos;
}
struct YtProbe { bool available; std::string version; };
static YtProbe yt_probe() {
  YtProbe r; r.available = false;
  std::string cmd = yt_q(ytool_bin()) + " --version 2>&1";
  FILE* pipe = YT_POPEN(cmd.c_str(), "r");
  if (!pipe) return r;
  char buf[256]; std::string line;
  if (fgets(buf, sizeof buf, pipe) != NULL) line = buf;
  int status = YT_PCLOSE(pipe);
  if (status != 0) return r;
  while (!line.empty() && (line[line.size()-1]=='\n' || line[line.size()-1]=='\r'
                           || line[line.size()-1]==' ' || line[line.size()-1]=='\t'))
    line.erase(line.size()-1);
  if (!line.empty() && line[0] >= '0' && line[0] <= '9') {   /* clean version, e.g. 0.9.7 */
    r.available = true; r.version = line;
  } else if (yt_str_has(line, "tool")) {                      /* older banner (ytool/xtool) */
    r.available = true; r.version = "";                       /* version unknown, best-effort */
  }
  return r;
}
static const YtProbe& yt_cached() { static YtProbe p = yt_probe(); return p; }

std::string ytool_version(void) { return yt_cached().version; }
bool ytool_available(void)       { return yt_cached().available; }

/* ---- precomp / decode: buffer -> buffer via temp files ---- */
static bool ytool_precomp(const std::vector<unsigned char>& in,
                          std::vector<unsigned char>& out) {
  out.clear();
  if (in.empty()) return false;
  std::string tin = yt_tmpname("pi"), tout = yt_tmpname("po");
  bool ok = false;
  if (yt_write_file(tin, &in[0], in.size())) {
    std::string cmd = yt_q(ytool_bin()) + " precomp " + yt_params() + " " + yt_q(tin) + " " + yt_q(tout) + " 2>&1";
    int rc = yt_run(cmd);
    /* success requires clean exit AND a non-empty output file actually produced
       (belt-and-suspenders against a codec that "succeeds" but writes nothing). */
    if (rc == 0) ok = yt_read_file(tout, out) && !out.empty();
    if (!ok) out.clear();
  }
  yt_unlink(tin); yt_unlink(tout);
  return ok;
}
static bool ytool_decode(const std::vector<unsigned char>& in,
                         std::vector<unsigned char>& out) {
  out.clear();
  if (in.empty()) return false;
  std::string tin = yt_tmpname("di"), tout = yt_tmpname("do");
  bool ok = false;
  if (yt_write_file(tin, &in[0], in.size())) {
    std::string cmd = yt_q(ytool_bin()) + " decode " + yt_q(tin) + " " + yt_q(tout) + " 2>&1";
    int rc = yt_run(cmd);
    if (rc == 0) ok = yt_read_file(tout, out);   /* decoded original may legitimately be any size */
  }
  yt_unlink(tin); yt_unlink(tout);
  return ok;
}

/* ---- detect-only scan: count recompressible streams without precompressing ----
   Runs `ytool precomp -scan -m<codecs> <in> <dummy>` (which prints "SCAN <n> streams"
   to stderr, exits 0, and never writes the output file). -scan takes -m<codecs> only
   (it REJECTS -l0), so the command is built from just the -m token of the params. */
static int yt_scan_path(const std::string& inpath) {
  std::string mtok = yt_mtoken(yt_params());
  if (mtok.empty()) return -1;                 /* no -m => scan not meaningful */
  std::string tdummy = yt_tmpname("sd");
  int n = -1;
  std::string cmd = yt_q(ytool_bin()) + " precomp -scan " + mtok + " "
                  + yt_q(inpath) + " " + yt_q(tdummy) + " 2>&1";
  FILE* pipe = YT_POPEN(cmd.c_str(), "r");
  if (pipe) {
    char buf[512]; std::string all;
    while (fgets(buf, sizeof buf, pipe) != NULL) all += buf;
    int status = YT_PCLOSE(pipe);
    if (status == 0) {
      size_t sp = all.find("SCAN ");
      if (sp != std::string::npos) {
        long v = strtol(all.c_str() + sp + 5, NULL, 10);
        if (v >= 0) n = (int)v;
      }
    }
  }
  yt_unlink(tdummy);
  return n;
}

int ytool_scan_streams_path(const char* path) {
  if (!path || !*path || !ytool_available()) return -1;
  return yt_scan_path(path);
}

int ytool_scan_streams(const unsigned char* data, size_t len) {
  if (!data || len == 0 || !ytool_available()) return -1;
  if (yt_mtoken(yt_params()).empty()) return -1;
  std::string tin = yt_tmpname("si");
  int n = -1;
  if (yt_write_file(tin, data, len)) n = yt_scan_path(tin);
  yt_unlink(tin);
  return n;
}

/* ---- container framing ---- */
static const unsigned char YT_MAGIC[4] = { 'z', 'Y', 'T', 'L' };
static const unsigned char YT_VER = 1;

static void yt_put_varint(std::vector<unsigned char>& v, uint64_t x) {
  while (x >= 0x80) { v.push_back((unsigned char)(x | 0x80)); x >>= 7; }
  v.push_back((unsigned char)x);
}
static bool yt_get_varint(const unsigned char* p, size_t n, size_t& pos, uint64_t& out) {
  out = 0; int shift = 0;
  for (;;) {
    if (pos >= n || shift > 63) return false;
    unsigned char b = p[pos++];
    out |= (uint64_t)(b & 0x7F) << shift;
    if (!(b & 0x80)) return true;
    shift += 7;
  }
}

bool ytool_is_container(const unsigned char* buf, size_t len) {
  return buf && len >= 4 && memcmp(buf, YT_MAGIC, 4) == 0;
}

bool ytool_file_encode(const std::vector<unsigned char>& original,
                       std::vector<unsigned char>& container_out) {
  container_out.clear();
  if (original.empty() || !ytool_available()) return false;

  std::vector<unsigned char> pmp;
  if (!ytool_precomp(original, pmp)) return false;

  std::string ver = ytool_version();
  if (ver.size() > 255) return false;
  uint32_t crc = yt_crc32(&original[0], original.size());

  std::vector<unsigned char> c;
  c.insert(c.end(), YT_MAGIC, YT_MAGIC + 4);
  c.push_back(YT_VER);
  c.push_back((unsigned char)ver.size());
  c.insert(c.end(), ver.begin(), ver.end());
  yt_put_varint(c, (uint64_t)original.size());
  c.push_back((unsigned char)(crc & 0xFF));
  c.push_back((unsigned char)((crc >> 8) & 0xFF));
  c.push_back((unsigned char)((crc >> 16) & 0xFF));
  c.push_back((unsigned char)((crc >> 24) & 0xFF));
  c.insert(c.end(), pmp.begin(), pmp.end());

  /* verify-then-fallback: the container must reverse to the exact original NOW,
     or we refuse it and the caller stores verbatim. */
  std::vector<unsigned char> check;
  if (!ytool_authentic_reverse(c, check)) return false;
  if (check.size() != original.size()) return false;
  if (!original.empty() && memcmp(&check[0], &original[0], original.size()) != 0) return false;

  container_out.swap(c);
  return true;
}

bool ytool_authentic_reverse(const std::vector<unsigned char>& container,
                             std::vector<unsigned char>& original_out) {
  original_out.clear();
  const unsigned char* p = container.data();
  size_t n = container.size();
  if (!ytool_is_container(p, n)) return false;
  size_t pos = 4;
  if (pos >= n || p[pos++] != YT_VER) return false;
  if (pos >= n) return false;
  unsigned vlen = p[pos++];
  if (pos + vlen > n) return false;
  pos += vlen;                       /* stored producer version (advisory) */
  uint64_t origsize = 0;
  if (!yt_get_varint(p, n, pos, origsize)) return false;
  if (pos + 4 > n) return false;
  uint32_t crc = (uint32_t)p[pos] | ((uint32_t)p[pos+1] << 8)
               | ((uint32_t)p[pos+2] << 16) | ((uint32_t)p[pos+3] << 24);
  pos += 4;
  /* the rest is ytool's .pmp */
  std::vector<unsigned char> pmp(p + pos, p + n);
  std::vector<unsigned char> orig;
  if (!ytool_decode(pmp, orig)) return false;               /* not ours / undecodable */
  if (orig.size() != origsize) return false;                /* authenticity: size */
  if (yt_crc32(orig.empty() ? (const unsigned char*)"" : &orig[0], orig.size()) != crc)
    return false;                                           /* authenticity: CRC-32 */
  original_out.swap(orig);
  return true;
}
