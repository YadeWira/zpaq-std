"""sylz_src.py: the decoder of sylz blocks (formats v2 to v5) as a ZPAQL post-processor.

This file is BOTH the Python model (run by zref.py) and the source gen.py compiles to ZPAQL, in the
subset of Python described at the top of gen.py: every lower-case name is one global 32-bit register,
M is the byte array, H the word array, functions are macros expanded in line. V5 (0 or 1, given by
gen.py / zref.py) selects the variant: ZPAQSYLZ4 (V5 = 0) reads v2 and v4 blocks, ZPAQSYLZ5 all four.
DEBUG (0 or 1, likewise) keeps the dbg() dumps: the size and the header, the table as loaded, every
update entry, every chunk, every sequence, every Huffman table and stream, the number of a fail().
NOTES.md has the design.

The segment:  [original size: u32 LE][one sylz block]   in M[0..n) when decode() runs.
"""

# ---- M: the segment at 0; the rest is addressed from the top (an index of M is taken modulo its size,
#      2^PM with PM <= 31, so these are its last bytes whatever PM is)
WIN = 0x7FFF0000           # the last 65536 bytes of the output (a ring)
WEND = 0x80000000          # its end
LBUF = 0x7FFE0000          # V5: the literals of the Huffman chunk being used (65536 at most)

# ---- H: 0..255 the token table (see tables.py for its words); and with V5:
CNT = 256                  # codes per length, then the next code of each length (16)
TAB = 2048                 # Huffman decoding table: the next 11 bits -> length << 8 | symbol (2048)


def le32(q):
    """v = the 32-bit little-endian value at M[q]."""
    v = M[q] | (M[q + 1] << 8) | (M[q + 2] << 16) | (M[q + 3] << 24)


def ext():
    """xv += a 255-run of the chunk's bytes at c. Bounded by the chunk's bytes; the sum by what is left
    of the output (o + xv <= orig < 2^31 before every addition, so it cannot wrap)."""
    while True:
        if c == cend:
            fail(30)
        t = M[c]
        c += 1
        xv += t
        if t != 255:
            break
        if o + xv > orig:
            fail(31)


def update():
    """A table update at c: (count - 1), then count times (code, entry: u16). Bounded by its count."""
    if c == tend:
        fail(20)
    cnt = M[c] + 1
    c += 1
    if cnt * 3 > tend - c:
        fail(21)
    while cnt != 0:
        code = M[c]
        c += 1
        ld16(v, c)
        c += 2
        ll = v & 31
        ml = (v >> 5) & 63
        if (v >> 12) != 0:
            fail(22)
        if ll > 16:
            if ll != 31:
                fail(23)
        if ml > 32:
            if ml != 63:
                fail(24)
        H[code] = ((v >> 11) << 11) + (ll << 6) + ml
        if DEBUG:
            dbg(code)
            dbg(H[code])
        cnt -= 1


def put(src, k):
    """k bytes (k >= 1) from M[src] to the window and the output; neither side crosses the window's end.
    The last byte of the output is kept in `last` and not written yet."""
    o += k
    if o == orig:
        k1 = k - 1
        if k1 != 0:
            copyout(wq, src, k1)
        t = src + k1
        last = M[t]
    else:
        copyout(wq, src, k)
    wq += k
    if wq == WEND:
        wq = WIN


def huff():
    """A Huffman chunk at p (after its mode byte), cc symbols (256..65536), into M[LBUF..]; p goes past
    it. hmode 2 (v3): four streams, one run of symbols each; hmode 3 (v5): eight, symbol j in stream j % 8."""
    # codes per length; the lengths must make a complete code (so at least two symbols)
    i = 0
    while i != 16:
        H[CNT + i] = 0
        i += 1
    kr = 0
    s = 0
    while s != 256:
        ln = (M[p + (s >> 1)] >> ((s & 1) << 2)) & 15
        if ln != 0:
            if ln > 11:
                fail(40)
            H[CNT + ln] += 1
            kr += 1 << (11 - ln)
        s += 1
    if kr != 2048:
        fail(41)
    # the first code of each length
    code = 0
    i = 1
    while i != 12:
        t = H[CNT + i]
        H[CNT + i] = code
        code = (code + t) << 1
        i += 1
    # the table: each symbol's code, bits reversed, at every 1 << length
    tab = TAB
    s = 0
    while s != 256:
        ln = (M[p + (s >> 1)] >> ((s & 1) << 2)) & 15
        if ln != 0:
            cd = H[CNT + ln]
            H[CNT + ln] = cd + 1
            r = 0
            j = ln
            while j != 0:
                r = (r << 1) | (cd & 1)
                cd = cd >> 1
                j -= 1
            ee = (ln << 8) | s
            st = 1 << ln
            while r < 2048:
                H[tab + r] = ee
                r += st
        s += 1
    p += 128
    if DEBUG:
        i = 0
        while i != 2048:
            dbg(H[tab + i])
            i += 1
    # the streams
    ns = 4
    stride = 1
    if hmode == 3:
        ns = 8
        stride = 8
    zp = p                           # their sizes
    sp = p + (ns << 1)               # the first one
    qq = (cc + 3) >> 2
    lq = LBUF
    hk = 0
    while hk != ns:
        ld16(sz, zp)
        zp += 2
        se = sp + sz
        if se > n:
            fail(42)
        if hmode == 3:
            hcnt = (cc + 7 - hk) >> 3
            lq = LBUF + hk
        else:
            hcnt = qq
            if hk == 3:
                hcnt = cc - qq * 3
        b0 = sp
        buf = 0
        nb = 0
        while hcnt != 0:
            if nb < 11:
                while True:          # past the stream's end it reads what follows: checked below
                    buf = buf | (M[sp] << nb)
                    sp += 1
                    nb += 8
                    if nb > 24:
                        break
            ee = H[tab + (((buf << 21) & MASK32) >> 21)]
            M[lq] = ee
            lq += stride
            ln = ee >> 8
            buf = buf >> ln
            nb -= ln
            hcnt -= 1
        if DEBUG:
            dbg(sz)
            dbg(((sp - b0) << 3) - nb)
        if ((sp - b0) << 3) - nb > (sz << 3):     # the codes end past the stream's bytes
            fail(43)
        sp = se
        hk += 1
    p = sp


def refill():
    """The next literal chunk (at p; lleft literals are still in chunks): lp..lend = its literals."""
    cc = lleft
    if cc > 65536:
        cc = 65536
    if p == n:
        fail(50)
    md = M[p]
    p += 1
    if md == 0:                      # raw: used where it is
        if cc > n - p:
            fail(51)
        lp = p
        p += cc
    else:
        if md != hmode:
            fail(52)
        if cc < 256:
            fail(53)
        if n - p < 144:
            if n - p < 136:
                fail(54)
            if hmode == 3:
                fail(54)
        huff()
        lp = LBUF
    lend = lp + cc
    lleft -= cc
    if DEBUG:
        dbg(md)
        dbg(cc)
        dbg(p)
    if lleft == 0:                   # the chunks end where the block does
        if p != n:
            fail(55)


def decode():
    try:
        if n < 8:
            fail(1)
        q = 0
        le32(q)
        orig = v
        q = 4
        le32(q)
        hdr = v
        if (orig >> 31) != 0:
            fail(2)
        o = 0
        wq = WIN
        dist = 1
        fin = 0
        lleft = 0
        op = 0
        oend = 0
        one = 1
        uflag = 0
        c = 8
        cend = 8
        if ((hdr >> 30) & 1) == 0:
            # v2, v3: one chunk, the offsets after the tokens
            loadtable(2)
            tend = ((hdr << 2) & MASK32) >> 2
            if tend > n - 8:
                fail(3)
            tend += 8
            q = tend
        else:
            # v4, v5
            loadtable(4)
            offc = 0
            one = (hdr >> 29) & 1
            if one != 0:
                tend = ((hdr << 18) & MASK32) >> 18
                offc = ((hdr << 4) & MASK32) >> 18
                uflag = (hdr >> 28) & 1
                if uflag != 0:
                    if tend == 0:
                        fail(4)
            else:
                tend = ((hdr << 3) & MASK32) >> 3
            if tend > n - 8:
                fail(3)
            tend += 8
            q = tend
            if one == 0:
                if tend != 8:
                    lsh = 0
                    while True:      # the offsets' count: 5 bytes at most
                        if q == n:
                            fail(5)
                        t = M[q]
                        q += 1
                        if lsh == 28:
                            if t > 15:
                                fail(6)
                        offc = offc | ((t & 127) << lsh)
                        lsh += 7
                        if t < 128:
                            break
            if offc > ((n - q) >> 1):
                fail(7)
            op = q
            oend = q + (offc << 1)
            q = oend
        if DEBUG:
            dbg(orig)
            dbg(hdr)
            dbg(tend)
            dbg(oend - op)
            i = 0
            while i != 256:
                dbg(H[i])
                i += 1
        # the literals, at q
        lp = q
        lend = n
        if (hdr >> 31) != 0:
            if V5:
                if n - q < 4:
                    fail(8)
                le32(q)
                lleft = v
                if lleft == 0:
                    fail(9)
                if lleft > orig:
                    fail(9)
                p = q + 4
                lp = 0
                lend = 0
                hmode = 2 + ((hdr >> 30) & 1)
            else:
                fail(10)
        while True:
            if c == cend:
                if c != tend:
                    # a chunk: its header, its update
                    if one != 0:
                        cu = uflag
                    else:
                        if tend - c < 2:
                            fail(11)
                        ld16(cn, c)
                        c += 2
                        if (cn & 2) != 0:
                            if tend - c < 2:
                                fail(11)
                            ld16(t, c)
                            c += 2
                            cn = cn | (t << 16)
                        cu = cn & 1
                        cn = cn >> 2
                    if cu != 0:
                        update()
                    if one != 0:             # the block's only chunk: what is left after its update
                        cn = tend - c
                    if cn > tend - c:
                        fail(12)
                    cend = c + cn
                    if DEBUG:
                        dbg(cu)
                        dbg(cn)
                    continue
                # the end of the tokens: the tail
                if op != oend:
                    fail(13)
                ll = orig - o
                if lend - lp + lleft != ll:
                    fail(14)
                fin = 1
            else:
                e = H[M[c]]
                c += 1
                x = e >> 11
                if x != 1:
                    if x == 0:
                        if op == oend:
                            fail(15)
                        ld16(dist, op)
                        op += 2
                    else:
                        if tend - c < 2:
                            fail(16)
                        ld16(dist, c)
                        c += 2
                    dist += 1
                ml = e & 63
                ll = (e >> 6) & 31
                if ll == 31:
                    xv = 0
                    ext()
                    ll = xv
                if ml == 63:
                    xv = 4
                    if x == 1:
                        xv = 2
                    ext()
                    ml = xv
                if DEBUG:
                    dbg(ll)
                    dbg(ml)
                    dbg(dist)
                if o + ll > orig:
                    fail(17)
            while ll != 0:
                k = lend - lp
                if k == 0:
                    if V5:
                        if lleft == 0:
                            fail(18)
                        refill()
                        k = lend - lp
                    else:
                        fail(18)
                if k > ll:
                    k = ll
                t = WEND - wq
                if k > t:
                    k = t
                put(lp, k)
                lp += k
                ll -= k
            if fin != 0:
                break
            if dist > o:
                fail(19)
            if o + ml > orig:
                fail(25)
            if ml != 0:
                ms = wq - dist
                if ms < WIN:
                    ms += 65536
                while True:
                    k = WEND - wq
                    if k > ml:
                        k = ml
                    t = WEND - ms
                    if k > t:
                        k = t
                    put(ms, k)
                    ml -= k
                    if ml == 0:
                        break
                    ms += k
                    if ms == WEND:
                        ms = WIN
        if orig != 0:
            out(last)
    except Fail:
        dbg(ferr)
