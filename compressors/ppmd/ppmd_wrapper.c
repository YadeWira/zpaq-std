/* One-shot buffer wrapper around Ppmd7 (PPMd var.H), public domain. */
#include "ppmd_wrapper.h"
#include "Ppmd7.h"
#include <stdlib.h>

static void *pp_alloc(ISzAllocPtr p, size_t s) { (void)p; return malloc(s); }
static void  pp_free (ISzAllocPtr p, void *a)  { (void)p; free(a); }
static const ISzAlloc g_ppmd_alloc = { pp_alloc, pp_free };

/* IByteOut sink -> fixed dst buffer (sets overflow if it doesn't fit) */
typedef struct { IByteOut vt; unsigned char *buf; size_t pos, cap; int overflow; } OutB;
static void ob_write(IByteOutPtr pp, Byte b) {
  OutB *o = (OutB *)(void *)pp;           /* IByteOut is the first member */
  if (o->pos < o->cap) o->buf[o->pos++] = b; else o->overflow = 1;
}

/* IByteIn source <- fixed src buffer (returns 0 past end, per the API contract) */
typedef struct { IByteIn vt; const unsigned char *buf; size_t pos, len; } InB;
static Byte ib_read(IByteInPtr pp) {
  InB *in = (InB *)(void *)pp;
  return (in->pos < in->len) ? in->buf[in->pos++] : (Byte)0;
}

size_t ppmd_compress(const unsigned char *src, size_t srclen,
                     unsigned char *dst, size_t dstcap,
                     unsigned order, unsigned mem_mb) {
  CPpmd7 p;
  OutB o;
  Ppmd7_Construct(&p);
  if (!Ppmd7_Alloc(&p, (UInt32)mem_mb << 20, &g_ppmd_alloc)) return 0;
  Ppmd7_Init(&p, order);
  o.vt.Write = ob_write; o.buf = dst; o.pos = 0; o.cap = dstcap; o.overflow = 0;
  p.rc.enc.Stream = &o.vt;
  Ppmd7z_Init_RangeEnc(&p);
  Ppmd7z_EncodeSymbols(&p, src, src + srclen);
  Ppmd7z_Flush_RangeEnc(&p);
  Ppmd7_Free(&p, &g_ppmd_alloc);
  return o.overflow ? 0 : o.pos;
}

int ppmd_decompress(const unsigned char *src, size_t srclen,
                    unsigned char *dst, size_t dstlen,
                    unsigned order, unsigned mem_mb) {
  CPpmd7 p;
  InB in;
  size_t i;
  Ppmd7_Construct(&p);
  if (!Ppmd7_Alloc(&p, (UInt32)mem_mb << 20, &g_ppmd_alloc)) return 0;
  Ppmd7_Init(&p, order);
  in.vt.Read = ib_read; in.buf = src; in.pos = 0; in.len = srclen;
  p.rc.dec.Stream = &in.vt;
  if (!Ppmd7z_RangeDec_Init(&p.rc.dec)) { Ppmd7_Free(&p, &g_ppmd_alloc); return 0; }
  for (i = 0; i < dstlen; i++) {
    int sym = Ppmd7z_DecodeSymbol(&p);
    if (sym < 0) { Ppmd7_Free(&p, &g_ppmd_alloc); return 0; }
    dst[i] = (unsigned char)sym;
  }
  Ppmd7_Free(&p, &g_ppmd_alloc);
  return 1;
}
