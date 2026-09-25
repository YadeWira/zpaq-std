#!/usr/bin/env python3
# Decodificador de referencia de libbsc 3.3.12 tal como lo usa zpaq-std -ma:bsc:
# sin LZP, ST3/ST4/ST5 y QLFC estatico. Especificacion ejecutable para el ZPAQL.
import sys, struct, os, re

BSC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bsc')

def tablas():
    """Las dos tablas de estados del QLFC, leidas de libbsc (coder/common/tables.h)."""
    src = open(os.path.join(BSC, 'coder', 'common', 'tables.h')).read()
    res = b''
    for name, size in (('model_rank_state_table', 32768), ('model_run_state_table', 8192)):
        body = src[src.index(name):]
        body = body[body.index('{') + 1:body.index('}')]
        v = [int(x) for x in re.findall(r'-?\d+', body)]
        assert len(v) == size, (name, len(v))
        res += bytes(v)
    return res

TAB = tablas()
RANK_ST = TAB[:32768]
RUN_ST = TAB[32768:]

# constantes F_* de qlfc_model.h (modelo estatico)
F = {}
for line in open(os.path.join(BSC, 'coder', 'qlfc', 'qlfc_model.h')):
    for part in line.split(';'):
        part = part.strip()
        if part.startswith('const int F_'):
            k, v = part[len('const int '):].split('=')
            F[k.strip()[2:]] = int(v)

def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v

def upd0(p, th, ar): return s16(p + (((4096 - th - p) * ar) >> 12))
def upd1(p, th, ar): return s16(p - (((p - th) * ar) >> 12))
def upd(b, p, th0, ar0, th1, ar1):
    d0 = p * ar0 - ((4096 - th0) * ar0 - 4095)
    d1 = p * ar1 - (th1 * ar1)
    return s16(p - ((d1 if b else d0) >> 12))

class RC:
    def __init__(s, b, p):
        s.b = b; s.p = p
        s.code = 0; s.range = 0xFFFFFFFF
        for _ in range(3): s.code = ((s.code << 16) | s.short()) & 0xFFFFFFFF
    def short(s):
        v = s.b[s.p] | (s.b[s.p + 1] << 8) if s.p + 1 < len(s.b) else 0
        s.p += 2; return v
    def bit(s, prob=2048):
        assert 0 < prob < 4096, prob
        if s.range < 0x10000:
            s.range = (s.range << 16) & 0xFFFFFFFF; s.code = ((s.code << 16) | s.short()) & 0xFFFFFFFF
        r = (s.range >> 12) * prob
        if s.code >= r:
            s.range -= r; s.code -= r; return 1
        s.range = r; return 0

def bsr(x): return x.bit_length() - 1

def qlfc_static(b, p):
    """Un bloque QLFC estatico desde b[p]; devuelve los n bytes (salida del ST)."""
    # modelo: todo en 2048
    rk_static = [2048]; rk_state = [2048] * 256; rk_char = [2048] * 256
    re_static = [2048] * 8; re_state = [[2048] * 8 for _ in range(256)]; re_char = [[2048] * 8 for _ in range(256)]
    rm = [([2048] * 256, [[2048] * 256 for _ in range(256)], [[2048] * 256 for _ in range(256)]) for _ in range(8)]
    rs = ([2048] * 256, [[2048] * 256 for _ in range(256)], [[2048] * 256 for _ in range(256)])
    un_static = [2048]; un_state = [2048] * 256; un_char = [2048] * 256
    ue_static = [2048] * 32; ue_state = [[2048] * 32 for _ in range(256)]; ue_char = [[2048] * 32 for _ in range(256)]
    um = [([2048] * 32, [[2048] * 32 for _ in range(256)], [[2048] * 32 for _ in range(256)]) for _ in range(32)]
    rc = RC(b, p)
    ctxR0 = ctxR4 = ctxRun = 0; maxRank = 7; avgRank = 0
    rankH = [0] * 256; runH = [0] * 256
    n = 0
    for _ in range(32): n = (n << 1) | rc.bit()
    used = [0] * 256; prev = -1; mtf = [0] * 256
    for rank in range(256):
        cur = 0
        for bit in range(7, -1, -1):
            b0 = b1 = False
            for c in range(256):
                if c == prev or used[c] == 0:
                    if cur == (c >> (bit + 1)):
                        if c & (1 << bit): b1 = True
                        else: b0 = True
                        if b0 and b1: break
            if b0 and b1: cur = cur * 2 + rc.bit()
            elif b0: cur = cur * 2
            elif b1: cur = cur * 2 + 1
        mtf[rank] = cur
        if cur == prev:
            maxRank = bsr(rank - 1) if rank > 1 else 63
            break
        prev = cur; used[cur] = 1
    out = bytearray()
    while len(out) < n:
        ch = mtf[0]
        state = RANK_ST[(ctxRun << 11) | (ctxR4 << 3) | rankH[ch]]
        rank = 1
        if avgRank < 32:
            pr = (rk_char[ch] * F['RANK_TM_LR0'] + rk_state[state] * F['RANK_TM_LR1'] + rk_static[0] * F['RANK_TM_LR2']) >> 5
            if rc.bit(pr):
                rk_state[state] = upd1(rk_state[state], F['RANK_TS_TH1'], F['RANK_TS_AR1'])
                rk_char[ch] = upd1(rk_char[ch], F['RANK_TC_TH1'], F['RANK_TC_AR1'])
                rk_static[0] = upd1(rk_static[0], F['RANK_TP_TH1'], F['RANK_TP_AR1'])
                sp, cp, tp = re_state[state], re_char[ch], re_static
                k = 0; bitRankSize = 1
                while bitRankSize != maxRank:
                    pr = (cp[k] * F['RANK_EM_LR0'] + sp[k] * F['RANK_EM_LR1'] + tp[k] * F['RANK_EM_LR2']) >> 5
                    if rc.bit(pr):
                        sp[k] = upd1(sp[k], F['RANK_ES_TH1'], F['RANK_ES_AR1'])
                        cp[k] = upd1(cp[k], F['RANK_EC_TH1'], F['RANK_EC_AR1'])
                        tp[k] = upd1(tp[k], F['RANK_EP_TH1'], F['RANK_EP_AR1'])
                        k += 1; bitRankSize += 1
                    else:
                        sp[k] = upd0(sp[k], F['RANK_ES_TH0'], F['RANK_ES_AR0'])
                        cp[k] = upd0(cp[k], F['RANK_EC_TH0'], F['RANK_EC_AR0'])
                        tp[k] = upd0(tp[k], F['RANK_EP_TH0'], F['RANK_EP_AR0'])
                        break
                rankH[ch] = bitRankSize
                tp, sp, cp = rm[bitRankSize][0], rm[bitRankSize][1][state], rm[bitRankSize][2][ch]
                for _ in range(bitRankSize):
                    pr = (cp[rank] * F['RANK_MM_LR0'] + sp[rank] * F['RANK_MM_LR1'] + tp[rank] * F['RANK_MM_LR2']) >> 5
                    bb = rc.bit(pr)
                    sp[rank] = upd(bb, sp[rank], F['RANK_MS_TH0'], F['RANK_MS_AR0'], F['RANK_MS_TH1'], F['RANK_MS_AR1'])
                    cp[rank] = upd(bb, cp[rank], F['RANK_MC_TH0'], F['RANK_MC_AR0'], F['RANK_MC_TH1'], F['RANK_MC_AR1'])
                    tp[rank] = upd(bb, tp[rank], F['RANK_MP_TH0'], F['RANK_MP_AR0'], F['RANK_MP_TH1'], F['RANK_MP_AR1'])
                    rank = rank * 2 + bb
            else:
                rankH[ch] = 0
                rk_state[state] = upd0(rk_state[state], F['RANK_TS_TH0'], F['RANK_TS_AR0'])
                rk_char[ch] = upd0(rk_char[ch], F['RANK_TC_TH0'], F['RANK_TC_AR0'])
                rk_static[0] = upd0(rk_static[0], F['RANK_TP_TH0'], F['RANK_TP_AR0'])
        else:
            tp, sp, cp = rs[0], rs[1][state], rs[2][ch]
            rank = 0; ctx = 1
            for _ in range(maxRank + 1):
                pr = (cp[ctx] * F['RANK_PM_LR0'] + sp[ctx] * F['RANK_PM_LR1'] + tp[ctx] * F['RANK_PM_LR2']) >> 5
                bb = rc.bit(pr)
                sp[ctx] = upd(bb, sp[ctx], F['RANK_PS_TH0'], F['RANK_PS_AR0'], F['RANK_PS_TH1'], F['RANK_PS_AR1'])
                cp[ctx] = upd(bb, cp[ctx], F['RANK_PC_TH0'], F['RANK_PC_AR0'], F['RANK_PC_TH1'], F['RANK_PC_AR1'])
                tp[ctx] = upd(bb, tp[ctx], F['RANK_PP_TH0'], F['RANK_PP_AR0'], F['RANK_PP_TH1'], F['RANK_PP_AR1'])
                ctx = ctx * 2 + bb; rank = rank * 2 + bb
            rankH[ch] = bsr(rank)
        for r in range(rank): mtf[r] = mtf[r + 1]
        mtf[rank] = ch
        avgRank = (avgRank * 124 + rank * 4) >> 7
        rank -= 1
        state = RUN_ST[(ctxR0 << 10) | (ctxRun << 6) | ((rank if rank < 7 else 7) << 3) | (runH[ch] if runH[ch] < 7 else 7)]
        pr = (un_char[ch] * F['RUN_TM_LR0'] + un_state[state] * F['RUN_TM_LR1'] + un_static[0] * F['RUN_TM_LR2']) >> 5
        if rc.bit(pr):
            un_state[state] = upd1(un_state[state], F['RUN_TS_TH1'], F['RUN_TS_AR1'])
            un_char[ch] = upd1(un_char[ch], F['RUN_TC_TH1'], F['RUN_TC_AR1'])
            un_static[0] = upd1(un_static[0], F['RUN_TP_TH1'], F['RUN_TP_AR1'])
            sp, cp, tp = ue_state[state], ue_char[ch], ue_static
            k = 0; runSize = 1; bitRunSize = 1
            while True:
                pr = (cp[k] * F['RUN_EM_LR0'] + sp[k] * F['RUN_EM_LR1'] + tp[k] * F['RUN_EM_LR2']) >> 5
                if rc.bit(pr):
                    sp[k] = upd1(sp[k], F['RUN_ES_TH1'], F['RUN_ES_AR1'])
                    cp[k] = upd1(cp[k], F['RUN_EC_TH1'], F['RUN_EC_AR1'])
                    tp[k] = upd1(tp[k], F['RUN_EP_TH1'], F['RUN_EP_AR1'])
                    k += 1; bitRunSize += 1
                else:
                    sp[k] = upd0(sp[k], F['RUN_ES_TH0'], F['RUN_ES_AR0'])
                    cp[k] = upd0(cp[k], F['RUN_EC_TH0'], F['RUN_EC_AR0'])
                    tp[k] = upd0(tp[k], F['RUN_EP_TH0'], F['RUN_EP_AR0'])
                    break
            runH[ch] = (runH[ch] + 3 * bitRunSize + 3) >> 2
            tp, sp, cp = um[bitRunSize][0], um[bitRunSize][1][state], um[bitRunSize][2][ch]
            ctx = 1
            for _ in range(bitRunSize):
                pr = (cp[ctx] * F['RUN_MM_LR0'] + sp[ctx] * F['RUN_MM_LR1'] + tp[ctx] * F['RUN_MM_LR2']) >> 5
                bb = rc.bit(pr)
                sp[ctx] = upd(bb, sp[ctx], F['RUN_MS_TH0'], F['RUN_MS_AR0'], F['RUN_MS_TH1'], F['RUN_MS_AR1'])
                cp[ctx] = upd(bb, cp[ctx], F['RUN_MC_TH0'], F['RUN_MC_AR0'], F['RUN_MC_TH1'], F['RUN_MC_AR1'])
                tp[ctx] = upd(bb, tp[ctx], F['RUN_MP_TH0'], F['RUN_MP_AR0'], F['RUN_MP_TH1'], F['RUN_MP_AR1'])
                runSize = runSize * 2 + bb
                c2 = ctx * 2 + bb; ctx += 1
                if bitRunSize <= 5: ctx = c2
            ctxR0 = ((ctxR0 << 1) | (1 if rank == 0 else 0)) & 7
            ctxR4 = ((ctxR4 << 2) | (rank if rank < 3 else 3)) & 0xFF
            ctxRun = ((ctxRun << 1) | (1 if runSize < 3 else 0)) & 0xF
            out += bytes([ch]) * runSize
        else:
            runH[ch] = (runH[ch] + 2) >> 2
            un_state[state] = upd0(un_state[state], F['RUN_TS_TH0'], F['RUN_TS_AR0'])
            un_char[ch] = upd0(un_char[ch], F['RUN_TC_TH0'], F['RUN_TC_AR0'])
            un_static[0] = upd0(un_static[0], F['RUN_TP_TH0'], F['RUN_TP_AR0'])
            ctxR0 = ((ctxR0 << 1) | (1 if rank == 0 else 0)) & 7
            ctxR4 = ((ctxR4 << 2) | (rank if rank < 3 else 3)) & 0xFF
            ctxRun = ((ctxRun << 1) | 1) & 0xF
            out.append(ch)
    assert len(out) == n, (len(out), n)
    return bytes(out)

def unst(T, k, start):
    """ST inversa (caso 1 de libbsc generalizado: sin limite de 2^23)."""
    n = len(T)
    if n <= 1: return bytes(T)
    count = [0] * 256
    for c in T: count[c] += 1
    s = 0
    for c in range(256): t = count[c]; count[c] = s; s += t
    bucket = [0] * 65536
    ends = count[1:] + [n]
    for c in range(256):
        for i in range(count[c], ends[c]): bucket[(c << 8) | T[i]] += 1
    # transponer: bucket[d<<8|c] <-> bucket[c<<8|d]
    for c in range(256):
        for d in range(c):
            a, b = (d << 8) | c, (c << 8) | d
            bucket[a], bucket[b] = bucket[b], bucket[a]
    P = [0] * n
    if k == 3:
        s = 0
        for w in range(65536):
            if bucket[w] > 0: P[s] = 1; s += bucket[w]
    else:
        index = list(count); group = [-1] * 256; s = 0
        for w in range(65536):
            t = s; s += bucket[w]
            for i in range(t, s):
                c = T[i]
                if group[c] != w: group[c] = w; P[index[c]] = 0x80000000
                index[c] += 1
        m0, m1 = 0x80000000, 0x40000000
        for rnd in range(4, k):
            index = list(count); group = [-1] * 256; g = 0
            for i in range(n):
                if P[i] & m0: g = i
                c = T[i]
                if group[c] != g: group[c] = g; P[index[c]] += m1
                index[c] += 1
            m0 >>= 1; m1 >>= 1
    # reconstruccion
    index = list(count); group = [-1] * 256; g = 0
    V = [0] * n; FL = 0x80000000
    for i in range(n):
        if P[i] > 0: g = i
        c = T[i]
        if group[c] < g:
            group[c] = i; V[i] = index[c]
        else:
            V[i] = FL | group[c]; V[group[c]] += 1
        index[c] += 1
    out = bytearray(n); p = start
    for i in range(n - 1, -1, -1):
        u = V[p]
        if u & FL: p = u & ~FL; u = V[p]
        out[i] = T[p]; V[p] -= 1; p = u
    return bytes(out)

def decompress(d):
    blockSize, n, mode, index = struct.unpack_from('<iiii', d, 0)
    if mode == 0: return d[28:28 + n]
    sorter = mode & 0x1f; coder = (mode >> 5) & 7
    assert coder == 1 and 3 <= sorter <= 5 and (mode >> 8) == 0, hex(mode)
    c = 28
    nb = d[c]
    if nb == 1:
        T = qlfc_static(d, c + 1)
    else:
        T = bytearray(); p = c + 1 + 8 * nb
        for bi in range(nb):
            osz, isz = struct.unpack_from('<ii', d, c + 1 + 8 * bi)
            if isz != osz: T += qlfc_static(d, p)
            else: T += d[p:p + isz]
            p += isz
    assert len(T) == n, (len(T), n)
    return unst(bytearray(T), sorter, index)

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    open(sys.argv[2], 'wb').write(decompress(d))
