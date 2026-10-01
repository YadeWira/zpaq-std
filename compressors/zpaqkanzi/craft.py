#!/usr/bin/env python3
"""craft.py raw_stream orig_file level pos0,pos1,... out
Takes a headerless kanzi stream written with a SUBSET of a level's transforms (e.g.
"BWT+ZRLT") and rewrites every block header so that the same payload reads as the
level's full 5-transform chain with the missing transforms skipped. pos[j] = position
in the full chain of the subset's j-th transform. The result (with zpaq-std's 5-byte
header) is checked afterwards with kanzi's own decoder (kdec) as the oracle."""
import sys
M32 = 0xFFFFFFFF

class R:
    def __init__(s, d): s.d = d; s.p = 0
    def bits(s, n):
        v = 0
        for _ in range(n): v = (v << 1) | ((s.d[s.p >> 3] >> (7 - (s.p & 7))) & 1); s.p += 1
        return v
class W:
    def __init__(s): s.b = []
    def put(s, v, n):
        for i in range(n - 1, -1, -1): s.b.append((v >> i) & 1)
    def bytes(s):
        b = s.b + [0] * (-len(s.b) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))

def mix(c, h, v): c ^= (h * (~v & M32)) & M32; c = ((c << 13) | (c >> 19)) & M32; return (c * 5 + 0x52DCE729) & M32
def cksum(mode, skip, pre, ln):
    h = 0x1E35A7BD; c = (h * 0x01030507) & M32
    for v in (mode, skip, pre, ln >> 32, ln & M32): c = mix(c, h, v)
    return ((c >> 23) ^ (c >> 3)) & 0xFF

raw = open(sys.argv[1], 'rb').read(); orig = open(sys.argv[2], 'rb').read()
level = int(sys.argv[3]); pos = [int(x) for x in sys.argv[4].split(',')]; nsub = len(pos)
r = R(raw); w = W()
while True:
    lr = 3 + r.bits(5); read = r.bits(lr)
    if read == 0: break
    start = r.p
    mode = r.bits(8)
    copy = bool(mode & 0x80); tcopy = copy and bool(mode & 0x10)
    if (tcopy and nsub > 4) or (not copy and (mode & 0x10)): skip = r.bits(8)
    else: skip = ((mode << 4) | 0x0F) & 0xFF
    dsz = 1 + ((mode >> 5) & 3); pre = r.bits(8 * dsz); r.bits(8)
    hdr = r.p - start
    payload = [r.bits(1) for _ in range(read - hdr)]
    if copy and not tcopy:
        nmode, nskip, extra = mode, None, 0
    else:
        nskip = 0xFF
        for j in range(nsub):
            if not (skip & (1 << (7 - j))): nskip &= ~(1 << (7 - pos[j])) & 0xFF
        nmode = (mode & 0xE0) | 0x10
        extra = 8
    nhdr = 8 + extra + 8 * dsz + 8
    nread = nhdr + len(payload)
    nlr = max(3, nread.bit_length())
    w.put(nlr - 3, 5); w.put(nread, nlr)
    w.put(nmode, 8)
    if nskip is not None: w.put(nskip, 8)
    w.put(pre, 8 * dsz)
    w.put(cksum(nmode, nskip if nskip is not None else (((mode << 4) | 0x0F) & 0xFF), pre, nread), 8)
    for b in payload: w.put(b, 1)
w.put(0, 5); w.put(0, 3)
n = len(orig)
open(sys.argv[5], 'wb').write(n.to_bytes(4, 'little') + bytes([level]) + w.bytes())
