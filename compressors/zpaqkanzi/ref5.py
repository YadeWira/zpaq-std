#!/usr/bin/env python3
"""Reference decoder for zpaq-std -ma:kanzi levels 5 and 6 (kanzi 2.6.0,
bitstream v7, headerless). A literal translation of kanzi's C++ decoder.

  level 5: transforms [TEXT, UTF, BWT, RANK, ZRLT], entropy ANS0 (TextCodec2)
  level 6: transforms [TEXT, UTF, BWT, SRT,  ZRLT], entropy FPAQ (TextCodec1)

Block layout as ref.py: orig (4 LE), level (1), kanzi's headerless stream.
"""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref import Bits, read_varint, decode_alphabet

import collections
ST = collections.Counter()
M32 = 0xFFFFFFFF
def log2(x): return x.bit_length() - 1

def kz_blocksize(n):
    bs = (n + 15) & ~15
    return min(max(bs, 1024), 1 << 30)

# ----------------------------------------------------------------------------- entropy
def ans0_decode(bs, count, chunk=16384):
    if count <= 32:
        return bytes(bs.bytes_(8 * count))
    out = bytearray()
    while len(out) < count:
        n = min(chunk, count - len(out))
        lr = 8 + bs.bits(3)
        if lr > 15: raise ValueError("ans logRange")
        scale = 1 << lr
        llr = log2(lr) + 1
        alpha = decode_alphabet(bs)
        if not alpha: raise ValueError("ans alphabet")
        f = [0] * 256
        chk = 8 if len(alpha) >= 64 else 6
        s = 0
        for i in range(1, len(alpha), chk):
            lm = bs.bits(llr)
            if lm > lr: raise ValueError("ans logMax")
            for j in range(i, min(i + chk, len(alpha))):
                fr = 1 if lm == 0 else bs.bits(lm) + 1
                f[alpha[j]] = fr; s += fr
        if scale <= s: raise ValueError("ans sum")
        f[alpha[0]] = scale - s
        ST['ans_chunk'] += 1
        if len(alpha) == 1:
            ST['ans_1sym'] += 1; out += bytes([alpha[0]]) * n; continue
        f2s = bytearray(scale); cum = [0] * 256; fq = [0] * 256; c = 0
        for i in range(256):
            if f[i] == 0: continue
            f2s[c:c + f[i]] = bytes([i]) * f[i]
            cum[i] = c; fq[i] = min(f[i], scale - 1); c += f[i]
        sz = read_varint(bs)
        st = [bs.bits(32) for _ in range(4)]          # st0..st3
        buf = bytes(bs.bytes_(8 * sz)) + bytes(600)
        p = 0; mask = scale - 1
        res = bytearray(n)
        c4 = n & ~3
        for i in range(0, c4, 4):
            for k, si in ((3, 0), (2, 1), (1, 2), (0, 3)):
                x = st[k]; sym = f2s[x & mask]; res[i + si] = sym
                x = (fq[sym] * (x >> lr) + (x & mask) - cum[sym]) & M32
                if x < (1 << 15):
                    x = ((x << 16) | (buf[p] << 8) | buf[p + 1]) & M32; p += 2
                st[k] = x
        for i in range(c4, n):
            res[i] = buf[p]; p += 1
        if p != sz: raise ValueError("ans payload %d != %d" % (p, sz))
        out += res
    return bytes(out)

def fpaq_decode(bs, count):
    M56 = (1 << 56) - 1
    probs = [[32768] * 256 for _ in range(4)]
    low, high = 0, M56
    out = bytearray()
    start = 0
    while start < count:
        n = min(4 << 20, count - start); ST['fpaq_chunk'] += 1
        sz = read_varint(bs)
        if sz > 2 * n: raise ValueError("fpaq size")
        cur = bs.bits(56)
        buf = bytes(bs.bytes_(8 * sz))
        idx = 0
        p = probs[0]
        for _ in range(n):
            ctx = 1
            for _b in range(8):
                pr = p[ctx]
                split = ((((high - low) >> 8) * pr) >> 8) + low
                if split >= cur:
                    high = split
                    p[ctx] = (pr - ((pr - 65536 + 64) >> 6)) & 0xFFFF
                    ctx += ctx + 1
                else:
                    low = split + 1
                    p[ctx] = (pr - (pr >> 6)) & 0xFFFF
                    ctx += ctx
                if ((low ^ high) >> 24) == 0:
                    low = (low << 32) & M56
                    high = ((high << 32) | M32) & M56
                    if idx + 4 > sz:
                        cur = (cur << 32) & M56; idx = sz + 1
                    else:
                        cur = ((cur << 32) | int.from_bytes(buf[idx:idx + 4], 'big')) & M56; idx += 4
            out.append(ctx & 255)
            if idx > sz: raise ValueError("fpaq overrun")
            p = probs[(ctx & 255) >> 6]
        start += n
    return bytes(out)

# ----------------------------------------------------------------------------- transforms
def zrlt_inverse(src, count, dstcap):
    dst = bytearray(); si = 0; run = 0
    end = False
    while True:
        val = src[si]
        if val <= 1:
            run = 1
            while True:
                run += run + val; si += 1
                if si >= count: end = True; break
                val = src[si]
                if val > 1: break
            if end: break
            run -= 1
            if run > 0:
                if run >= dstcap - len(dst): end = True; break
                dst += bytes(run); run = 0
                continue
        if len(dst) >= dstcap: raise ValueError("zrlt cap")
        if val == 0xFF:
            si += 1
            if si >= count: raise ValueError("zrlt ff")
            dst.append((0xFE + src[si]) & 255)
        else:
            dst.append(val - 1)
        si += 1
        if si >= count or len(dst) >= dstcap: break
    if run > 0:
        run -= 1
        if run > dstcap - len(dst): raise ValueError("zrlt tail")
        dst += bytes(run)
    if si != count: raise ValueError("zrlt end")
    return bytes(dst)

def rank_inverse(src, count):
    p = [0] * 256; q = [0] * 256; r2s = list(range(256)); dst = bytearray(count)
    for i in range(count):
        r = src[i]; c = r2s[r]; dst[i] = c
        qc = (i + p[c]) >> 1
        p[c] = i; q[c] = qc
        while r > 0 and q[r2s[r - 1]] <= qc:
            r2s[r] = r2s[r - 1]; r -= 1
        r2s[r] = c
    return bytes(dst)

def srt_inverse(src, length):
    if length < 256: raise ValueError("srt len")
    freqs = [0] * 256; si = 0
    for i in range(256):
        res = 0; sh = 0
        for j in range(5):
            v = src[si]; si += 1
            res |= (v & 0x7F) << sh
            if (v & 0x80) == 0: break
            if j == 4: raise ValueError("srt hdr")
            sh += 7
        freqs[i] = res
    data = src[si:length]; n = len(data)
    if sum(freqs) != n: raise ValueError("srt freqs")
    syms = [i for i in range(256) if freqs[i]]
    syms.sort(key=lambda s: (-freqs[s], s))
    nb = len(syms)
    buckets = [0] * 256; ends = [0] * 256; r2s = [0] * 256; pos = 0
    for c in syms:
        r2s[data[pos]] = c; buckets[c] = pos + 1; pos += freqs[c]; ends[c] = pos
    c = r2s[0]; dst = bytearray(n)
    for i in range(n):
        dst[i] = c
        if buckets[c] < ends[c]:
            r = data[buckets[c]]; buckets[c] += 1
            if r == 0: continue
            r2s[0:r] = r2s[1:r + 1]; r2s[r] = c; c = r2s[0]
        else:
            ST['srt_agota'] += 1
            if nb == 1: continue
            nb -= 1; r2s[0:nb] = r2s[1:nb + 1]; c = r2s[0]
    return bytes(dst)

def bwt_inverse(src, count):
    mode = src[0]
    lognb = (mode >> 2) & 7; pis = (mode & 3) + 1; chunks = 1 << lognb
    hs = 1 + chunks * pis
    n = count - hs
    if chunks != (1 if n < 256 else 8): raise ValueError("bwt chunks")
    pidx = []
    k = 1
    for i in range(chunks):
        v = 0
        for _ in range(pis): v = (v << 8) | src[k]; k += 1
        pidx.append(v + 1)
    data = src[hs:count]
    if n == 1: return bytes(data)
    pi = pidx[0]
    buckets = [0] * 256
    for b in data: buckets[b] += 1
    s = 0
    for i in range(256): t = buckets[i]; buckets[i] = s; s += t
    buf = [0] * n
    buf[buckets[data[0]]] = data[0]; buckets[data[0]] += 1
    for i in range(1, n):
        v = data[i]
        buf[buckets[v]] = (((i - 1) if i < pi else i) << 8) | v; buckets[v] += 1
    t = pi - 1; out = bytearray(n)
    for j in range(n):
        ptr = buf[t]; out[j] = ptr & 255; t = ptr >> 8
    return bytes(out)

def utf_unpack(s):
    t = s >> 19
    if t == 0: return bytes([s & 255])
    if t == 1: return bytes([(s >> 8) & 255, s & 255])
    if t == 2: return bytes([((s >> 12) & 0x0F) | 0xE0, ((s >> 6) & 0x3F) | 0x80, (s & 0x3F) | 0x80])
    if t in (4, 5, 6, 7): return bytes([((s >> 18) & 7) | 0xF0, ((s >> 12) & 0x3F) | 0x80, ((s >> 6) & 0x3F) | 0x80, (s & 0x3F) | 0x80])
    raise ValueError("utf unpack")

def utf_inverse(src, count, dstcap):
    start = src[0] & 3; adjust = src[1] & 3; n = (src[2] << 8) + src[3]
    if n == 0 or n >= 32768 or 3 * n > count - 4: raise ValueError("utf n")
    m = []; si = 4
    for i in range(n):
        m.append(utf_unpack((src[si] << 16) | (src[si + 1] << 8) | src[si + 2])); si += 3
    send = count - 4 + adjust
    dst = bytearray(src[si:si + start]); si += start
    ST['utf_n<=128' if n <= 128 else 'utf_n>128'] += 1
    if n <= 128:
        while si < send:
            a = src[si]; si += 1
            if a >= n: raise ValueError("utf alias")
            dst += m[a]
    else:
        while si < send:
            a = src[si]; si += 1
            if a >= 128: a = (src[si] << 7) + (a & 0x7F); si += 1
            if a >= n: raise ValueError("utf alias")
            dst += m[a]
    if si == send and len(dst) < dstcap - 4 + adjust:
        dst += src[si:si + 4 - adjust]; si += 4 - adjust
    if si != count: raise ValueError("utf end")
    return bytes(dst)

# --- TEXT
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, '..', 'kanzi', 'transform', 'TextCodec.cpp')).read()   # compressors/kanzi
_i = _src.index('char TextCodec::DICT_EN_1024[] =')
DICT_EN = _src[_src.index('"', _i) + 1:_src.index('";', _i)].replace('\\\n', '').encode()
HASH1, HASH2 = 0x7FEB352D, 0x846CA68B

def ctype(c):
    if 0x20 <= c <= 0x2F or 0x3A <= c <= 0x3F or c in b'\n\r\t_|{}[]': return 1
    if 0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A: return 0
    return -1

def whash(bs_):
    h = HASH1
    for b in bs_: h = ((h * HASH1) ^ (b * HASH2)) & M32
    return h

def static_dict():
    src = bytearray(DICT_EN + b'\0')        # sizeof includes the NUL
    words = []; anchor = 0
    for i in range(len(src)):
        if len(words) >= 1024: break
        if ctype(src[i]) != 0: continue
        if 0x41 <= src[i] <= 0x5A:
            if i > anchor:
                w = bytes(src[anchor:i]); words.append(w); anchor = i
            src[i] ^= 0x20
    if len(words) < 1024:
        w = bytes(src[anchor:len(src) - 1]); words.append(w)
    return words
STATIC = static_dict()

def text_inverse(src, count, outlen, bsz, variant):
    # variant 1: TextCodec1 (escapes 0x0E/0x0F), variant 2: TextCodec2 (0x80 tokens)
    if variant == 1:
        log = max(min(log2(bsz // 8), 26), 13) if bsz >= 8 else 13
    else:
        log = max(min(log2(bsz // 32), 24), 13) if bsz >= 32 else 13
    hmask = (1 << log) - 1
    lg = 13 if outlen < 1024 else max(min(log2(outlen // 128), 18), 13)
    nstat = len(STATIC)
    # entries: [word bytes or None, hash, data]; map: dict slot -> entry index
    ent = [[w, whash(w), (len(w) << 24) | i] for i, w in enumerate(STATIC)]
    if variant == 1:
        dsize = max(nstat + 2, 1 << lg)
        ent.append([b'\x0e', 0, (1 << 24) | nstat]); ent.append([b'\x0f', 0, (1 << 24) | (nstat + 1)])
        sds = nstat + 2
    else:
        dsize = max(nstat, 1 << lg); sds = nstat
    hmap = {}
    for i in range(sds): hmap[ent[i][1] & hmask] = i
    for i in range(sds, dsize): ent.append([None, 0, i])
    crlf = (src[0] & 0x40) != 0
    si = 1; dst = bytearray(); dend = outlen
    anchor = si - 1 if ctype(src[si]) == 0 else si
    words = sds; wrun = False
    while si < count and len(dst) < dend:
        cur = src[si]; ct = ctype(cur)
        if ct == 0:
            dst.append(cur); si += 1; continue
        if si > anchor + 3 and ct > 0:
            length = si - anchor - 1
            if length <= 31:
                h1 = whash(src[anchor + 1:si])
                pe1 = hmap.get(h1 & hmask)
                pe = None
                if pe1 is not None and ent[pe1][1] == h1 and (ent[pe1][2] >> 24) == length: pe = pe1
                if pe is None and (length > 3 or words < 128 * 128) and pe1 is None:
                    e = ent[words]
                    if (e[2] & 0x7FFFF) >= sds:
                        if hmap.get(e[1] & hmask) is not None: del hmap[e[1] & hmask]
                        e[0] = bytes(src[anchor + 1:si]); e[1] = h1; e[2] = (length << 24) | words
                    hmap[h1 & hmask] = words
                    words += 1
                    if words >= dsize:
                        ST['dict_lleno'] += 1
                        if dsize >= (1 << 19): words = sds
                        else:
                            for i in range(dsize, 2 * dsize): ent.append([None, 0, i])
                            for i in range(dsize): hmap[ent[i][1] & hmask] = i
                            dsize *= 2; ST['dict_expande'] += 1
        si += 1
        if variant == 1:
            if cur in (0x0F, 0x0E):
                idx = src[si]; si += 1
                if idx >= 128:
                    idx2 = src[si]; si += 1
                    if idx2 >= 128:
                        idx = ((idx & 0x1F) << 14) | ((idx2 & 0x7F) << 7) | src[si]; si += 1; ST['t1_idx3'] += 1
                    else:
                        idx = ((idx & 0x7F) << 7) | idx2
                    if idx >= dsize: raise ValueError("text idx")
                flip = 0x20 if cur == 0x0E else 0; ST['t1_flip'] += (cur == 0x0E)
                word = True
            else:
                word = False
        else:
            if cur >= 0x80:
                flip = 0
                if cur == 0x80:
                    flip = 0x20; cur = src[si]; si += 1; ST['t2_flip'] += 1
                idx = cur & 0x7F; one = idx < 64
                if idx >= 64:
                    if idx >= 112:
                        idx = ((idx & 0x0F) << 16) | (src[si] << 8) | src[si + 1]; si += 2; idx += 8255; ST['t2_idx3'] += 1
                    else:
                        idx = ((idx & 0x1F) << 8) | src[si]; si += 1; idx += 63; ST['t2_idx2'] += 1
                    if idx >= dsize: raise ValueError("text idx")
                if idx == 0: raise ValueError("text idx0")
                idx -= 1 if one else 0
                word = True
            else:
                word = False
        if word:
            w = ent[idx][0]; length = (ent[idx][2] >> 24) & 255
            if length > 1:
                if wrun: dst.append(0x20)
                wrun = True; anchor = si
            else:
                if length == 0: raise ValueError("text len0")
                wrun = False; anchor = si - 1
            wb = bytearray(w[:length]); wb[0] ^= flip
            dst += wb
        else:
            if variant == 2 and cur == 0x0F:
                dst.append(src[si]); si += 1; ST['t2_esc'] += 1
            else:
                if crlf and cur == 0x0A: dst.append(0x0D); ST['crlf'] += 1
                dst.append(cur)
            wrun = False; anchor = si - 1
    if si != count: raise ValueError("text end %d %d" % (si, count))
    return bytes(dst)

# ----------------------------------------------------------------------------- container
def decode(z):
    orig = int.from_bytes(z[0:4], 'little'); level = z[4]
    ntr = 5
    bsz = kz_blocksize(orig)
    blk = max(bsz + 512, bsz + (bsz >> 4))
    bs = Bits(z, 5); out = bytearray()
    while True:
        lr = 3 + bs.bits(5); read = bs.bits(lr)
        if read == 0: break
        start = bs.p
        mode = bs.bits(8)
        copy = bool(mode & 0x80); tcopy = copy and bool(mode & 0x10)
        if (tcopy and ntr > 4) or (not copy and (mode & 0x10)): skip = bs.bits(8)
        else: skip = ((mode << 4) | 0x0F) & 0xFF
        dsz = 1 + ((mode >> 5) & 3)
        pre = bs.bits(8 * dsz)
        bs.bits(8)
        r = (read + 7) >> 3
        ST['copia_cruda' if copy and not tcopy else 'copia_transf' if tcopy else 'normal'] += 1; ST['skip=%02x' % skip] += 1
        if copy and not tcopy:
            out += bytes(bs.bytes_(8 * pre))
        else:
            if tcopy: data = bytes(bs.bytes_(8 * pre))
            elif level == 5: data = ans0_decode(bs, pre)
            else: data = fpaq_decode(bs, pre)
            # buffer lengths as in DecodingTask / TransformSequence
            LA = max(blk, pre + 512); LD = blk
            lens = {'in': LA, 'out': LD, 'buf': 0}
            cin, cout = 'in', 'out'
            for i in range(ntr - 1, -1, -1):
                if skip & (1 << (7 - i)): continue
                if lens[cout] < LD:
                    if cout in ('in', 'out'): cout = 'buf'
                    if lens[cout] < LD: lens[cout] = LD
                cap = lens[cout]
                if i == 4: data = zrlt_inverse(data, len(data), cap)
                elif i == 3: data = rank_inverse(data, len(data)) if level == 5 else srt_inverse(data, len(data))
                elif i == 2: data = bwt_inverse(data, len(data))
                elif i == 1: data = utf_inverse(data, len(data), cap)
                else: data = text_inverse(data, len(data), cap, bsz, 2 if (data[0] & 0x10) else 1)
                cin, cout = cout, cin
            out += data
        if bs.p - start != read: raise ValueError("block bits %d != %d" % (bs.p - start, read))
    if len(out) != orig: raise ValueError("size %d != %d" % (len(out), orig))
    return bytes(out)

if __name__ == "__main__":
    z = open(sys.argv[1], "rb").read()
    o = decode(z)
    if len(sys.argv) > 2: open(sys.argv[2], "wb").write(o)
    print(len(o))
    if os.environ.get('REFSTAT'): print(dict(ST))
