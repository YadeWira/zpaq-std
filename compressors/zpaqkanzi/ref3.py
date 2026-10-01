#!/usr/bin/env python3
"""Reference decoder for zpaq-std -ma:kanzi levels 3 and 4 (kanzi 2.6.0, bitstream
v7, headerless). A literal translation of kanzi's C++ decoder.

  level 3: transforms [TEXT, UTF, PACK, MM, LZX],       entropy HUFFMAN
  level 4: transforms [TEXT, UTF, EXE, PACK, MM, ROLZ], entropy NONE

Reuses ref.py (bits, Huffman, LZX, alias) and ref5.py (TEXT, UTF, buffer sizes).
Block layout as ref5.py: orig (4 LE), level (1), kanzi's headerless stream (zpaq-std
inserts the static dictionary after the header; this reference reads the stream
without it, like ref5.py)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref import Bits, read_varint, decode_alphabet, huffman_decode, lzx_inverse, dna_inverse
from ref5 import text_inverse, utf_inverse, kz_blocksize, log2
ST = collections.Counter()
M32 = 0xFFFFFFFF
le32 = lambda b, i: b[i] | b[i + 1] << 8 | b[i + 2] << 16 | b[i + 3] << 24
be32 = lambda b, i: b[i] << 24 | b[i + 1] << 16 | b[i + 2] << 8 | b[i + 3]
def s32(v): v &= M32; return v - (1 << 32) if v & 0x80000000 else v

# ----------------------------------------------------------------------------- ANS order 0 / 1
def ans_decode(bs, count, order, chunk):
    if count <= 32:
        return bytes(bs.bytes_(8 * count))
    csize = min(chunk << (8 * order), 1 << 27)
    out = bytearray()
    while len(out) < count:
        n = min(csize, count - len(out))
        lr = 8 + bs.bits(3)
        if lr > 15: raise ValueError("ans logRange")
        scale = 1 << lr; llr = log2(lr) + 1; mask = scale - 1
        dim = 255 * order + 1
        f2s = [None] * dim; cum = [None] * dim; fq = [None] * dim
        total = 0; single = None
        for k in range(dim):
            alpha = decode_alphabet(bs)
            if not alpha:
                if order == 1 and k == 0: raise ValueError("ans ctx0")
                f2s[k] = bytes(scale); cum[k] = [0] * 256; fq[k] = [0] * 256
                if order == 1: fq[k][0] = min(scale, scale - 1); cum[k][0] = 0   # reset(0, scale)
                continue
            f = [0] * 256; chk = 8 if len(alpha) >= 64 else 6; s = 0
            for i in range(1, len(alpha), chk):
                lm = bs.bits(llr)
                if lm > lr: raise ValueError("ans logMax")
                for j in range(i, min(i + chk, len(alpha))):
                    fr = 1 if lm == 0 else bs.bits(lm) + 1
                    f[alpha[j]] = fr; s += fr
            if scale <= s: raise ValueError("ans sum")
            f[alpha[0]] = scale - s
            t = bytearray(scale); cu = [0] * 256; fqq = [0] * 256; c = 0
            for i in range(256):
                if f[i] == 0: continue
                t[c:c + f[i]] = bytes([i]) * f[i]; cu[i] = c; fqq[i] = min(f[i], scale - 1); c += f[i]
            f2s[k] = bytes(t); cum[k] = cu; fq[k] = fqq
            total += len(alpha)
            if order == 0 and len(alpha) == 1: single = alpha[0]
        if total == 0: raise ValueError("ans empty")
        if order == 0 and single is not None:
            ST['ans_1sym'] += 1; out += bytes([single]) * n; continue
        sz = read_varint(bs)
        st = [bs.bits(32) for _ in range(4)]
        buf = bytes(bs.bytes_(8 * sz)) + bytes(600)
        p = 0
        res = bytearray(n); c4 = n & ~3
        def step(k, ctx, sym):
            nonlocal p
            x = st[k]
            x = (fq[ctx][sym] * (x >> lr) + (x & mask) - cum[ctx][sym]) & M32
            if x < (1 << 15): x = ((x << 16) | (buf[p] << 8) | buf[p + 1]) & M32; p += 2
            st[k] = x
        if order == 0:
            for i in range(0, c4, 4):
                for k, si in ((3, 0), (2, 1), (1, 2), (0, 3)):
                    sym = f2s[0][st[k] & mask]; res[i + si] = sym; step(k, 0, sym)
        else:
            ST['ans_orden1'] += 1
            q = c4 >> 2; prv = [0, 0, 0, 0]
            for j in range(q):
                cur = [f2s[prv[k]][st[k] & mask] for k in range(4)]   # cur0..cur3 (before updates)
                for k in (3, 2, 1, 0): step(k, prv[k], cur[k])
                for k in range(4): res[k * q + j] = cur[k]; prv[k] = cur[k]
        for i in range(c4, n): res[i] = buf[p]; p += 1
        if p != sz: raise ValueError("ans payload %d != %d" % (p, sz))
        out += res
    return bytes(out)

# ----------------------------------------------------------------------------- transforms
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kanzi', 'transform', 'FSDCodec.cpp')).read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kanzi', 'transform', 'FSDCodec.cpp')) \
    else open('/home/forum/git/zpaq-std/compressors/kanzi/transform/FSDCodec.cpp').read()
_i = _src.index('ZIGZAG2[256] = {')
ZIGZAG2 = [int(x) for x in _src[_i + len('ZIGZAG2[256] = {'):_src.index('}', _i)].replace('\n', ' ').split(',') if x.strip()]
assert len(ZIGZAG2) == 256 and all(ZIGZAG2[v] == ((v >> 1) ^ -(v & 1)) for v in range(256))

def fsd_inverse(src, count, cap):
    mode = src[0]; coding = mode & 1; bucketed = (mode & 2) != 0; dist = src[1]
    if dist < 1 or (dist > 4 and dist not in (8, 16)) or (mode & ~3): raise ValueError("fsd")
    ST['fsd_' + ('xor' if coding else 'delta') + ('_bucket' if bucketed else '')] += 1
    dl = count - 2
    dst = bytearray(max(cap, dl) + 16)
    dst[0:dist] = src[2:2 + dist]
    si = dist + 2; di = dist
    if bucketed:
        tl = dist * (1 << 15)
        for ts in range(0, dl, tl):
            te = min(ts + tl, dl)
            for lane in range(dist):
                pos = ts + lane + (dist if ts == 0 else 0)
                while pos < te:
                    v = src[si]; si += 1
                    dst[pos] = ((dst[pos - dist] + ZIGZAG2[v]) & 255) if coding == 0 else (v ^ dst[pos - dist])
                    pos += dist
        di = dl
    else:
        while si < count and di < cap:
            v = src[si]; si += 1
            dst[di] = ((dst[di - dist] + ZIGZAG2[v]) & 255) if coding == 0 else (v ^ dst[di - dist])
            di += 1
    if si != count: raise ValueError("fsd end")
    return bytes(dst[:di])

def exe_inverse(src, count, cap):
    mode = src[0]
    cs, ce = s32(le32(src, 1)), s32(le32(src, 5))
    si = 9; dst = bytearray()
    if cs < 0 or ce < si or ce > count or cs > ce - si: raise ValueError("exe hdr")
    dst += src[si:si + cs]; si += cs
    if mode == 0x40:
        ST['exe_x86'] += 1
        while si < ce:
            if src[si] == 0x0F:
                if si + 1 >= ce:
                    dst.append(src[si]); si += 1; break
                dst.append(src[si]); si += 1
                if (src[si] & 0xF0) != 0x80:
                    if src[si] == 0x9B:
                        si += 1
                    dst.append(src[si]); si += 1; continue
            elif (src[si] & 0xFE) != 0xE8:
                if src[si] == 0x9B:
                    si += 1
                dst.append(src[si]); si += 1; continue
            if si + 4 >= ce: raise ValueError("exe jmp")
            addr = s32(be32(src, si + 1) ^ 0xF0F0F0F0)
            off = addr - len(dst)
            enc = off if off >= 0 else -((-off) & ((1 << 24) - 1))
            dst.append(src[si]); si += 1
            dst += (enc & M32).to_bytes(4, 'little'); si += 4
            ST['exe_x86_jmp'] += 1
    elif mode == 0x20:
        ST['exe_arm'] += 1
        while si < ce:
            instr = le32(src, si)
            op = instr & (M32 ^ ((1 << 26) - 1))
            if op not in (0x14000000, 0x94000000):
                dst += src[si:si + 4]; si += 4; continue
            addr = (instr & ((1 << 26) - 1)) << 2
            if addr == 0:
                dst += src[si + 4:si + 8]; si += 8; continue
            off = s32(addr - len(dst)) >> 2
            val = op | (off & ((1 << 26) - 1))
            dst += (val & M32).to_bytes(4, 'little'); si += 4
    else:
        raise ValueError("exe mode")
    dst += src[si:count]
    return bytes(dst)

ROLZ_HASH = 200002979
def rolz_read_length(b, pos):
    nxt = b[pos]; pos += 1
    if nxt < 128: return nxt, pos
    ln = nxt & 0x7F
    nxt = b[pos]; pos += 1; ln = (ln << 7) | (nxt & 0x7F)
    if nxt >= 128:
        nxt = b[pos]; pos += 1; ln = (ln << 7) | (nxt & 0x7F)
        if nxt >= 128:
            nxt = b[pos]; pos += 1; ln = (ln << 7) | (nxt & 0x7F)
    return ln, pos

def rolz_inverse(src, count, cap):
    end = be32(src, 0)
    if end <= 4 or end - 4 > cap: raise ValueError("rolz end")
    dend = end - 4; si = 5
    szc = min(dend, 16 << 20); start = 0
    flags = src[4]; lo = flags & 1; mm = 3; delta = 2
    t = flags & 0x0E
    if t == 2: mm, delta = 4, 8
    elif t == 4: mm, delta = 7, 8
    elif t == 8: delta = 3
    lpc = flags >> 4
    if lpc < 2 or lpc > 8: raise ValueError("rolz lpc")
    ST['rolz_lo%d_mm%d_d%d_lpc%d' % (lo, mm, delta, lpc)] += 1
    pc = 1 << lpc; mskc = pc - 1
    counters = [0] * 65536
    out = bytearray()
    while start < dend:
        endc = min(start + szc, dend); szc = endc - start
        sub = src[si:count]
        bs = Bits(bytes(sub) + bytes(16))
        litLen, tkLen, mLenLen, mIdxLen = (bs.bits(32) for _ in range(4))
        lit = ans_decode(bs, litLen, lo, 16384)
        tk = ans_decode(bs, tkLen, 0, 32768)
        lnb = ans_decode(bs, mLenLen, 0, 32768) + bytes(4)
        mi = ans_decode(bs, mIdxLen, 0, 32768)
        si += (bs.p + 7) >> 3
        if tkLen == 0:
            ST['rolz_solo_literales'] += 1
            out += lit[:szc]; start = endc; continue
        matches = [0] * (65536 << lpc)
        base = len(out)                      # output._index
        buf = out                            # buf[i] = out[base + i]
        def key(i):                          # refBuf[i] = buf[i - delta]
            p = base + i - delta
            if mm == 3: return (out[p] | out[p + 1] << 8) & 0xFFFF
            x = int.from_bytes(out[p:p + 8], 'little')
            return ((x * ROLZ_HASH) >> 40) & 0xFFFF
        li = 0; ti = 0; mii = 0; lni = 0
        n = min(dend - base, 8)
        out += lit[li:li + n]; li += n; di = n
        while di < szc:
            token = tk[ti]; ti += 1
            mlen = token & 7
            if mlen == 7:
                x, lni = rolz_read_length(lnb, lni); mlen += mm + x
            else: mlen += mm
            ll = token >> 3
            if token >= 0xF8:
                ll, lni = rolz_read_length(lnb, lni); ll += 31
            if ll > 0:
                out += lit[li:li + ll]
                inc = 0; k = 0
                while k < ll:
                    kk = key(di + k)
                    counters[kk] = (counters[kk] + 1) & mskc
                    matches[(kk << lpc) + counters[kk]] = di + k
                    k += inc >> 6; inc += 1; k += 1
                li += ll; di += ll
                if di >= szc:
                    if di == szc: break
                    raise ValueError("rolz lit")
            idx = mi[mii]; mii += 1
            kk = key(di)
            ref = matches[(kk << lpc) + ((counters[kk] - idx) & mskc)]
            counters[kk] = (counters[kk] + 1) & mskc
            matches[(kk << lpc) + counters[kk]] = di
            for j in range(mlen): out.append(out[base + ref + j])
            di += mlen
        if ti != tkLen or mii != mIdxLen or li != litLen or lni != mLenLen:
            raise ValueError("rolz buffers %d/%d %d/%d %d/%d %d/%d" % (ti, tkLen, mii, mIdxLen, li, litLen, lni, mLenLen))
        start = endc
    if count - si != 4: raise ValueError("rolz tail")
    out += src[si:si + 4]
    return bytes(out)

# ----------------------------------------------------------------------------- container
def decode(z):
    orig = le32(z, 0); level = z[4]
    ntr = 5 if level == 3 else 6
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
            data = bytes(bs.bytes_(8 * pre)) if (tcopy or level == 4) else huffman_decode(bs, pre)
            LA = max(blk, pre + 512); LD = blk
            lens = {'in': LA, 'out': LD, 'buf': 0}
            cin, cout = 'in', 'out'
            names = ['TEXT', 'UTF', 'PACK', 'MM', 'LZX'] if level == 3 else ['TEXT', 'UTF', 'EXE', 'PACK', 'MM', 'ROLZ']
            for i in range(ntr - 1, -1, -1):
                if skip & (1 << (7 - i)): continue
                if lens[cout] < LD:
                    if cout in ('in', 'out'): cout = 'buf'
                    if lens[cout] < LD: lens[cout] = LD
                cap = lens[cout]
                nm = names[i]; ST['t_' + nm] += 1
                if nm == 'LZX': data = lzx_inverse(data, len(data))
                elif nm == 'ROLZ': data = rolz_inverse(data, len(data), cap)
                elif nm == 'MM': data = fsd_inverse(data, len(data), cap)
                elif nm == 'PACK': data = dna_inverse(data, len(data))
                elif nm == 'EXE': data = exe_inverse(data, len(data), cap)
                elif nm == 'UTF': data = utf_inverse(data, len(data), cap)
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
