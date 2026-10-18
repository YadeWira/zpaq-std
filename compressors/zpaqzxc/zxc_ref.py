#!/usr/bin/env python3
# Reference decoder for zxc format 9 frames (no dictionary), written from
# docs/FORMAT.md and the PivCo encoder, to check the ZPAQL against.
# Usage: zxc_ref.py IN OUT
import sys

def varint(b, p):
    x = b[p]
    if x < 0x80: return x, p + 1
    if x < 0xC0: return (x & 0x3F) | (b[p + 1] << 6), p + 2
    if x < 0xE0: return (x & 0x1F) | (b[p + 1] << 5) | (b[p + 2] << 13), p + 3
    raise ValueError('varint')

def huffman(sec, n):
    """PivCo section: 128-byte lengths header, then one run per uncovered internal node."""
    L = [0] * 256
    for i in range(128):
        L[2 * i] = sec[i] & 15; L[2 * i + 1] = sec[i] >> 4
    pay = sec[128:]
    maxd = max(L)
    # canonical codes
    blc = [0] * 12
    for l in L:
        if l: blc[l] += 1
    code = 0; first = [0] * 13
    for l in range(1, 12):
        code = (code + blc[l - 1]) << 1 if l > 1 else 0
        first[l] = code
    nxt = first[:]
    sym_of = {}
    for s in range(256):
        if L[s]:
            sym_of[(L[s], nxt[L[s]])] = s; nxt[L[s]] += 1
    lone = sum(1 for l in L if l) == 1
    # nodes by (depth, prefix); leaf if (d, p) is a code
    def is_leaf(d, p): return (d, p) in sym_of
    # height of complete subtree, None = incomplete; memo
    memo = {}
    def height(d, p):
        if (d, p) in memo: return memo[(d, p)]
        if is_leaf(d, p): h = 0
        elif d >= maxd: h = None
        else:
            a = height(d + 1, 2 * p); b = height(d + 1, 2 * p + 1)
            h = a + 1 if (a is not None and a == b) else None
        memo[(d, p)] = h; return h
    # internal nodes per depth, in prefix order
    internal = []
    if lone:
        internal = [[(0, 0)]]
    # walk the trie level by level
    level = [(0, 0)]; fd = {}
    covered = set()
    order = []
    for d in range(maxd):
        nl = []
        for (dd, p) in level:
            if is_leaf(dd, p): continue
            if (dd, p) in covered:
                covered.add((dd + 1, 2 * p)); covered.add((dd + 1, 2 * p + 1)); continue
            h = height(dd, p)
            if h is not None and h >= 2:
                fd[(dd, p)] = h
                covered.add((dd + 1, 2 * p)); covered.add((dd + 1, 2 * p + 1))
            else:
                fd[(dd, p)] = 0
            order.append((dd, p))
        for (dd, p) in level:
            if not is_leaf(dd, p): nl += [(dd + 1, 2 * p), (dd + 1, 2 * p + 1)]
        level = sorted(nl, key=lambda x: x[1])
    # counts and cursors in run order (parents before children)
    count = {(0, 0): n}; cur = {}; tot = 0
    def bit(pos): return (pay[pos >> 3] >> (pos & 7)) & 1
    for (d, p) in order:
        c = count.get((d, p), 0)
        cur[(d, p)] = tot * 8
        f = fd[(d, p)]
        if f:
            tot += (c * f + 7) // 8
        else:
            ones = sum(bit(tot * 8 + i) for i in range(c))
            count[(d + 1, 2 * p + 1)] = ones; count[(d + 1, 2 * p)] = c - ones
            tot += (c + 7) // 8
    out = bytearray()
    for _ in range(n):
        d, p = 0, 0
        while True:
            if is_leaf(d, p) and not (lone and d == 0):
                out.append(sym_of[(d, p)]); break
            f = fd[(d, p)]
            pos = cur[(d, p)]
            if f:
                # bit j is the branch at relative depth j: the path, MSB first
                v = 0
                for j in range(f): v = (v << 1) | bit(pos + j)
                cur[(d, p)] = pos + f
                out.append(sym_of[(d + f, (p << f) | v)]); break
            b = bit(pos); cur[(d, p)] = pos + 1
            d, p = d + 1, 2 * p + b
    return bytes(out), 128 + tot

def rle(sec, n):
    out = bytearray(); p = 0
    while len(out) < n:
        t = sec[p]; p += 1
        if t < 0x80: out += sec[p:p + t + 1]; p += t + 1
        else: out += bytes([sec[p]]) * ((t & 0x7F) + 4); p += 1
    return bytes(out[:n])

def block(b, out):
    typ = b[0]; size = int.from_bytes(b[3:7], 'little'); pay = b[8:8 + size]
    if typ == 0: out += pay; return
    nseq = int.from_bytes(pay[0:4], 'little'); nlit = int.from_bytes(pay[4:8], 'little')
    el, et, em, eo = pay[8], pay[9], pay[10], pay[11]
    p = 12; start = len(out)
    if typ == 1:
        lc = tc = None
        if el != 0: lc = int.from_bytes(pay[p:p + 4], 'little'); p += 4
        if et == 2: tc = int.from_bytes(pay[p:p + 4], 'little'); p += 4
        if el == 0: lit = pay[p:p + nlit]; p += nlit
        elif el == 1: lit = rle(pay[p:p + lc], nlit); p += lc
        else: lit = huffman(pay[p:p + lc], nlit)[0]; p += lc
        if et == 2: tok = huffman(pay[p:p + tc], nseq)[0]; p += tc
        else: tok = pay[p:p + nseq]; p += nseq
        ow = 1 if eo else 2
        offs = pay[p:p + nseq * ow]; p += nseq * ow
        ex = p; lp = 0
        for i in range(nseq):
            ll = tok[i] >> 4; ml = tok[i] & 15
            if ll == 15: v, ex = varint(pay, ex); ll += v
            if ml == 15: v, ex = varint(pay, ex); ml += v
            ml += 5
            off = (offs[i] if eo else offs[2 * i] | offs[2 * i + 1] << 8) + 1
            out += lit[lp:lp + ll]; lp += ll
            if off > len(out) - start: raise ValueError('offset')
            for _ in range(ml): out.append(out[-off])
        out += lit[lp:nlit]
    elif typ == 2:
        lit = pay[p:p + nlit]; p += nlit
        seq = pay[p:p + 4 * nseq]; p += 4 * nseq; ex = p; lp = 0
        for i in range(nseq):
            off = (seq[4 * i] | seq[4 * i + 1] << 8) + 1; ml = seq[4 * i + 2]; ll = seq[4 * i + 3]
            if ll == 255: v, ex = varint(pay, ex); ll += v
            if ml == 255: v, ex = varint(pay, ex); ml += v
            ml += 5
            out += lit[lp:lp + ll]; lp += ll
            if off > len(out) - start: raise ValueError('offset')
            for _ in range(ml): out.append(out[-off])
        out += lit[lp:nlit]
    else:
        raise ValueError('block type %d' % typ)

def decode(b):
    out = bytearray(); p = 0
    while p < len(b):
        assert b[p:p + 4] == bytes.fromhex('f52eb09c'), 'magic'
        flags = b[p + 6]; ck = 4 if flags & 0x80 else 0
        p += 16
        while True:
            typ = b[p]; size = int.from_bytes(b[p + 3:p + 7], 'little')
            if typ == 255: p += 8; break
            block(b[p:p + 8 + size], out); p += 8 + size + ck
        if flags & 0x20: raise ValueError('seek table')
        # footer: we only decode one frame per segment
        break
    return bytes(out)

if __name__ == '__main__':
    open(sys.argv[2], 'wb').write(decode(open(sys.argv[1], 'rb').read()))
