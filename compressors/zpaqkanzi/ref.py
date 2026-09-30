#!/usr/bin/env python3
"""Reference decoder for zpaq-std -ma:kanzi blocks, levels 1 and 2 (kanzi 2.6.0,
bitstream v7, headerless). A literal translation of kanzi's C++ decoder, used to
validate against the library before writing the ZPAQL.

Block layout: orig size (4 bytes LE), level (1 byte), then kanzi's headerless
stream: blocks of [lr:5][read:lr bits][header][payload], bit-packed MSB first, and
an empty block (read == 0) at the end.
  level 1: transforms [LZX],     entropy NONE
  level 2: transforms [DNA, LZ], entropy HUFFMAN
"""
import sys

class Bits:
    def __init__(self, data, pos=0):
        self.d = data; self.p = pos * 8          # bit position
    def bit(self):
        b = (self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1; self.p += 1; return b
    def bits(self, n):
        v = 0
        for _ in range(n): v = (v << 1) | self.bit()
        return v
    def bytes_(self, nbits):                     # readBits(byte[], nbits)
        out = bytearray()
        full, rest = nbits >> 3, nbits & 7
        for _ in range(full): out.append(self.bits(8))
        if rest: out.append(self.bits(rest) << (8 - rest))
        return out

def read_varint(bs):
    v = bs.bits(8); res = v & 0x7F; shift = 7
    while v >= 128:
        v = bs.bits(8)
        if shift == 28: return res | ((v & 0x0F) << 28)
        res |= (v & 0x7F) << shift; shift += 7
    return res

def expgolomb_signed(bs):
    if bs.bit(): return 0
    log2 = 1
    while bs.bit() == 0: log2 += 1
    log2 = min(log2, 7)
    base = (1 << log2) - 1
    res = bs.bits(log2 + 1)
    value = (res >> 1) + base
    return -value if (res & 1) else value

def decode_alphabet(bs):
    if bs.bit() == 0:                            # FULL_ALPHABET
        return list(range(256)) if bs.bit() == 0 else []
    last = bs.bits(5)
    masks = bs.bytes_(8 * (last + 1))
    return [8 * i + j for i in range(last + 1) for j in range(8) if (masks[i] >> j) & 1]

def huffman_decode(bs, count, chunk=1 << 14):
    out = bytearray()
    while len(out) < count:
        n = min(chunk, count - len(out))
        if n < 32:
            out += bs.bytes_(8 * n); continue
        alpha = decode_alphabet(bs)
        if not alpha: raise ValueError("empty alphabet")
        sizes = {}; cur = 2
        for s in alpha:
            cur += expgolomb_signed(bs)
            if cur <= 0 or cur > 12: raise ValueError("bad size")
            sizes[s] = cur
        if len(alpha) == 1:
            out += bytes([alpha[0]]) * n; continue
        syms = sorted(alpha, key=lambda s: (sizes[s], s))
        codes = {}; code = 0; curlen = sizes[syms[0]]
        for s in syms:
            code <<= sizes[s] - curlen; curlen = sizes[s]; codes[(curlen, code)] = s; code += 1
        szb = [read_varint(bs) for _ in range(4)]
        frags = [bs.bytes_(b) for b in szb]
        q = n // 4
        res = bytearray(n)
        for k in range(4):
            fb = Bits(bytes(frags[k]) + bytes(8)); used = 0
            for i in range(q):
                c = 0; l = 0
                while True:
                    c = (c << 1) | fb.bit(); l += 1
                    if (l, c) in codes: res[k * q + i] = codes[(l, c)]; break
                    if l > 12: raise ValueError("bad code")
            if fb.p != szb[k]: raise ValueError("fragment bits %d != %d" % (fb.p, szb[k]))
        for i in range(4 * q, n): res[i] = bs.bits(8)
        out += res
    return bytes(out)

def read_length(src, pos):
    r = src[pos]; pos += 1
    if r < 254: return r, pos
    if r == 254: return 254 + (src[pos] << 8 | src[pos + 1]), pos + 2
    return 255 + (src[pos] << 16 | src[pos + 1] << 8 | src[pos + 2]), pos + 3

def lzx_inverse(src, count):
    le = lambda i: src[i] | src[i+1] << 8 | src[i+2] << 16 | src[i+3] << 24
    tk, mi, ml = le(0), le(4), le(8)
    if tk <= 13 or tk > count or mi > count - tk or ml > count - tk - mi: raise ValueError("lz hdr")
    mi += tk; ml += mi
    token_end, match_end, src_end, lit_end = mi, ml, tk - 13, tk
    max_dist = (1 << 16) - 2 if (src[12] & 1) == 0 else (1 << 24) - 2
    min_match = ((src[12] >> 1) & 7) + 2
    s = src + bytes(8)
    si, dst, repd0, repd1 = 13, bytearray(), count, count
    while True:
        t = s[tk]; tk += 1
        if (t & 0x18) == 0:
            mlen = t & 3
            if mlen == 3:
                if ml >= count: raise ValueError("ml")
                x, ml = read_length(s, ml); mlen += min_match + x
            else: mlen += min_match
            dist = repd0 if (t & 4) == 0 else repd1
        else:
            mlen = t & 7
            if mlen == 7:
                if ml >= count: raise ValueError("ml")
                x, ml = read_length(s, ml); mlen += min_match + x
            else: mlen += min_match
            if mi >= count: raise ValueError("mi")
            w = (t >> 3) & 3
            v = s[mi] << 24 | s[mi+1] << 16 | s[mi+2] << 8 | s[mi+3]
            dist = (v >> (0, 24, 16, 8)[w]) + (0, 1, 257, 65793)[w]; mi += w
        if t >= 32:
            if t >= 0xE0: x, si = read_length(s, si); lit = 7 + x
            else: lit = t >> 5
            if si + lit > lit_end: raise ValueError("lit")
            dst += s[si:si + lit]; si += lit
            if si >= src_end: break
        repd1, repd0 = repd0, dist
        ref = len(dst) - dist
        if ref < 0 or dist > max_dist: raise ValueError("dist")
        for i in range(mlen): dst.append(dst[ref + i])
    if not (si == src_end + 13 and tk == token_end and mi == match_end and ml == count):
        raise ValueError("lz end %d %d %d %d" % (si - src_end - 13, tk - token_end, mi - match_end, ml - count))
    return bytes(dst)

def dna_inverse(src, count):
    n = src[0]
    if n < 16: raise ValueError("dna n")
    dst = bytearray()
    if n >= 240:
        n = 256 - n; si = 1
        if n == 1:
            val = src[1]; osz = src[2] | src[3] << 8 | src[4] << 16 | src[5] << 24
            return bytes([val]) * osz
        idx2 = list(src[si:si + n]) + [0] * (16 - n); si += n
        adjust = src[si]; si += 1
        if n <= 4:
            dst += src[si:si + adjust]; si += adjust
            while si < count:
                b = src[si]; si += 1
                # the C++ builds idx[b&3]<<24 | ... | idx[b>>6] and writes it LITTLE endian
                dst += bytes([idx2[(b >> 6) & 3], idx2[(b >> 4) & 3], idx2[(b >> 2) & 3], idx2[b & 3]])
        else:
            if adjust: dst.append(src[si]); si += 1
            while si < count:
                b = src[si]; si += 1
                dst += bytes([idx2[b >> 4], idx2[b & 15]])
    else:
        adjust = src[1]; send = count - adjust; si = 2
        m = {}
        for i in range(n):
            m[src[si + 2]] = bytes([src[si], src[si + 1]]); si += 3
        while si < send:
            b = src[si]; si += 1
            dst += m.get(b, bytes([b]))
        if adjust: dst.append(src[si]); si += 1
    return bytes(dst)

LEVELS = {1: ([lzx_inverse], False), 2: ([dna_inverse, lzx_inverse], True)}

def decode(z):
    orig = z[0] | z[1] << 8 | z[2] << 16 | z[3] << 24
    level = z[4]
    trs, huff = LEVELS[level]
    bs = Bits(z, 5); out = bytearray()
    while True:
        lr = 3 + bs.bits(5); read = bs.bits(lr)
        if read == 0: break
        start = bs.p
        mode = bs.bits(8)
        copy = mode & 0x80
        tcopy = bool(copy and (mode & 0x10))
        if not copy and (mode & 0x10): skip = bs.bits(8)
        else: skip = ((mode << 4) | 0x0F) & 0xFF
        dsz = 1 + ((mode >> 5) & 3)
        pre = bs.bits(8 * dsz)
        bs.bits(8)                               # v7 block header checksum (not checked)
        if copy and not tcopy:
            data = bytes(bs.bytes_(8 * pre)); t_list = []
        else:
            data = bytes(bs.bytes_(8 * pre)) if (tcopy or not huff) else huffman_decode(bs, pre)
            t_list = trs
        cnt = len(data)
        for i in range(len(t_list) - 1, -1, -1):
            if skip & (1 << (7 - i)): continue
            data = t_list[i](data, len(data))
        out += data
        if bs.p - start != read: raise ValueError("block bits %d != %d" % (bs.p - start, read))
    if len(out) != orig: raise ValueError("size %d != %d" % (len(out), orig))
    return bytes(out)

if __name__ == "__main__":
    z = open(sys.argv[1], "rb").read()
    o = decode(z)
    if len(sys.argv) > 2: open(sys.argv[2], "wb").write(o)
    print(len(o))
