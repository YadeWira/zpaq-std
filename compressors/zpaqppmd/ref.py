#!/usr/bin/env python3
# Decodificador de referencia de PPMd var.H (Ppmd7 del 7-Zip SDK, con el codificador de
# rango de 7z) tal como lo usa zpaq-std -ma:ppmd. Traduccion fiel de Ppmd7.c/Ppmd7Dec.c
# sobre un monticulo de bytes: el modelo depende del asignador de memoria (compara
# desplazamientos y se reinicia al quedarse sin memoria), asi que se reproduce entero.
#   python3 ref.py flujo salida ORDEN MEM ORIG
import sys

UNIT = 12
MAX_FREQ = 124
NUM_INDEXES = 38
kExpEscape = [25, 14, 9, 7, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2]
kInitBinEsc = [0x3CDD, 0x1F3F, 0x59BF, 0x48F3, 0x64A1, 0x5ABC, 0x6632, 0x6051]

class P7:
    def __init__(s, size, order, data):
        s.H = bytearray(size)
        s.Size = size
        s.MaxOrder = order
        s.I2U = [0] * NUM_INDEXES; s.U2I = [0] * 128
        k = 0
        for i in range(NUM_INDEXES):
            step = 4 if i >= 12 else (i >> 2) + 1
            for _ in range(step): s.U2I[k] = i; k += 1
            s.I2U[i] = k
        s.NS2BSIndx = [0, 2] + [4] * 9 + [6] * (256 - 11)
        s.NS2Indx = [0] * 256
        for i in range(3): s.NS2Indx[i] = i
        m = 3; k = 1
        for i in range(3, 256):
            s.NS2Indx[i] = m
            k -= 1
            if k == 0: m += 1; k = m - 2
        s.HiBitsFlag = 0; s.InitEsc = 0
        s.data = data; s.dp = 0
        s.restart()

    # --- memoria
    def g8(s, a): return s.H[a]
    def s8(s, a, v): s.H[a] = v & 255
    def g16(s, a): return s.H[a] | (s.H[a + 1] << 8)
    def s16(s, a, v): s.H[a] = v & 255; s.H[a + 1] = (v >> 8) & 255
    def g32(s, a): return s.H[a] | (s.H[a + 1] << 8) | (s.H[a + 2] << 16) | (s.H[a + 3] << 24)
    def s32(s, a, v):
        v &= 0xFFFFFFFF
        s.H[a] = v & 255; s.H[a + 1] = (v >> 8) & 255; s.H[a + 2] = (v >> 16) & 255; s.H[a + 3] = v >> 24
    # contexto: NumStats @0, SummFreq @2 (OneState: Symbol @2, Freq @3, Successor @4), Stats @4, Suffix @8
    # estado: Symbol @0, Freq @1, Successor @2 (u32 LE)
    def succ(s, st): return s.g32(st + 2)
    def setsucc(s, st, v): s.s32(st + 2, v)
    def copystate(s, dst, src): s.H[dst:dst + 6] = s.H[src:src + 6]

    def insert(s, node, indx):
        s.s32(node, s.FreeList[indx]); s.FreeList[indx] = node
    def remove(s, indx):
        node = s.FreeList[indx]; s.FreeList[indx] = s.g32(node); return node
    def split(s, ptr, oldIndx, newIndx):
        nu = s.I2U[oldIndx] - s.I2U[newIndx]
        ptr = ptr + UNIT * s.I2U[newIndx]
        i = s.U2I[nu - 1]
        if s.I2U[i] != nu:
            i -= 1; k = s.I2U[i]
            s.insert(ptr + UNIT * k, nu - k - 1)
        s.insert(ptr, i)
    def glue(s):
        n = 0
        s.GlueCount = 255
        if s.LoUnit != s.HiUnit: s.s16(s.LoUnit, 1)
        for i in range(NUM_INDEXES):
            nu = s.I2U[i]
            nxt = s.FreeList[i]; s.FreeList[i] = 0
            while nxt != 0:
                un = nxt; tmp = nxt
                nxt = s.g32(un)
                s.s16(un, 0); s.s16(un + 2, nu); s.s32(un + 4, n)
                n = tmp
        head = n
        # glue: prev es una "direccion" de campo Next (o None = head)
        prev = None
        while n:
            node = n
            nu = s.g16(node + 2)
            n = s.g32(node + 4)
            if nu == 0:
                if prev is None: head = n
                else: s.s32(prev, n)
                continue
            prev = node + 4
            while True:
                node2 = node + nu * UNIT
                nu += s.g16(node2 + 2)
                if s.g16(node2) != 0 or nu >= 0x10000: break
                s.s16(node + 2, nu)
                s.s16(node2 + 2, 0)
        n = head
        while n != 0:
            node = n
            nu = s.g16(node + 2)
            n = s.g32(node + 4)
            if nu == 0: continue
            while nu > 128:
                s.insert(node, NUM_INDEXES - 1); nu -= 128; node += 128 * UNIT
            i = s.U2I[nu - 1]
            if s.I2U[i] != nu:
                i -= 1; k = s.I2U[i]
                s.insert(node + k * UNIT, nu - k - 1)
            s.insert(node, i)
    def alloc_rare(s, indx):
        if s.GlueCount == 0:
            s.glue()
            if s.FreeList[indx] != 0: return s.remove(indx)
        i = indx
        while True:
            i += 1
            if i == NUM_INDEXES:
                numBytes = UNIT * s.I2U[indx]
                us = s.UnitsStart
                s.GlueCount = (s.GlueCount - 1) & 0xFFFFFFFF
                if us - s.Text > numBytes:
                    s.UnitsStart = us - numBytes; return s.UnitsStart
                return 0
            if s.FreeList[i] != 0: break
        block = s.remove(i)
        s.split(block, i, indx)
        return block
    def alloc(s, indx):
        if s.FreeList[indx] != 0: return s.remove(indx)
        numBytes = UNIT * s.I2U[indx]
        lo = s.LoUnit
        if s.HiUnit - lo >= numBytes:
            s.LoUnit = lo + numBytes; return lo
        return s.alloc_rare(indx)

    def restart(s):
        s.FreeList = [0] * NUM_INDEXES
        s.Text = 0
        s.HiUnit = s.Text + s.Size
        s.LoUnit = s.UnitsStart = s.HiUnit - s.Size // 8 // UNIT * 7 * UNIT
        s.GlueCount = 0
        s.OrderFall = s.MaxOrder
        s.RunLength = s.InitRL = -(s.MaxOrder if s.MaxOrder < 12 else 12) - 1
        s.PrevSuccess = 0
        s.HiUnit -= UNIT; mc = s.HiUnit
        st = s.LoUnit
        s.LoUnit += UNIT * 128
        s.MaxContext = s.MinContext = mc
        s.FoundState = st
        s.s16(mc, 256); s.s16(mc + 2, 257); s.s32(mc + 4, st); s.s32(mc + 8, 0)
        for i in range(256):
            a = st + 6 * i
            s.s8(a, i); s.s8(a + 1, 1); s.setsucc(a, 0)
        s.BinSumm = [[0] * 64 for _ in range(128)]
        for i in range(128):
            for k in range(8):
                val = (1 << 14) - kInitBinEsc[k] // (i + 2)
                for m in range(0, 64, 8): s.BinSumm[i][k + m] = val
        # See[i][k] = [Summ, Shift, Count]
        s.See = [[[(5 * i + 10) << (7 - 4), 7 - 4, 4] for k in range(16)] for i in range(25)]
        s.Dummy = [0, 7, 64]

    def create_successors(s):
        c = s.MinContext
        upBranch = s.succ(s.FoundState)
        ps = []
        if s.OrderFall != 0: ps.append(s.FoundState)
        while s.g32(c + 8):
            c = s.g32(c + 8)
            if s.g16(c) != 1:
                sym = s.g8(s.FoundState)
                st = s.g32(c + 4)
                while s.g8(st) != sym: st += 6
            else:
                st = c + 2
            successor = s.succ(st)
            if successor != upBranch:
                c = successor
                if len(ps) == 0: return c
                break
            ps.append(st)
        newSym = s.g8(upBranch)
        upBranch += 1
        if s.g16(c) == 1:
            newFreq = s.g8(c + 3)
        else:
            st = s.g32(c + 4)
            while s.g8(st) != newSym: st += 6
            cf = s.g8(st + 1) - 1
            s0 = s.g16(c + 2) - s.g16(c) - cf
            if 2 * cf <= s0: newFreq = 1 + (1 if 5 * cf > s0 else 0)
            else: newFreq = 1 + ((2 * cf + s0 - 1) // (2 * s0) + 1)
            newFreq &= 255
        while True:
            if s.HiUnit != s.LoUnit:
                s.HiUnit -= UNIT; c1 = s.HiUnit
            elif s.FreeList[0] != 0:
                c1 = s.remove(0)
            else:
                c1 = s.alloc_rare(0)
                if not c1: return 0
            s.s16(c1, 1)
            s.s8(c1 + 2, newSym); s.s8(c1 + 3, newFreq); s.setsucc(c1 + 2, upBranch)
            s.s32(c1 + 8, c)
            s.setsucc(ps.pop(), c1)
            c = c1
            if not ps: break
        return c

    def swap_prev(s, st):     # SWAP_STATES(s): s[0] <-> s[-1]
        a = bytes(s.H[st:st + 6]); s.H[st:st + 6] = s.H[st - 6:st]; s.H[st - 6:st] = a

    def update_model(s):
        fs = s.FoundState
        fsym = s.g8(fs); ffreq = s.g8(fs + 1)
        if ffreq < MAX_FREQ // 4 and s.g32(s.MinContext + 8) != 0:
            c = s.g32(s.MinContext + 8)
            if s.g16(c) == 1:
                st = c + 2
                if s.g8(st + 1) < 32: s.s8(st + 1, s.g8(st + 1) + 1)
            else:
                st = s.g32(c + 4)
                if s.g8(st) != fsym:
                    while True:
                        st += 6
                        if s.g8(st) == fsym: break
                    if s.g8(st + 1) >= s.g8(st - 6 + 1):
                        s.swap_prev(st); st -= 6
                if s.g8(st + 1) < MAX_FREQ - 9:
                    s.s8(st + 1, s.g8(st + 1) + 2)
                    s.s16(c + 2, s.g16(c + 2) + 2)
        if s.OrderFall == 0:
            s.MinContext = s.MaxContext = s.create_successors()
            if not s.MinContext:
                s.restart(); return
            s.setsucc(s.FoundState, s.MinContext)
            return
        s.s8(s.Text, fsym); s.Text += 1
        text = s.Text
        if text >= s.UnitsStart:
            s.restart(); return
        maxSuccessor = text
        minSuccessor = s.succ(s.FoundState)
        if minSuccessor:
            if minSuccessor <= maxSuccessor:
                cs = s.create_successors()
                if not cs:
                    s.restart(); return
                minSuccessor = cs
            s.OrderFall -= 1
            if s.OrderFall == 0:
                maxSuccessor = minSuccessor
                if s.MaxContext != s.MinContext: s.Text -= 1
        else:
            s.setsucc(s.FoundState, maxSuccessor)
            minSuccessor = s.MinContext
        mc = s.MinContext
        c = s.MaxContext
        s.MaxContext = s.MinContext = minSuccessor
        if c == mc: return
        ns = s.g16(mc)
        s0 = s.g16(mc + 2) - ns - (s.g8(s.FoundState + 1) - 1)
        fsym = s.g8(s.FoundState); ffreq = s.g8(s.FoundState + 1)
        while True:
            ns1 = s.g16(c)
            if ns1 != 1:
                if (ns1 & 1) == 0:
                    oldNU = ns1 >> 1
                    i = s.U2I[oldNU - 1]
                    if i != s.U2I[oldNU]:
                        ptr = s.alloc(i + 1)
                        if not ptr:
                            s.restart(); return
                        oldPtr = s.g32(c + 4)
                        s.H[ptr:ptr + 12 * oldNU] = s.H[oldPtr:oldPtr + 12 * oldNU]
                        s.insert(oldPtr, i)
                        s.s32(c + 4, ptr)
                sm = s.g16(c + 2)
                sm += (1 if 2 * ns1 < ns else 0) + 2 * ((1 if 4 * ns1 <= ns else 0) & (1 if sm <= 8 * ns1 else 0))
            else:
                st = s.alloc(0)
                if not st:
                    s.restart(); return
                freq = s.g8(c + 3)
                s.s8(st, s.g8(c + 2))
                s.H[st + 2:st + 6] = s.H[c + 4:c + 8]
                s.s32(c + 4, st)
                if freq < MAX_FREQ // 4 - 1: freq <<= 1
                else: freq = MAX_FREQ - 4
                s.s8(st + 1, freq)
                sm = freq + s.InitEsc + (1 if ns > 3 else 0)
            st = s.g32(c + 4) + 6 * ns1
            cf = 2 * (sm + 6) * ffreq
            sf = s0 + sm
            s.s8(st, fsym)
            s.s16(c, ns1 + 1)
            s.setsucc(st, maxSuccessor)
            if cf < 6 * sf:
                cf = 1 + (1 if cf > sf else 0) + (1 if cf >= 4 * sf else 0)
                sm += 3
            else:
                cf = 4 + (1 if cf >= 9 * sf else 0) + (1 if cf >= 12 * sf else 0) + (1 if cf >= 15 * sf else 0)
                sm += cf
            s.s16(c + 2, sm)
            s.s8(st + 1, cf)
            c = s.g32(c + 8)
            if c == mc: break

    def rescale(s):
        mc = s.MinContext
        stats = s.g32(mc + 4)
        st = s.FoundState
        if st != stats:
            tmp = bytes(s.H[st:st + 6])
            while True:
                s.H[st:st + 6] = s.H[st - 6:st]; st -= 6
                if st == stats: break
            s.H[st:st + 6] = tmp
        sumFreq = s.g8(st + 1)
        escFreq = s.g16(mc + 2) - sumFreq
        adder = 1 if s.OrderFall != 0 else 0
        sumFreq = (sumFreq + 4 + adder) >> 1
        i = s.g16(mc) - 1
        s.s8(st + 1, sumFreq)
        while True:
            st += 6
            freq = s.g8(st + 1)
            escFreq -= freq
            freq = (freq + adder) >> 1
            sumFreq += freq
            s.s8(st + 1, freq)
            if freq > s.g8(st - 6 + 1):
                tmp = bytes(s.H[st:st + 6])
                s1 = st
                while True:
                    s.H[s1:s1 + 6] = s.H[s1 - 6:s1]; s1 -= 6
                    if not (s1 != stats and freq > s.g8(s1 - 6 + 1)): break
                s.H[s1:s1 + 6] = tmp
            i -= 1
            if i == 0: break
        if s.g8(st + 1) == 0:
            i = 0
            while True:
                i += 1; st -= 6
                if s.g8(st + 1) != 0: break
            escFreq += i
            numStats = s.g16(mc)
            numStatsNew = numStats - i
            s.s16(mc, numStatsNew)
            n0 = (numStats + 1) >> 1
            if numStatsNew == 1:
                freq = s.g8(stats + 1)
                while True:
                    escFreq >>= 1
                    freq = (freq + 1) >> 1
                    if not (escFreq > 1): break
                s.H[mc + 2:mc + 8] = s.H[stats:stats + 6]
                s.s8(mc + 3, freq)
                s.FoundState = mc + 2
                s.insert(stats, s.U2I[n0 - 1])
                return
            n1 = (numStatsNew + 1) >> 1
            if n0 != n1:
                i0 = s.U2I[n0 - 1]; i1 = s.U2I[n1 - 1]
                if i0 != i1:
                    if s.FreeList[i1] != 0:
                        ptr = s.remove(i1)
                        s.s32(mc + 4, ptr)
                        s.H[ptr:ptr + 12 * n1] = s.H[stats:stats + 12 * n1]
                        s.insert(stats, i0)
                    else:
                        s.split(stats, i0, i1)
        s.s16(mc + 2, (sumFreq + escFreq - (escFreq >> 1)) & 0xFFFF)
        s.FoundState = s.g32(mc + 4)

    def make_esc_freq(s, numMasked):
        mc = s.MinContext
        numStats = s.g16(mc)
        if numStats != 256:
            nonMasked = numStats - numMasked
            see = s.See[s.NS2Indx[nonMasked - 1]][
                (1 if nonMasked < ((s.g16(s.g32(mc + 8)) - numStats) & 0xFFFFFFFF) else 0)
                + 2 * (1 if s.g16(mc + 2) < 11 * numStats else 0)
                + 4 * (1 if numMasked > nonMasked else 0)
                + s.HiBitsFlag]
            summ = see[0] & 0xFFFF
            r = summ >> see[1]
            see[0] = (summ - r) & 0xFFFF
            return see, r + (1 if r == 0 else 0)
        return s.Dummy, 1

    def next_context(s):
        c = s.succ(s.FoundState)
        if s.OrderFall == 0 and c > s.Text:
            s.MaxContext = s.MinContext = c
        else:
            s.update_model()
    def update1(s):
        st = s.FoundState
        freq = s.g8(st + 1) + 4
        s.s16(s.MinContext + 2, s.g16(s.MinContext + 2) + 4)
        s.s8(st + 1, freq)
        if freq > s.g8(st - 6 + 1):
            s.swap_prev(st)
            st -= 6; s.FoundState = st
            if freq > MAX_FREQ: s.rescale()
        s.next_context()
    def update1_0(s):
        st = s.FoundState; mc = s.MinContext
        freq = s.g8(st + 1)
        summFreq = s.g16(mc + 2)
        s.PrevSuccess = 1 if 2 * freq > summFreq else 0
        s.RunLength += s.PrevSuccess
        s.s16(mc + 2, summFreq + 4)
        freq += 4
        s.s8(st + 1, freq)
        if freq > MAX_FREQ: s.rescale()
        s.next_context()
    def update2(s):
        st = s.FoundState
        freq = s.g8(st + 1) + 4
        s.RunLength = s.InitRL
        s.s16(s.MinContext + 2, s.g16(s.MinContext + 2) + 4)
        s.s8(st + 1, freq)
        if freq > MAX_FREQ: s.rescale()
        s.update_model()

    # --- codificador de rango de 7z
    def rb(s):
        v = s.data[s.dp] if s.dp < len(s.data) else 0
        s.dp += 1; return v
    def rc_init(s):
        s.Code = 0; s.Range = 0xFFFFFFFF
        if s.rb() != 0: raise Exception('rc init')
        for _ in range(4): s.Code = ((s.Code << 8) | s.rb()) & 0xFFFFFFFF
    def norm1(s):
        if s.Range < (1 << 24):
            s.Code = ((s.Code << 8) | s.rb()) & 0xFFFFFFFF; s.Range = (s.Range << 8) & 0xFFFFFFFF
    def norm(s):
        if s.Range < (1 << 24):
            s.Code = ((s.Code << 8) | s.rb()) & 0xFFFFFFFF; s.Range = (s.Range << 8) & 0xFFFFFFFF
            if s.Range < (1 << 24):
                s.Code = ((s.Code << 8) | s.rb()) & 0xFFFFFFFF; s.Range = (s.Range << 8) & 0xFFFFFFFF
    def rc_decode(s, start, size):
        s.Code = (s.Code - start * s.Range) & 0xFFFFFFFF
        s.Range = (s.Range * size) & 0xFFFFFFFF
    def threshold(s, total):
        s.Range //= total
        return s.Code // s.Range

    def decode_symbol(s):
        mask = [0xFF] * 256
        mc = s.MinContext
        if s.g16(mc) != 1:
            st = s.g32(mc + 4)
            summFreq = s.g16(mc + 2)
            count = s.threshold(summFreq)
            hiCnt = count
            count -= s.g8(st + 1)
            if count < 0:
                s.rc_decode(0, s.g8(st + 1)); s.norm()
                s.FoundState = st
                sym = s.g8(st)
                s.update1_0()
                return sym
            s.PrevSuccess = 0
            i = s.g16(mc) - 1
            while True:
                st += 6
                count -= s.g8(st + 1)
                if count < 0:
                    s.rc_decode((hiCnt - count) - s.g8(st + 1), s.g8(st + 1)); s.norm()
                    s.FoundState = st
                    sym = s.g8(st)
                    s.update1()
                    return sym
                i -= 1
                if i == 0: break
            if hiCnt >= summFreq: raise Exception('error')
            hiCnt -= count
            s.rc_decode(hiCnt, summFreq - hiCnt)
            s.HiBitsFlag = ((s.g8(s.FoundState) + 0xC0) >> 5) & 8
            s2 = s.g32(mc + 4)
            mask[s.g8(st)] = 0
            while True:
                mask[s.g8(s2)] = 0; mask[s.g8(s2 + 6)] = 0
                s2 += 12
                if not (s2 < st): break
        else:
            st = mc + 2
            freq1 = s.g8(st + 1)
            s.HiBitsFlag = ((s.g8(s.FoundState) + 0xC0) >> 5) & 8
            row = s.BinSumm[freq1 - 1]
            col = (s.PrevSuccess + ((s.RunLength >> 26) & 0x20)
                   + s.NS2BSIndx[s.g16(s.g32(mc + 8)) - 1]
                   + (((s.g8(st) + 0xC0) >> 4) & 16) + s.HiBitsFlag)
            pr = row[col]
            size0 = (s.Range >> 14) * pr
            pr = pr - ((pr + (1 << 5)) >> 7)
            if s.Code < size0:
                row[col] = (pr + (1 << 7)) & 0xFFFF
                s.Range = size0
                s.norm1()
                c = s.succ(st)
                sym = s.g8(st)
                s.FoundState = st
                s.PrevSuccess = 1
                s.RunLength += 1
                s.s8(st + 1, freq1 + (1 if freq1 < 128 else 0))
                if s.OrderFall == 0 and c > s.Text:
                    s.MaxContext = s.MinContext = c
                else:
                    s.update_model()
                return sym
            row[col] = pr & 0xFFFF
            s.InitEsc = kExpEscape[pr >> 10]
            s.Code = (s.Code - size0) & 0xFFFFFFFF
            s.Range = (s.Range - size0) & 0xFFFFFFFF
            mask[s.g8(st)] = 0
            s.PrevSuccess = 0
        while True:
            s.norm()
            mc = s.MinContext
            numMasked = s.g16(mc)
            while True:
                s.OrderFall += 1
                if not s.g32(mc + 8): raise Exception('end')
                mc = s.g32(mc + 8)
                if s.g16(mc) != numMasked: break
            st = s.g32(mc + 4)
            num = s.g16(mc)
            s.MinContext = mc
            hiCnt = 0
            for k in range(num):
                hiCnt += s.g8(st + 6 * k + 1) & mask[s.g8(st + 6 * k)]
            see, freqSum = s.make_esc_freq(numMasked)
            freqSum += hiCnt
            count = s.threshold(freqSum)
            if count < hiCnt:
                st = s.g32(mc + 4)
                hiCnt = count
                while True:
                    count -= s.g8(st + 1) & mask[s.g8(st)]
                    st += 6
                    if count < 0: break
                st -= 6
                s.rc_decode((hiCnt - count) - s.g8(st + 1), s.g8(st + 1)); s.norm()
                if see[1] < 7:
                    see[2] = (see[2] - 1) & 255
                    if see[2] == 0:
                        see[0] = (see[0] << 1) & 0xFFFF
                        see[2] = (3 << see[1]) & 255; see[1] += 1
                s.FoundState = st
                sym = s.g8(st)
                s.update2()
                return sym
            if count >= freqSum: raise Exception('error2')
            s.rc_decode(hiCnt, freqSum - hiCnt)
            see[0] = (see[0] + freqSum) & 0xFFFF
            st = s.g32(mc + 4)
            for k in range(num): mask[s.g8(st + 6 * k)] = 0

def decompress(data, order, mem, orig):
    p = P7(mem, order, data)
    p.rc_init()
    out = bytearray()
    for _ in range(orig): out.append(p.decode_symbol())
    return bytes(out)

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    o = decompress(d, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    open(sys.argv[2], 'wb').write(o)
