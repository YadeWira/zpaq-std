#!/usr/bin/env python3
# Model of ZPAQSYLZ3 (gen.py): decodes one sylzec block (sylz format v3, or a plain
# v2 block) the way the ZPAQL does: the whole segment in M, then the literals into
# a buffer, then v2's sequences. Every loop is bounded by a count known before it
# starts. Any damage: stop (the output is short; zpaq's SHA-1 reports it).
#   ref3.py seg out      (seg: original size u32le + the block)
#   ref3.py --check DIR  (DIR: sylz-vectors/sylzec or sylz)
import sys, os, re
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sylz', 'sylz.pas')).read()
t = src[src.index('SYLZ_TOKENS: array[0..255] of UInt32 = ('):]; t = t[:t.index(');')]
T = [int(x, 16) for x in re.findall(r'\$([0-9A-F]+)', t)]; assert len(T) == 256

class Bad(Exception): pass

def u16(M, p): return M[p] | M[p + 1] << 8
def u32(M, p): return M[p] | M[p + 1] << 8 | M[p + 2] << 16 | M[p + 3] << 24

def huff_chunk(M, p, end, c, LB, lp):
    """mode 2 chunk at p (after the mode byte): c symbols into M[lp..]; returns the next p"""
    if c < 256: raise Bad('small huffman chunk')
    if p + 128 + 8 > end: raise Bad('chunk past the block')
    ln = [0] * 256
    for k in range(128):
        b = M[p + k]; ln[2 * k] = b & 15; ln[2 * k + 1] = b >> 4
    cnt = [0] * 16; kraft = 0; nsym = 0
    for s in range(256):
        L = ln[s]
        if L > 11: raise Bad('length > 11')
        if L: cnt[L] += 1; kraft += 1 << (11 - L); nsym += 1
    if kraft != 2048 or nsym < 2: raise Bad('not a complete code')
    nxt = [0] * 13; code = 0
    for b in range(1, 12):
        nxt[b] = code; code = (code + cnt[b]) << 1
    tab = [0] * 2048
    for s in range(256):
        L = ln[s]
        if not L: continue
        cd = nxt[L]; nxt[L] += 1
        r = 0
        for i in range(L): r = (r << 1) | ((cd >> i) & 1)      # bits reversed
        i = r
        while i < 2048: tab[i] = s | L << 8; i += 1 << L
    p += 128
    sz = [u16(M, p), u16(M, p + 2), u16(M, p + 4), u16(M, p + 6)]; p += 8
    if p + sum(sz) > end: raise Bad('streams past the block')
    q = (c + 3) // 4
    for k in range(4):
        n = q if k < 3 else c - 3 * q
        sp = p; se = p + sz[k]; buf = 0; nb = 0; used = 0
        for _ in range(n):
            while nb < 11:
                buf |= (M[sp] if sp < se else 0) << nb; sp += 1; nb += 8
            e = tab[buf & 2047]; L = e >> 8
            M[lp] = e & 255; lp += 1
            buf >>= L; nb -= L; used += L
        if used > 8 * sz[k]: raise Bad('stream past its size')
        p = se
    return p, lp

def decode(seg):
    n = len(seg)
    if n < 8: raise Bad('short')
    orig = u32(seg, 0)
    M = bytearray(seg) + bytearray(32 + 2 * orig + 16)   # segment, padding, literals, output
    hdr = u32(M, 4); clen = hdr & 0x7FFFFFFF
    cp = 8; ce = 8 + clen
    if ce > n: raise Bad('control past the block')
    if hdr >> 31:
        p = ce
        if p + 4 > n: raise Bad('no litCount')
        lc = u32(M, p); p += 4
        if lc < 1 or lc > orig: raise Bad('litCount')
        LB = n + 32; lp = LB; left = lc
        while left > 0:
            c = left if left < 65536 else 65536
            if p >= n: raise Bad('chunk past the block')
            mode = M[p]; p += 1
            if mode == 0:
                if p + c > n: raise Bad('raw past the block')
                M[lp:lp + c] = M[p:p + c]; lp += c; p += c
            elif mode == 2:
                p, lp = huff_chunk(M, p, n, c, LB, lp)
            else: raise Bad('chunk mode')
            left -= c
        if p != n: raise Bad('chunks do not end at the block end')
        ls = LB; le = LB + lc; OB = le
    else:
        ls = ce; le = n; OB = n + 32
    out = 0
    while cp < ce:
        if cp + 3 > ce: raise Bad('sequence past control')
        e = T[M[cp]]; off = u16(M, cp + 1) + 1; cp += 3
        lit = e & 255; ml = (e >> 8) & 255
        if e >> 16 & 1:
            while True:
                if cp >= ce: raise Bad('ext past control')
                b = M[cp]; cp += 1; lit += b
                if b != 255: break
        if e >> 17 & 1:
            while True:
                if cp >= ce: raise Bad('ext past control')
                b = M[cp]; cp += 1; ml += b
                if b != 255: break
        if ls + lit > le or out + lit > orig: raise Bad('literals')
        M[OB + out:OB + out + lit] = M[ls:ls + lit]; ls += lit; out += lit
        if off > out or out + ml > orig: raise Bad('match')
        for k in range(ml): M[OB + out + k] = M[OB + out - off + k]
        out += ml
    if le - ls != orig - out: raise Bad('tail')
    M[OB + out:OB + orig] = M[ls:le]
    return bytes(M[OB:OB + orig])

if __name__ == '__main__':
    if sys.argv[1] == '--check':
        d = sys.argv[2]; ok = bad = 0
        for f in sorted(os.listdir(d)):
            if not f.endswith('.blk'): continue
            o = open(os.path.join(d, f.split('.')[0] + '.orig'), 'rb').read()
            b = open(os.path.join(d, f), 'rb').read()
            seg = len(o).to_bytes(4, 'little') + b
            try:
                r = decode(seg); good = r == o
            except Bad as x:
                good = False; print(f, 'Bad', x)
            ok += good; bad += not good
        print(f'{ok} ok, {bad} bad')
    else:
        open(sys.argv[2], 'wb').write(decode(open(sys.argv[1], 'rb').read()))
