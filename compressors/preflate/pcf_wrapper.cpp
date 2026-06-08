/* pcf_wrapper.cpp — implementation of the collision-free preflate bridge.
   This is the ONLY translation unit that includes preflate headers. */
#include "pcf_wrapper.h"
#include <cstdint>
#include <algorithm>
#include <utility>
#include "preflate_decoder.h"
#include "preflate_reencoder.h"
#include "support/memstream.h"

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
enum { PCF_SEG_LITERAL = 0, PCF_SEG_DEFLATE = 1, PCF_SEG_PNGIDAT = 2 };

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

/* ---- Phase 2: embedded-stream scanning (ZIP) ---- */

static uint32_t rd32(const unsigned char* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint16_t rd16(const unsigned char* p) { return (uint16_t)(p[0] | (p[1] << 8)); }

/* big-endian 32-bit (PNG chunk lengths/CRCs are big-endian) */
static uint32_t rd32be(const unsigned char* p) {
  return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static void put32be(std::vector<unsigned char>& v, uint32_t x) {
  v.push_back((unsigned char)(x >> 24)); v.push_back((unsigned char)(x >> 16));
  v.push_back((unsigned char)(x >> 8));  v.push_back((unsigned char)x);
}

/* standard IEEE CRC-32 (poly 0xEDB88320) — used for PNG chunk CRCs */
static uint32_t png_crc32(const unsigned char* buf, size_t len) {
  static uint32_t table[256];
  static bool init = false;
  if (!init) {
    for (uint32_t i = 0; i < 256; ++i) {
      uint32_t c = i;
      for (int k = 0; k < 8; ++k) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
      table[i] = c;
    }
    init = true;
  }
  uint32_t c = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; ++i) c = table[(c ^ buf[i]) & 0xff] ^ (c >> 8);
  return c ^ 0xFFFFFFFFu;
}

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
  std::vector<std::vector<unsigned char> > unps, recs;
  for (size_t i = 0; i < regions_in.size(); ++i) {
    size_t s = regions_in[i].first, e = regions_in[i].second;
    if (s >= e || e > f.size()) continue;
    std::vector<unsigned char> d(f.begin() + s, f.begin() + e), u, r;
    if (pcf_deflate_decode(d.empty() ? 0 : &d[0], d.size(), u, r)) {
      regs.push_back(regions_in[i]); unps.push_back(u); recs.push_back(r);
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
    body.push_back(PCF_SEG_DEFLATE);
    put_varint(body, recs[i].size());
    body.insert(body.end(), recs[i].begin(), recs[i].end());
    put_varint(body, unps[i].size());
    body.insert(body.end(), unps[i].begin(), unps[i].end());
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

/* Parse a PNG: collect the consecutive IDAT chunks (whose data, concatenated,
   is ONE zlib stream). Sets [idat_start,idat_end) = the byte span of the IDAT
   chunk region in the file, chunk_lens = each IDAT's data length, and idat_data
   = the concatenated IDAT payloads. Returns false if not a PNG with a single
   consecutive IDAT run. */
static bool scan_png(const std::vector<unsigned char>& f,
                     size_t& idat_start, size_t& idat_end,
                     std::vector<uint32_t>& chunk_lens,
                     std::vector<unsigned char>& idat_data) {
  static const unsigned char SIG[8] = {0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a};
  const size_t n = f.size();
  if (n < 8 + 12) return false;
  for (int i = 0; i < 8; ++i) if (f[i] != SIG[i]) return false;
  size_t p = 8;
  bool in_idat = false, seen_idat = false;
  idat_start = idat_end = 0;
  while (p + 8 <= n) {
    uint32_t len = rd32be(&f[p]);
    if (p + 12 + (size_t)len > n) return false;            /* truncated */
    const unsigned char* type = &f[p + 4];
    bool is_idat = (type[0]=='I'&&type[1]=='D'&&type[2]=='A'&&type[3]=='T');
    if (is_idat) {
      if (seen_idat && !in_idat) return false;             /* IDAT run not consecutive */
      if (!in_idat) { idat_start = p; in_idat = true; seen_idat = true; }
      chunk_lens.push_back(len);
      idat_data.insert(idat_data.end(), &f[p+8], &f[p+8+len]);
    } else if (in_idat) {
      idat_end = p; in_idat = false;                       /* IDAT run just ended */
    }
    bool is_iend = (type[0]=='I'&&type[1]=='E'&&type[2]=='N'&&type[3]=='D');
    p += 12 + len;                                         /* len(4)+type(4)+data+crc(4) */
    if (is_iend) break;
  }
  if (in_idat) idat_end = p;                               /* IDAT ran to last chunk */
  return seen_idat && idat_end > idat_start && idat_data.size() >= 6;
}

/* Build a PCF from a PNG: literal prefix, a PNG-IDAT segment (the combined zlib
   stream split into the original IDAT chunk sizes), literal suffix. */
static bool build_pcf_png(const std::vector<unsigned char>& f,
                          std::vector<unsigned char>& pcf_out) {
  size_t idat_start = 0, idat_end = 0;
  std::vector<uint32_t> chunk_lens;
  std::vector<unsigned char> idat;
  if (!scan_png(f, idat_start, idat_end, chunk_lens, idat)) return false;
  /* idat = zlib header(2) + raw deflate + adler(4..). preflate the deflate. */
  if (idat.size() < 6 || (idat[0] & 0x0f) != 0x08) return false;
  std::vector<unsigned char> unpacked, recon;
  size_t consumed = 0;
  if (!deflate_decode_sized(&idat[2], idat.size() - 2, unpacked, recon, 16, consumed)) return false;
  if (2 + consumed > idat.size()) return false;
  std::vector<unsigned char> zhdr(idat.begin(), idat.begin() + 2);
  std::vector<unsigned char> trailer(idat.begin() + 2 + consumed, idat.end());

  std::vector<unsigned char> body;
  uint64_t nseg = 0;
  if (idat_start > 0) {
    body.push_back(PCF_SEG_LITERAL); put_varint(body, idat_start);
    body.insert(body.end(), f.begin(), f.begin() + idat_start); ++nseg;
  }
  body.push_back(PCF_SEG_PNGIDAT);
  put_varint(body, chunk_lens.size());
  for (size_t i = 0; i < chunk_lens.size(); ++i) put_varint(body, chunk_lens[i]);
  put_varint(body, zhdr.size());    body.insert(body.end(), zhdr.begin(), zhdr.end());
  put_varint(body, trailer.size()); body.insert(body.end(), trailer.begin(), trailer.end());
  put_varint(body, recon.size());   body.insert(body.end(), recon.begin(), recon.end());
  put_varint(body, unpacked.size());body.insert(body.end(), unpacked.begin(), unpacked.end());
  ++nseg;
  if (idat_end < f.size()) {
    body.push_back(PCF_SEG_LITERAL); put_varint(body, f.size() - idat_end);
    body.insert(body.end(), f.begin() + idat_end, f.end()); ++nseg;
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
    } else if (kind == PCF_SEG_PNGIDAT) {
      uint64_t nchunks = 0;
      if (!get_varint(p, n, pos, nchunks) || nchunks == 0 || nchunks > (1u << 24)) return false;
      std::vector<uint64_t> clens(nchunks);
      uint64_t total = 0;
      for (uint64_t c = 0; c < nchunks; ++c) {
        if (!get_varint(p, n, pos, clens[c])) return false;
        total += clens[c];
      }
      uint64_t zlen = 0;
      if (!get_varint(p, n, pos, zlen) || pos + zlen > n) return false;
      std::vector<unsigned char> zhdr(p + pos, p + pos + zlen); pos += zlen;
      uint64_t tlen = 0;
      if (!get_varint(p, n, pos, tlen) || pos + tlen > n) return false;
      std::vector<unsigned char> trailer(p + pos, p + pos + tlen); pos += tlen;
      uint64_t rlen = 0;
      if (!get_varint(p, n, pos, rlen) || pos + rlen > n) return false;
      std::vector<unsigned char> recon(p + pos, p + pos + rlen); pos += rlen;
      uint64_t ulen = 0;
      if (!get_varint(p, n, pos, ulen) || pos + ulen > n) return false;
      std::vector<unsigned char> unpacked(p + pos, p + pos + ulen); pos += ulen;
      std::vector<unsigned char> deflate;
      if (!pcf_deflate_reencode(unpacked, recon, deflate)) return false;
      /* reassemble the full zlib stream, then re-split into the original IDAT chunks */
      std::vector<unsigned char> full;
      full.reserve(zhdr.size() + deflate.size() + trailer.size());
      full.insert(full.end(), zhdr.begin(), zhdr.end());
      full.insert(full.end(), deflate.begin(), deflate.end());
      full.insert(full.end(), trailer.begin(), trailer.end());
      if (total != full.size()) return false;
      size_t off = 0;
      for (uint64_t c = 0; c < nchunks; ++c) {
        uint32_t L = (uint32_t)clens[c];
        put32be(original_out, L);
        size_t crcpos = original_out.size();
        const unsigned char idat_tag[4] = {'I','D','A','T'};
        original_out.insert(original_out.end(), idat_tag, idat_tag + 4);
        original_out.insert(original_out.end(), full.begin() + off, full.begin() + off + L);
        uint32_t crc = png_crc32(&original_out[crcpos], 4 + L);
        put32be(original_out, crc);
        off += L;
      }
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

  /* PNG: recompress the IDAT zlib stream (split across consecutive IDAT chunks). */
  if (!built && original.size() >= 8 && original[0] == 0x89 && original[1] == 0x50
      && original[2] == 0x4e && original[3] == 0x47) {
    built = build_pcf_png(original, cand);
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

bool pcf_authentic_reverse(const std::vector<unsigned char>& stored,
                           std::vector<unsigned char>& original_out) {
  original_out.clear();
  if (!pcf_is_container(stored.data(), stored.size())) return false;
  std::vector<unsigned char> orig;
  if (!pcf_file_decode(stored, orig)) return false;
  /* authenticity: re-encoding the decoded original must reproduce `stored`
     exactly, otherwise this was not a PCF stream we created (do not touch it). */
  std::vector<unsigned char> re;
  if (!pcf_file_encode(orig, re)) return false;
  if (re != stored) return false;
  original_out.swap(orig);
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
