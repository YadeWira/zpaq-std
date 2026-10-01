#!/usr/bin/env python3
"""Reference decoder for zpaq-std -ma:kanzi levels 8 and 9 (kanzi 2.6.0, bitstream
v7, headerless). A literal translation of kanzi's C++ decoder.

  level 8: transforms [EXE, RLT, TEXT, UTF, DNA], entropy TPAQ
  level 9: transforms [EXE, RLT, TEXT, UTF, DNA], entropy TPAQX

TPAQ is kanzi's TPAQPredictor (after Tangelo 2.4 / PAQ8) behind the binary entropy
decoder of level 7. Integer semantics follow C++: 32-bit wraparound where the C++
code multiplies or adds in (u)int, arithmetic right shifts on signed values.
The state tables are read from kanzi's TPAQPredictor.hpp.

Reuses ref.py (bits, DNA), ref3.py (EXE), ref5.py (UTF, TEXT, buffer sizes) and
ref7.py (the binary decoder's chunking)."""
import sys, os, re, collections, array
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref import Bits, read_varint, dna_inverse
from ref3 import exe_inverse
from ref5 import utf_inverse, kz_blocksize
import ref5 as _ref5, inspect as _inspect
# TEXT con TPAQX: kanzi le da a la tabla de hash un bit mas (TextCodec1/2:
# _logHashSize = log + 1 si la entropia es "TPAQX"). Mismo codigo de ref5.py, con
# ese parametro.
_tsrc = _inspect.getsource(_ref5.text_inverse)
assert _tsrc.count('hmask = (1 << log) - 1') == 1
_tsrc = _tsrc.replace('def text_inverse(src, count, outlen, bsz, variant):', 'def text_inverse(src, count, outlen, bsz, variant, xlog=0):')
_tsrc = _tsrc.replace('hmask = (1 << log) - 1', 'hmask = (1 << (log + xlog)) - 1')
exec(_tsrc, _ref5.__dict__)
text_inverse = _ref5.text_inverse
ST = collections.Counter()
M32 = 0xFFFFFFFF
M56 = (1 << 56) - 1
def s32(v): v &= M32; return v - (1 << 32) if v & 0x80000000 else v
def log2(x): return x.bit_length() - 1

# ----------------------------------------------------------------------------- tables
_kz = None
for d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kanzi'),
          '/home/forum/git/zpaq-std/compressors/kanzi'):
    if os.path.exists(os.path.join(d, 'entropy', 'TPAQPredictor.hpp')): _kz = d; break
_hpp = open(os.path.join(_kz, 'entropy', 'TPAQPredictor.hpp')).read()
def _arr(name):
    i = _hpp.index(name); j = _hpp.index('{', i); k = _hpp.index('};', j)
    return [int(x) for x in re.findall(r'-?\d+', re.sub(r'//[^\n]*', '', _hpp[j:k]))]
_st = _arr('STATE_TRANSITIONS[2][256]')
assert len(_st) == 512
TRANS = [_st[:256], _st[256:]]
STATE_MAP = _arr('STATE_MAP[]'); assert len(STATE_MAP) == 256
MATCH_PRED = _arr('MATCH_PRED[]'); assert len(MATCH_PRED) == 88

INV_EXP = [0, 8, 22, 47, 88, 160, 283, 492, 848, 1451, 2459, 4117, 6766, 10819, 16608, 24127,
           32768, 41409, 48928, 54717, 58770, 61419, 63077, 64085, 64688, 65044, 65253, 65376,
           65448, 65489, 65514, 65528, 65536]
SQUASH = [0] * 4096
for x in range(1, 4096):
    w = x & 127; y = x >> 7
    SQUASH[x - 1] = (INV_EXP[y] * (128 - w) + INV_EXP[y + 1] * w) >> 11
SQUASH[4095] = 4095
def squash(d):
    if d >= 2048: return 4095
    return 0 if d <= -2048 else SQUASH[d + 2047]
STRETCH = [0] * 4096
_n = 0
for x in range(-2047, 2048):
    sq = squash(x)
    while _n <= sq:
        STRETCH[_n] = x; _n += 1
    if _n >= 4096: break
STRETCH[4095] = 2047

class APM:
    """LogisticAdaptiveProbMap<false, RATE>"""
    def __init__(s, n, rate):
        s.rate = rate; s.idx = 0
        base = [squash((j - 16) * 128) << 4 for j in range(33)]
        s.d = base * n
    def get(s, bit, pr, ctx):
        d = s.d; g = (-bit) & 65528
        d[s.idx] = (d[s.idx] + (((g - d[s.idx]) >> s.rate) + bit)) & 0xFFFF
        d[s.idx + 1] = (d[s.idx + 1] + (((g - d[s.idx + 1]) >> s.rate) + bit)) & 0xFFFF
        pr = STRETCH[pr]
        s.idx = ((pr + 2048) >> 7) + 33 * ctx
        w = pr & 127
        return ((d[s.idx] << 7) + (d[s.idx + 1] - d[s.idx]) * w) >> 11

HASH = 0x7FEB352D
class TPAQ:
    def __init__(s, x, blocksize, size):
        s.x = x
        rbsz = blocksize; absz = size
        if rbsz >= 64 << 20: st = 1 << 28
        elif rbsz >= 16 << 20: st = 1 << 27
        elif rbsz >= 4 << 20: st = 1 << 26
        else: st = (1 << 24) if rbsz >= 1 << 20 else (1 << 22)
        if absz >= 32 << 20: mx = 1 << 16
        elif absz >= 16 << 20: mx = 1 << 15
        elif absz >= 8 << 20: mx = 1 << 14
        elif absz >= 4 << 20: mx = 1 << 13
        else: mx = (1 << 11) if absz >= 1 << 20 else (1 << 8)
        bsz = min(rbsz, 64 << 20)
        mxsz = absz * 16 if absz < (1 << 26) else (1 << 30)
        hs = min(16 << 20, mxsz)
        bsz = 1 << log2(bsz); hs = 1 << log2(hs)
        e = 2 if x else 0
        mx <<= e; st <<= e; hs <<= e
        if hs > (1 << 30): hs = 1 << 30
        s.stmask = st - 1; s.mxmask = (mx - 1) & ~1; s.hmask = hs - 1; s.bmask = bsz - 1
        ST['tpaq_st%d_mx%d_h%d_b%d' % (log2(st), log2(mx), log2(hs), log2(bsz))] += 1
        # mixers: w[8], p[8], pr, skew, lr
        s.mw = [[32768] * 8 for _ in range(mx)]
        s.mp = [[0] * 8 for _ in range(mx)]
        s.mpr = [2048] * mx; s.mskew = [0] * mx; s.mlr = [60 << 7] * mx
        s.big = bytearray(st); s.sm0 = bytearray(1 << 16); s.sm1 = bytearray(1 << 24)
        s.hashes = array.array('i', bytes(4 * hs)); s.buf = bytearray(bsz)
        s.sse0 = APM(256, 6 if x else 7); s.sse1 = APM(65536 if x else 256, 7)
        s.pr = 2048; s.c0 = 1; s.c4 = 0; s.c8 = 0; s.pos = 0; s.bpos = 8; s.bin = 0
        s.mlen = 0; s.mpos = 0; s.mval = 0; s.hash = 0; s.mix = 0
        # context pointers: (array, index)
        s.cp = [(s.sm0, 0), (s.sm1, 0), (s.big, 0), (s.big, 0), (s.big, 0), (s.big, 0), (s.big, 0)]
        s.ctx = [0] * 7
    def hashf(s, x, y):
        h = s32(((x * HASH) & M32) ^ ((y * HASH) & M32))
        return s32((h >> 1) ^ (h >> 9) ^ ((x & M32) >> 2) ^ ((y & M32) >> 3) ^ HASH)
    @staticmethod
    def cctx(cid, cx):
        cx = (cx * 987654323 + cid) & M32
        cx = ((cx << 16) | (cx >> 16)) & M32
        return s32(cx * 123456791 + cid)
    def mixer_update(s, m, bit):
        err = (((bit << 12) - s.mpr[m]) * s.mlr[m]) >> 10
        if err == 0: return
        if (((11 << 7) - s.mlr[m]) & M32) >> 31: s.mlr[m] -= 1
        s.mskew[m] = s32(s.mskew[m] + err)
        w = s.mw[m]; p = s.mp[m]
        for i in range(8): w[i] = s32(w[i] + ((p[i] * err) >> 12))
    def mixer_get(s, m, ps):
        s.mp[m] = list(ps); w = s.mw[m]
        dot = 0
        for i in range(8): dot = s32(dot + s32(ps[i] * w[i]))
        s.mpr[m] = squash(s32(dot + s.mskew[m] + 65536) >> 17)
        return s.mpr[m]
    def find_match(s):
        if s.mlen > 0:
            if s.mlen < 88: s.mlen += 1
            s.mpos += 1
            return
        s.mpos = s.hashes[s.hash]
        if s.mpos != 0 and ((s.pos - s.mpos) & M32) <= s.bmask:
            r = s.mlen + 2; b = s.buf; bm = s.bmask
            while r <= 88:
                if b[(s.pos - r - 1) & bm] != b[(s.mpos - r - 1) & bm]: break
                if b[(s.pos - r) & bm] != b[(s.mpos - r) & bm]: break
                r += 2
            s.mlen = r - 2
    def get(s): return s.pr
    def update(s, bit):
        s.mixer_update(s.mix, bit)
        s.c0 += s.c0 + bit
        s.bpos -= 1
        if s.bpos == 0:
            s.buf[s.pos & s.bmask] = s.c0 & 255
            s.pos += 1
            s.c8 = ((s.c8 << 8) | ((s.c4 >> 24) & 0xFF)) & M32
            s.c4 = ((s.c4 << 8) | (s.c0 & 0xFF)) & M32
            s.hash = ((((s.hash * HASH) & M32) << 4) + s.c4) & M32 & s.hmask
            s.c0 = 1; s.bpos = 8
            s.bin += (s.c4 >> 7) & 1
            s.mix = (s.c4 & s.mxmask) + (1 if s.mlen != 0 else 0)
            c = s.ctx
            c[0] = (s.c4 & 0xFF) << 8
            c[1] = (s.c4 & 0xFFFF) << 8
            c[2] = s.cctx(2, s.c4 & 0x00FFFFFF)
            c[3] = s.cctx(3, s.c4)
            if s.bin < (s.pos >> 2):
                c[4] = s.cctx(c[1], s.c4 ^ (s.c8 & 0xFFFF))
                c[5] = (s.c8 & 0xF0F0F000) | ((s.c4 & 0xF0F0F000) >> 4)
                if s.x:
                    h1 = (s.c4 & 0x4F4FFFFF) if (s.c4 & 0x80808080) == 0 else (s.c4 & 0x80808080)
                    h2 = (s.c8 & 0x4F4FFFFF) if (s.c8 & 0x80808080) == 0 else (s.c8 & 0x80808080)
                    c[6] = s.hashf((h1 << 2) & M32, h2 >> 2)
            else:
                c[4] = s.cctx((HASH + s.mlen) & M32, s.c4 ^ (s.c4 & 0x000FFFFF))
                c[5] = c[0] | ((s.c8 << 16) & M32)
                if s.x:
                    c[6] = s.hashf(s.c4 & 0xFFFF0000, s.c8 >> 16)
            s.find_match()
            s.mval = s.buf[s.mpos & s.bmask] | 0x100
            s.hashes[s.hash] = s.pos
        c = s.ctx; c0 = s.c0; sm = s.stmask
        idx2 = ((c[2] & M32) + c0) & sm
        idx3 = ((c[3] & M32) + c0) & sm
        idx4 = ((c[4] & M32) + c0) & sm
        idx5 = ((c[5] & M32) ^ c0) & sm
        t = TRANS[bit]
        for k in range(6):
            a, i = s.cp[k]; a[i] = t[a[i]]
        s.cp[0] = (s.sm0, c[0] + c0); s.cp[1] = (s.sm1, c[1] + c0)
        s.cp[2] = (s.big, idx2); s.cp[3] = (s.big, idx3); s.cp[4] = (s.big, idx4); s.cp[5] = (s.big, idx5)
        ps = [STATE_MAP[a[i]] for (a, i) in s.cp[:6]]
        if s.mlen == 0: p7 = 0
        else:
            mp = s.mval >> s.bpos
            if s.c0 == mp:
                p7 = MATCH_PRED[s.mlen - 1] if ((s.mval >> (s.bpos - 1)) & 1) else -MATCH_PRED[s.mlen - 1]
            else:
                s.mlen = 0; p7 = 0
        if not s.x:
            p = s.mixer_get(s.mix, ps + [p7, p7])
            if s.bin < (s.pos >> 3):
                p = (3 * s.sse0.get(bit, p, s.c0) + p) >> 2
        else:
            idx6 = ((c[6] & M32) + c0) & sm
            a, i = s.cp[6]; a[i] = t[a[i]]
            s.cp[6] = (s.big, idx6)
            p6 = STATE_MAP[s.big[idx6]]
            p = s.mixer_get(s.mix, ps + [p6, p7])
            if s.bin < (s.pos >> 3):
                p = s.sse1.get(bit, p, c[0] + s.c0)
            else:
                if s.bin >= (s.pos >> 2):
                    p = (3 * s.sse0.get(bit, p, s.c0) + p) >> 2
                p = (3 * s.sse1.get(bit, p, c[0] + s.c0) + p) >> 2
        s.pr = p + (1 if p < 2048 else 0)

def bin_decode(bs, count, pred):
    """BinaryEntropyDecoder (same chunking as ref7.cm_decode)."""
    if count == 0: return b''
    length = max(count, 64)
    if length >= (1 << 26):
        length = (count >> 3) if (length // 8 < (1 << 26)) else (count >> 4)
    low, high = 0, M56
    out = bytearray(); start = 0
    while start < count:
        n = min(length, count - start); ST['bin_chunk'] += 1
        sz = read_varint(bs)
        if sz > min(n << 5, M32 >> 3): raise ValueError("bin size")
        cur = bs.bits(56)
        buf = bytes(bs.bytes_(8 * sz)); idx = 0
        for _ in range(n):
            v = 0
            for _b in range(8):
                pr = pred.get()
                split = ((((high - low) >> 4) * pr) >> 8) + low
                if split >= cur: bit = 1; high = split
                else: bit = 0; low = split + 1
                pred.update(bit)
                v = (v << 1) | bit
                if ((low ^ high) >> 24) == 0:
                    if idx + 4 > sz: raise ValueError("bin payload underrun")
                    low = (low << 32) & M56
                    high = ((high << 32) | M32) & M56
                    cur = ((cur << 32) | int.from_bytes(buf[idx:idx + 4], 'big')) & M56; idx += 4
            out.append(v)
        if idx != sz: raise ValueError("bin payload %d != %d" % (idx, sz))
        start += n
    return bytes(out)

# ----------------------------------------------------------------------------- RLT
def rlt_inverse(src, count, cap):
    ST['rlt'] += 1
    esc = src[0]; si = 1; dst = bytearray()
    if si < count and src[si] == esc:
        si += 1
        if si < count and src[si] != 0: raise ValueError("rlt start")
        dst.append(esc); si += 1
    while si < count:
        j = src.find(bytes([esc]), si, count)
        if j < 0: j = count
        if j > si:
            if j - si > cap - len(dst): raise ValueError("rlt lit")
            dst += src[si:j]; si = j
        if si >= count: break
        si += 1
        if si >= count: raise ValueError("rlt end")
        run = src[si]; si += 1
        if run == 0:
            dst.append(esc); ST['rlt_escape'] += 1; continue
        if run == 0xFF:
            if si + 1 >= count: raise ValueError("rlt run2")
            run = ((src[si] << 8) | src[si + 1]) + (31 << 8); si += 2; ST['rlt_run2'] += 1
        elif run >= 224:
            if si >= count: raise ValueError("rlt run1")
            run = (((run - 224) << 8) | src[si]) + 224; si += 1; ST['rlt_run1'] += 1
        run += 2
        if len(dst) + run > cap or run > 0xFFFF + (31 << 8) + 2: raise ValueError("rlt run")
        if not dst: raise ValueError("rlt run first")
        dst += bytes([dst[-1]]) * run; ST['rlt_run'] += 1
    return bytes(dst)

# ----------------------------------------------------------------------------- container
def decode(z):
    orig = int.from_bytes(z[0:4], 'little'); level = z[4]
    if level not in (8, 9): raise ValueError("level")
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
        ST['copia_cruda' if copy and not tcopy else 'copia_transf' if tcopy else 'normal'] += 1
        ST['skip=%02x' % skip] += 1
        if copy and not tcopy:
            out += bytes(bs.bytes_(8 * pre))
        else:
            data = bytes(bs.bytes_(8 * pre)) if tcopy else bin_decode(bs, pre, TPAQ(level == 9, bsz, pre))
            LA = max(blk, pre + 512); LD = blk
            lens = {'in': LA, 'out': LD, 'buf': 0}
            cin, cout = 'in', 'out'
            names = ['EXE', 'RLT', 'TEXT', 'UTF', 'DNA']
            for i in range(ntr - 1, -1, -1):
                if skip & (1 << (7 - i)): continue
                if lens[cout] < LD:
                    if cout in ('in', 'out'): cout = 'buf'
                    if lens[cout] < LD: lens[cout] = LD
                cap = lens[cout]
                nm = names[i]; ST['t_' + nm] += 1
                if nm == 'DNA': data = dna_inverse(data, len(data))
                elif nm == 'UTF': data = utf_inverse(data, len(data), cap)
                elif nm == 'TEXT': data = text_inverse(data, len(data), cap, bsz, 2 if (data[0] & 0x10) else 1, 1 if level == 9 else 0)
                elif nm == 'RLT': data = rlt_inverse(data, len(data), cap)
                else: data = exe_inverse(data, len(data), cap)
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
