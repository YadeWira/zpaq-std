/* pcf_wrapper.cpp — implementation of the collision-free preflate bridge.
   This is the ONLY translation unit that includes preflate headers. */
#include "pcf_wrapper.h"
#include <cstdint>
#include "preflate_decoder.h"
#include "preflate_reencoder.h"

bool pcf_deflate_decode(const unsigned char* deflate, size_t deflate_len,
                        std::vector<unsigned char>& unpacked,
                        std::vector<unsigned char>& recon) {
  unpacked.clear();
  recon.clear();
  if (deflate == 0 || deflate_len == 0) return false;
  std::vector<unsigned char> in(deflate, deflate + deflate_len);
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

/* ---------------- File-level PCF container ---------------- */

static const unsigned char PCF_MAGIC[4] = { 'z', 'P', 'C', 'F' };
static const unsigned char PCF_VERSION  = 1;
enum { PCF_SEG_LITERAL = 0, PCF_SEG_DEFLATE = 1 };

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
  std::vector<unsigned char> deflate(f.begin() + d0, f.begin() + d1);
  std::vector<unsigned char> unpacked, recon;
  if (!pcf_deflate_decode(deflate.data(), deflate.size(), unpacked, recon)) return false;

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
  pcf_out.push_back(PCF_SEG_DEFLATE);
  put_varint(pcf_out, recon.size());
  pcf_out.insert(pcf_out.end(), recon.begin(), recon.end());
  put_varint(pcf_out, unpacked.size());
  pcf_out.insert(pcf_out.end(), unpacked.begin(), unpacked.end());
  if (d1 < f.size()) {
    pcf_out.push_back(PCF_SEG_LITERAL);
    put_varint(pcf_out, f.size() - d1);
    pcf_out.insert(pcf_out.end(), f.begin() + d1, f.end());
  }
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
    if (kind == PCF_SEG_LITERAL) {
      uint64_t len = 0;
      if (!get_varint(p, n, pos, len) || pos + len > n) return false;
      original_out.insert(original_out.end(), p + pos, p + pos + len);
      pos += len;
    } else if (kind == PCF_SEG_DEFLATE) {
      uint64_t rlen = 0;
      if (!get_varint(p, n, pos, rlen) || pos + rlen > n) return false;
      std::vector<unsigned char> recon(p + pos, p + pos + rlen); pos += rlen;
      uint64_t ulen = 0;
      if (!get_varint(p, n, pos, ulen) || pos + ulen > n) return false;
      std::vector<unsigned char> unpacked(p + pos, p + pos + ulen); pos += ulen;
      std::vector<unsigned char> deflate;
      if (!pcf_deflate_reencode(unpacked, recon, deflate)) return false;
      original_out.insert(original_out.end(), deflate.begin(), deflate.end());
    } else {
      return false;
    }
  }
  return pos == n;
}

bool pcf_file_encode(const std::vector<unsigned char>& original,
                     std::vector<unsigned char>& pcf_out) {
  pcf_out.clear();
  if (original.size() < 18) return false; /* too small to be worth it */

  size_t d0 = 0, d1 = 0;
  bool built = false;
  std::vector<unsigned char> cand;
  if (locate_payload(original, d0, d1)) {
    built = build_pcf(original, d0, d1, cand);
  }
  if (!built) {
    /* last resort: whole file as raw DEFLATE */
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
