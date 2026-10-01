#!/usr/bin/env python3
"""Reference decoder for zpaq-std -ma:kanzi level 7 (kanzi 2.6.0, bitstream v7,
headerless). A literal translation of kanzi's C++ decoder.

  level 7: transforms [LZP, TEXT, UTF, BWT, LZP], entropy CM

Reuses ref.py (bits) and ref5.py (BWT, UTF, TEXT, buffer sizes). Block layout as
ref5.py: orig (4 LE), level (1), kanzi's headerless stream (zpaq-std inserts the
static dictionary after the header; this reference reads the stream without it)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref import Bits, read_varint
from ref5 import text_inverse, utf_inverse, bwt_inverse, kz_blocksize
ST = collections.Counter()
M32 = 0xFFFFFFFF
M56 = (1 << 56) - 1

# ----------------------------------------------------------------------------- CM
def cm_decode(bs, count):
    """BinaryEntropyDecoder with CMPredictor (bitstream 7): one chunk per block
    unless the block is 64 MB or more; a new predictor for every block."""
    if count == 0: return b''
    length = max(count, 64)
    if length >= (1 << 26):
        length = (count >> 3) if (length // 8 < (1 << 26)) else (count >> 4)
    # CMPredictor
    c1 = [[32768] * 257 for _ in range(256)]
    c2 = [[j << 12 for j in range(17)] for _ in range(512)]
    for r in c2: r[16] = 65535
    st = {'ctx': 1, 'run': 0, 'c1': 0, 'c2': 0}
    pc1 = c1[1]
    pc2 = None
    low, high = 0, M56
    out = bytearray()
    start = 0
    while start < count:
        n = min(length, count - start); ST['cm_chunk'] += 1
        sz = read_varint(bs)
        if sz > min(n << 5, M32 >> 3): raise ValueError("cm size")
        cur = bs.bits(56)
        buf = bytes(bs.bytes_(8 * sz))
        idx = 0
        for _ in range(n):
            for _b in range(8):
                # get()
                ctx = st['ctx']; a = st['c1']; b = st['c2']
                p = (13 * (pc1[256] + pc1[a]) + 6 * pc1[b]) >> 5
                pc2 = c2[ctx | st['run']]; k = p >> 12
                pr = (p + p + 3 * (pc2[k] + pc2[k + 1]) + 64) >> 7
                # decodeBit
                split = ((((high - low) >> 4) * pr) >> 8) + low
                if split >= cur:
                    bit = 1; high = split
                else:
                    bit = 0; low = split + 1
                # update(bit)
                if bit == 0:
                    pc1[256] -= pc1[256] >> 2
                    pc1[a] -= pc1[a] >> 4
                    pc2[k] -= pc2[k] >> 6
                    pc2[k + 1] -= pc2[k + 1] >> 6
                    ctx += ctx
                else:
                    pc1[256] -= (pc1[256] - 65536 + 16) >> 2
                    pc1[a] -= (pc1[a] - 65536 + 16) >> 4
                    pc2[k] -= (pc2[k] - 65536 + 16) >> 6
                    pc2[k + 1] -= (pc2[k + 1] - 65536 + 16) >> 6
                    ctx += ctx + 1
                if ctx > 255:
                    st['c2'] = st['c1']; st['c1'] = ctx & 255; ctx = 1
                    st['run'] = 0x100 if st['c1'] == st['c2'] else 0
                    pc1 = c1[1]
                else:
                    pc1 = c1[ctx]
                st['ctx'] = ctx
                if ((low ^ high) >> 24) == 0:
                    if idx + 4 > sz: raise ValueError("cm payload underrun")
                    low = (low << 32) & M56
                    high = ((high << 32) | M32) & M56
                    cur = ((cur << 32) | int.from_bytes(buf[idx:idx + 4], 'big')) & M56; idx += 4
            out.append(st['c1'])
        if idx != sz: raise ValueError("cm payload %d != %d" % (idx, sz))
        start += n
    return bytes(out)

# ----------------------------------------------------------------------------- LZP
def lzp_inverse(src, count, cap):
    if count < 4: raise ValueError("lzp short")
    if cap < count: raise ValueError("lzp cap")
    ST['lzp'] += 1
    hashes = [0] * 65536
    dst = bytearray(src[0:4])
    ctx = int.from_bytes(dst[0:4], 'little')
    si = 4
    while si < count:
        h = ((0x7FEB352D * ctx) & M32) >> 16
        ref = hashes[h]; hashes[h] = len(dst)
        if src[si] != 0xFC or ref == 0:
            if len(dst) >= cap: raise ValueError("lzp out")
            ctx = ((ctx << 8) | src[si]) & M32; dst.append(src[si]); si += 1
            continue
        si += 1
        if si >= count: raise ValueError("lzp end")
        if src[si] == 0xFF:
            ST['lzp_escape'] += 1
            ctx = ((ctx << 8) | 0xFC) & M32; dst.append(0xFC); si += 1
            continue
        ml = 64
        if src[si] == 0xFE:
            while si < count and src[si] == 0xFE: si += 1; ml += 254
            ST['lzp_long'] += 1
            if si >= count: raise ValueError("lzp end2")
        ml += src[si]; si += 1
        if ml > cap - len(dst): raise ValueError("lzp match")
        ST['lzp_match'] += 1
        for i in range(ml): dst.append(dst[ref + i])
        ctx = int.from_bytes(dst[-4:], 'little')
    return bytes(dst)

# ----------------------------------------------------------------------------- container
def decode(z):
    orig = int.from_bytes(z[0:4], 'little'); level = z[4]
    if level != 7: raise ValueError("level")
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
            data = bytes(bs.bytes_(8 * pre)) if tcopy else cm_decode(bs, pre)
            LA = max(blk, pre + 512); LD = blk
            lens = {'in': LA, 'out': LD, 'buf': 0}
            cin, cout = 'in', 'out'
            names = ['LZP', 'TEXT', 'UTF', 'BWT', 'LZP']
            for i in range(ntr - 1, -1, -1):
                if skip & (1 << (7 - i)): continue
                if lens[cout] < LD:
                    if cout in ('in', 'out'): cout = 'buf'
                    if lens[cout] < LD: lens[cout] = LD
                cap = lens[cout]
                nm = names[i]; ST['t_%s%d' % (nm, i)] += 1
                if nm == 'LZP': data = lzp_inverse(data, len(data), cap)
                elif nm == 'BWT': data = bwt_inverse(data, len(data))
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
