"""lz6seq: decoder of lz6 "seq" blocks (format 2 subset) as a ZPAQL post-processor.

This file is BOTH the Python model (run by zref.py) and the source that gen.py compiles to ZPAQL
(lz6seq.cfg). It is written in the subset of Python described at the top of gen.py: every lower-case
name is one global 32-bit register, M is the byte array, H the word array, functions are macros
expanded in line. See NOTES.md for the container, the memory layout and the register map.

Input (container):  [n_chunks:4 LE]  then per chunk  [csize:4 LE][seq block of csize bytes]
"""

# ---- sizes of the two arrays (the `comp 0 0 PH PM 0` line)
PM = 26                    # M: 64 MiB
PH = 16                    # H: 65536 words

# ---- M layout
INMAX = 0x1100000          # the compressed chunk is at 0; csize may not exceed this (17 MiB)
LIT = 0x1100000            # decoded literals of the chunk (at most OMAX bytes)
OUT = 0x2200000            # output of a normal block (at most OMAX bytes)
OMAX = 0x1000000           # largest isize accepted: 16 MiB
SLOT = 0x3300000           # rANS: symbol of each slot (at most 65536 bytes)
SPREAD = 0x3310000         # tANS: symbol of each state while a table is built (4096 bytes)

# ---- H layout (words)
TBL = 0                    # 3 tANS tables (ll, ml, of) x 4096 states x 2 words:
                           #   word 0: nbBits | (address of the entry of the next state's base) << 8
                           #   word 1: the symbol's value word (see INFO)
HB = 24576                 # highbit[x] for x < 8192
INFO = 32768               # value word of each symbol, 256 per alphabet (ll, ml, of):
                           #   extra bits | base << 5;  of: | (1 + rep index) << 30;  ml symbol 0: 0
NORM = 33536               # normalised counts of the table being read (256)
NEXT = 33792               # next[] of the table being built (256)
HLEN = 34048               # Huffman: code length of each symbol (256)
HCNT = 34304               # Huffman: codes per length (17)
HFIRST = 34336             # Huffman: first code of each length (17)
HOFF = 34368               # Huffman: index in HSORT of the first symbol of each length (17)
HNEXT = 34400              # Huffman: next code to give out per length (17)
HSORT = 34432              # Huffman: symbols sorted by (length, symbol) (256)
HTAB = 34688               # Huffman: lookup by the next hk bits: length << 8 | symbol, 0 = longer code (4096)
RFREQ = 38784              # rANS: frequency of each symbol (256)
RCUM = 39040               # rANS: cumulative frequency (256)
AMAX = 39296               # largest symbol of ll, ml, of (3)
TLOG = 39300               # table log of ll, ml, of (3)


# =====================================================================================================
# small readers
# =====================================================================================================
def le32(q):
    """v = 32-bit little-endian value at M[q]."""
    v = M[q] | (M[q + 1] << 8) | (M[q + 2] << 16) | (M[q + 3] << 24)


def leb(lim):
    """v = LEB128 count at p (at most 5 bytes, value below 2^30); p moves past it."""
    v = 0
    lsh = 0
    while True:
        if lsh > 28 or p >= lim:
            fail(1)
        lt = M[p]
        p += 1
        v = v | (((lt & 127) << lsh) & MASK32)
        if lt < 128:
            break
        lsh += 7
    if (v >> 30) != 0:
        fail(2)


def hbits(nb):
    """hv = the next nb bits (nb <= 11) of a bit-packed header, LSB first. hp = next byte, hlim = limit."""
    while hn < nb:
        if hp >= hlim:
            fail(3)
        hacc = hacc | (M[hp] << hn)
        hp += 1
        hn += 8
    hv = hacc & ((1 << nb) - 1)
    hacc = hacc >> nb
    hn -= nb


def gamma():
    """g = Elias gamma code: gz zero bits (at most 8), a one, gz bits high bit first."""
    gz = 0
    while True:
        hbits(1)
        if hv != 0:
            break
        gz += 1
        if gz > 8:
            fail(4)
    g = 1
    while gz > 0:
        hbits(1)
        g = (g << 1) | hv
        gz -= 1


def bread():
    """bv = the next bn bits (bn <= 24) of the backward sequence bitstream. bacc holds bcnt <= 31 bits.
    Pulling below blo is not checked here: the caller tests bptr < blo once per sequence (the 8 pad
    bytes and the headers in front of the stream keep the reads inside the chunk)."""
    while bcnt < bn:
        bptr -= 1
        bacc = (bacc << 8) | M[bptr]
        bcnt += 8
    bcnt -= bn
    bv = bacc >> bcnt
    bacc = bacc & ((1 << bcnt) - 1)


# =====================================================================================================
# constant tables (once per ZPAQ block: H starts at zero)
# =====================================================================================================
def init_consts():
    H[HB + 1] = 0
    i = 2
    while i < 8192:
        H[HB + i] = H[HB + (i >> 1)] + 1
        i += 1
    # ll codes 0..35 at INFO, ml symbols 1..36 at INFO + 257 (ml symbol 0 stays 0): value = base + extra bits
    i = 0
    while i < 16:
        H[INFO + i] = i << 5
        H[INFO + 257 + i] = (i + 3) << 5
        i += 1
    x = 16                               # base of code i
    while i < 35:
        t = 1                            # extra bits: 1 for codes 16..19, 2: 20..23, 3: 24..26, 4: 27..30, 5: 31..34
        if i > 19:
            t = 2
        if i > 23:
            t = 3
        if i > 26:
            t = 4
        if i > 30:
            t = 5
        H[INFO + i] = (x << 5) | t
        H[INFO + 257 + i] = ((x + 3) << 5) | t
        x += 1 << t
        i += 1
    H[INFO + 35] = (x << 5) | 24         # the escape codes: 24 extra bits (x = 256 here)
    H[INFO + 292] = ((x + 3) << 5) | 24
    # of codes 0..30: offset = code + 1; 31..190: bucket t = 5..24, low 3 bits in the code, t - 3 extra bits
    i = 0
    while i < 31:
        H[INFO + 512 + i] = (i + 1) << 5
        i += 1
    while i < 191:
        t = 5 + ((i - 31) >> 3)
        H[INFO + 512 + i] = (((1 << t) + ((i - 31) & 7)) << 5) | (t - 3)
        i += 1
    H[INFO + 703] = 1 << 30              # rep0, rep1, rep2
    H[INFO + 704] = 2 << 30
    H[INFO + 705] = 3 << 30
    H[AMAX] = 35
    H[AMAX + 1] = 36
    H[AMAX + 2] = 193


# =====================================================================================================
# literals
# =====================================================================================================
def huffman():
    """Literal modes 5 and 7 at p (payload ends at pe): scount literals to M[ld..]."""
    # ---- bit-packed header: [k:4], then per symbol a run of absent symbols or a length delta
    hp = p
    hacc = 0
    hn = 0
    hlim = pe
    hbits(4)
    hk = hv
    if hk < 1 or hk > 12:
        fail(20)
    i = 0
    while i < 17:
        H[HCNT + i] = 0
        i += 1
    prev = 8
    s = 0
    while s < 256:
        hbits(1)
        if hv == 0:
            gamma()
            if s + g > 256:
                fail(21)
            while g > 0:
                H[HLEN + s] = 0
                s += 1
                g -= 1
        else:
            q = 0
            while True:
                hbits(1)
                if hv == 0:
                    break
                q += 1
                if q > 40:
                    fail(22)
            hbits(1)
            z = (q << 1) | hv
            if z & 1:
                t = (z + 1) >> 1
                if t >= prev:
                    fail(23)
                prev -= t
            else:
                prev += z >> 1
                if prev > 16:
                    fail(24)
            H[HLEN + s] = prev
            H[HCNT + prev] = H[HCNT + prev] + 1
            s += 1
    p = hp
    # ---- canonical code, numbered from the longest length down; complete, or the one-symbol code
    kraft = 0
    nsym = 0
    i = 1
    while i < 17:
        kraft += H[HCNT + i] << (16 - i)
        nsym += H[HCNT + i]
        i += 1
    if kraft != 65536:
        if nsym != 1 or H[HCNT + 1] != 1:
            fail(25)
    H[HFIRST + 16] = 0
    i = 15
    while i > 0:
        H[HFIRST + i] = (H[HFIRST + 1 + i] + H[HCNT + 1 + i]) >> 1
        i -= 1
    t = 0
    i = 1
    while i < 17:
        H[HOFF + i] = t
        H[HNEXT + i] = H[HFIRST + i]
        t += H[HCNT + i]
        i += 1
    # ---- lookup table on the next hk bits
    hsz = 1 << hk
    i = 0
    while i < hsz:
        H[HTAB + i] = 0
        i += 1
    s = 0
    while s < 256:
        l = H[HLEN + s]
        if l != 0:
            c = H[HNEXT + l]
            H[HNEXT + l] = c + 1
            H[HSORT + H[HOFF + l] + (c - H[HFIRST + l])] = s
            if l <= hk:
                i = c << (hk - l)
                t = i + (1 << (hk - l))
                x = (l << 8) | s
                while i < t:
                    H[HTAB + i] = x
                    i += 1
        s += 1
    # ---- the streams: one (mode 5) or four (mode 7), each [total_bits:4][MSB-first bits]
    if smode == 5:
        seg = scount
        ns = 1
    else:
        seg = (scount + 3) >> 2
        ns = 4
    o = ld
    left = scount
    while ns > 0:
        m = left
        if m > seg:
            m = seg
        if pe - p < 4:
            fail(26)
        le32(p)
        total = v
        p += 4
        nby = ((total + 7) & MASK32) >> 3
        if pe - p < nby:
            fail(27)
        q = p
        acc = 0
        cnt = 0
        oe = o + m
        while o < oe:
            # bytes behind the stream may be pulled here; only bits of the stream are consumed in a
            # valid stream, and the count is checked below
            while cnt < hk:
                acc = (acc << 8) | M[q]
                q += 1
                cnt += 8
            x = H[HTAB + (acc >> (cnt - hk))]
            if x != 0:
                cnt -= x >> 8
                M[o] = x & 255
            else:
                while cnt < 16:
                    acc = (acc << 8) | M[q]
                    q += 1
                    cnt += 8
                l = hk
                while True:
                    l += 1
                    if l > 16:
                        fail(28)
                    c = acc >> (cnt - l)
                    t = H[HFIRST + l]
                    if c >= t and c - t < H[HCNT + l]:
                        break
                M[o] = H[HSORT + H[HOFF + l] + (c - t)]
                cnt -= l
            acc = acc & ((1 << cnt) - 1)
            o += 1
        if (q - p) * 8 - cnt != total:
            fail(29)
        p += nby
        left -= m
        ns -= 1
    if p != pe:
        fail(30)


def rans0():
    """Literal mode 1 at p (payload ends at pe): [L_bits:1][maxSym:1][3 bytes per frequency] + rANS stream."""
    if pe - p < 2:
        fail(31)
    lb = M[p]
    ms = M[p + 1]
    p += 2
    if pe - p < 3 * (ms + 1):
        fail(32)
    if lb < 1 or lb > 16:
        fail(33)
    size = 1 << lb
    t = 0
    s = 0
    while s <= ms:
        x = M[p] | (M[p + 1] << 8) | (M[p + 2] << 16)
        p += 3
        if x > size - t:
            fail(34)
        H[RFREQ + s] = x
        H[RCUM + s] = t
        i = SLOT + t
        t += x
        q = SLOT + t
        while i < q:
            M[i] = s
            i += 1
        s += 1
    if t != size:
        fail(35)
    if pe - p < 8:
        fail(36)
    le32(p)
    p += 4
    if v < 4 or pe - p < v:
        fail(37)
    x = (M[p] << 24) | (M[p + 1] << 16) | (M[p + 2] << 8) | M[p + 3]
    if (x >> 16) == 0:
        fail(38)
    q = p + 4
    qe = p + v
    mask = size - 1
    o = ld
    oe = ld + scount
    while o < oe:
        r = x & mask
        s = M[SLOT + r]
        M[o] = s
        o += 1
        x = H[RFREQ + s] * (x >> lb) + (r - H[RCUM + s])
        while (x >> 16) == 0:
            if q >= qe:
                fail(39)
            x = (x << 8) | M[q]
            q += 1


def literals():
    """The literal section at p. Afterwards the literals are M[lp .. lend) and p is behind the section."""
    lmode = M[p]
    p += 1
    leb(end)
    lcount = v
    if lcount > isize:
        fail(40)
    litb = LIT
    if lmode == 8:                       # literal epochs: [size][n] and n sections
        leb(end)
        if end - p < v:
            fail(41)
        send = p + v
        leb(send)
        nsec = v
        if nsec < 1 or nsec > 256:
            fail(42)
        nested = 1
    else:
        nsec = 1
        send = end
        nested = 0
    lo = 0
    while nsec > 0:
        if nested:
            if p >= send:
                fail(43)
            smode = M[p]
            p += 1
            leb(send)
            scount = v
            if scount > lcount - lo:
                fail(44)
        else:
            smode = lmode
            scount = lcount
        if smode == 0:                   # raw
            if send - p < scount:
                fail(45)
            if nested:
                ld = LIT + lo
                copy(ld, p, scount)
            else:
                litb = p                 # read in place
            p += scount
        else:
            if smode != 1 and smode != 5 and smode != 7:
                fail(46)
            leb(send)
            if send - p < v:
                fail(47)
            pe = p + v
            ld = LIT + lo
            if smode == 1:
                rans0()
            else:
                huffman()
            p = pe
        lo += scount
        nsec -= 1
    if nested:
        if lo != lcount or p != send:
            fail(48)
    lp = litb
    lend = litb + lcount


# =====================================================================================================
# sequences
# =====================================================================================================
def tans_header():
    """Table header at p for table tt: fills H[NORM..], sets lg, size, ms; p moves behind it."""
    hp = p
    hacc = 0
    hn = 0
    hlim = end
    hbits(4)
    lg = hv
    hbits(4)
    tk = hv
    hbits(8)
    ms = hv
    if lg < 5 or lg > 12 or tk > 11 or ms > H[AMAX + tt]:
        fail(50)
    size = 1 << lg
    total = 0
    s = 0
    while s < ms:
        q = 0
        while True:
            hbits(1)
            if hv == 0:
                break
            q += 1
            if q > size:
                fail(51)
        hbits(tk)
        x = (q << tk) | hv
        if x > size - total:
            fail(52)
        H[NORM + s] = x
        total += x
        if x == 0:
            gamma()
            g -= 1
            if s + g >= ms:
                fail(53)
            while g > 0:
                s += 1
                H[NORM + s] = 0
                g -= 1
        s += 1
    if total >= size:
        fail(54)
    H[NORM + ms] = size - total
    p = hp


def build_dtable():
    """Decode table of table tt from H[NORM + 0..ms] (spread, then one entry per state)."""
    mask = size - 1
    step_ = (size >> 1) + (size >> 3) + 3
    pos = 0
    s = 0
    while s <= ms:
        c = H[NORM + s]
        H[NEXT + s] = c
        while c > 0:
            M[SPREAD + pos] = s
            pos = (pos + step_) & mask
            c -= 1
        s += 1
    tb = TBL + (tt << 13)
    ib = INFO + (tt << 8)
    te = tb
    i = 0
    while i < size:
        s = M[SPREAD + i]
        x = H[NEXT + s]
        H[NEXT + s] = x + 1
        nb = lg - H[HB + x]
        H[te] = nb | ((tb + (((x << nb) - size) << 1)) << 8)
        H[te + 1] = H[ib + s]
        te += 2
        i += 1
    H[TLOG + tt] = lg


def seq_epoch():
    """The n sequences of one epoch."""
    bn = H[TLOG]
    bread()
    sl = TBL + (bv << 1)
    bn = H[TLOG + 2]
    bread()
    so = TBL + 16384 + (bv << 1)
    bn = H[TLOG + 1]
    bread()
    sm = TBL + 8192 + (bv << 1)
    while True:
        mw = H[sm + 1]
        if mw != 0:
            ow = H[so + 1]
            x = ow >> 30
            if x == 0:                   # new offset: always pushed
                md = ow >> 5
                bn = ow & 31
                if bn != 0:
                    bread()
                    md += bv << 3
                r2 = r1
                r1 = r0
                r0 = md
            elif x == 1:                 # rep0
                md = r0
            elif x == 2:                 # rep1 to the front
                md = r1
                r1 = r0
                r0 = md
            else:                        # rep2 to the front
                md = r2
                r2 = r1
                r1 = r0
                r0 = md
            ml = mw >> 5
            bn = mw & 31
            if bn != 0:
                bread()
                ml += bv
        lw = H[sl + 1]
        ll = lw >> 5
        bn = lw & 31
        if bn != 0:
            bread()
            ll += bv
        n -= 1
        if n != 0:                       # state updates ll, ml, of; none after the last of an epoch
            x = H[sl]
            bn = x & 255
            bread()
            sl = (x >> 8) + (bv << 1)
            x = H[sm]
            bn = x & 255
            bread()
            sm = (x >> 8) + (bv << 1)
            x = H[so]
            bn = x & 255
            bread()
            so = (x >> 8) + (bv << 1)
        if bptr < blo:
            fail(60)
        if done:
            fail(61)
        dbg(ll)
        if ll > lend - lp or ll > oend - o:
            fail(62)
        copy(o, lp, ll)
        o += ll
        lp += ll
        if mw == 0:                      # literals only: it must complete the output
            if o != oend:
                fail(63)
            done = 1
        else:
            dbg(ml)
            dbg(md)
            if md == 0 or md > o - OUT or ml > oend - o:
                fail(64)
            t = o - md
            copy(o, t, ml)
            o += ml
        if n == 0:
            break


def normal_block():
    """Normal format 2 block; p is behind [flags][isize]. The output goes to M[OUT .. OUT + isize)."""
    literals()
    if end - p < 4:
        fail(70)
    le32(p)
    sc = v
    p += 4
    if sc > (1 << 24):
        fail(71)
    o = OUT
    oend = OUT + isize
    if sc == 0:
        if isize != 0 or p != end:
            fail(72)
        return
    leb(end)
    ne = v
    if ne < 1 or ne > 1024 or ne > sc:
        fail(73)
    hp0 = p
    pas = 0
    r0 = 0
    r1 = 0
    r2 = 0
    done = 0
    # two passes over the epoch headers: pass 0 validates them and finds the bitstream behind the last
    # one, pass 1 reads them again epoch by epoch, builds the tables and decodes the sequences
    while True:
        p = hp0
        e = 0
        ssum = 0
        while e < ne:
            leb(end)
            n = v
            if pas == 0:
                if n < 1 or n > sc - ssum:
                    fail(74)
                ssum += n
            tt = 0
            while tt < 3:
                if p < end and M[p] == 0:        # the table of the previous epoch
                    if e == 0:
                        fail(75)
                    p += 1
                else:
                    tans_header()
                    if pas:
                        build_dtable()
                        dbg(lg)
                tt += 1
            if pas:
                seq_epoch()
            e += 1
        if pas:
            break
        if ssum != sc:
            fail(76)
        if end - p < 4:
            fail(77)
        le32(p)
        p += 4
        if end - p != v or v < 9:        # [bits len:4][8 pad bytes][bitstream] ends the block
            fail(78)
        blo = p + 8
        bptr = end - 1
        t = M[bptr]
        if t == 0:
            fail(79)
        bcnt = H[HB + t]                 # the highest set bit of the last byte is the end marker
        bacc = t - (1 << bcnt)
        pas = 1
    if o != oend:
        fail(80)
    if bptr != blo or bcnt != 0:
        fail(81)
    if lp != lend:
        fail(82)


# =====================================================================================================
# x86 filter (inverse E8/E9 converter of xz / 7-Zip) on M[xb .. xb + xs), position xn
# =====================================================================================================
def unbcj():
    if xs < 5:
        return
    xm = 0
    xp = (xn - 5) & MASK32
    xl = xs - 5
    xi = 0
    while True:
        while xi <= xl and (M[xb + xi] & 254) != 232:
            xi += 1
        if xi > xl:
            break
        xo = (xn + xi - xp) & MASK32
        xp = xn + xi
        if xo > 5:
            xm = 0
        else:
            while xo > 0:
                xm = (xm & 0x77) << 1
                xo -= 1
        xq = xb + xi
        xt = M[xq + 4]
        x = xm >> 1
        if (xt == 0 or xt == 255) and x < 16 and ((x & 7) < 3 or (x & 7) == 4):
            xsrc = (xt << 24) | (M[xq + 3] << 16) | (M[xq + 2] << 8) | M[xq + 1]
            while True:
                xd = (xsrc - (xn + xi + 5)) & MASK32
                if xm == 0:
                    break
                xk = 24                  # 8 * bitnum[x], bitnum = 0 1 2 2 3 3 3 3 (x <= 7 here)
                if x < 4:
                    xk = 16
                if x == 1:
                    xk = 8
                xt = (xd >> (24 - xk)) & 255
                if xt != 0 and xt != 255:
                    break
                xsrc = xd ^ ((1 << (32 - xk)) - 1)
            M[xq + 4] = (0 - ((xd >> 24) & 1)) & 255
            M[xq + 3] = (xd >> 16) & 255
            M[xq + 2] = (xd >> 8) & 255
            M[xq + 1] = xd & 255
            xi += 5
            xm = 0
        else:
            xi += 1
            xm = xm | 1
            if xt == 0 or xt == 255:
                xm = xm | 16


# =====================================================================================================
# one chunk = one seq block at M[0 .. need)
# =====================================================================================================
def decode_chunk():
    if inited == 0:
        init_consts()
        inited = 1
    end = need
    p = 0
    flags = M[0]
    le32(1)
    isize = v
    if isize > OMAX:
        fail(90)
    nr = 0
    if flags & 16:                       # x86 block: [nr:vlq][nr x (start:4, len:4)][inner block]
        if end < 19:
            fail(91)
        q = 5
        while True:                      # 255-continuation count; anything above isize / 65536 + 1 fails
            if q >= end:
                break
            t = M[q]
            q += 1
            nr += t
            if t != 255 or nr > 1023:
                break
        if nr < 1 or nr > (isize >> 16) + 1:
            fail(92)
        if end - q < nr * 8 + 5:
            fail(93)
        xr = q
        q += nr * 8
        t = xr
        xe = 0
        while t < q:                     # ranges: sorted, not overlapping, at least 5 bytes, inside isize
            le32(t)
            xn = v
            t += 4
            le32(t)
            t += 4
            if xn < xe or v < 5 or v > isize or xn > isize - v:
                fail(94)
            xe = xn + v
        flags = M[q]
        if flags & 16:
            fail(95)
        p = q
        t = p + 1
        le32(t)
        if v != isize:
            fail(96)
    if flags & 12:                       # plane and PRNG blocks: not in this subset
        fail(97)
    if flags & 1:                        # stored: emitted (and filtered) where it is
        if end - p - 5 != isize:
            fail(98)
        ob = p + 5
    else:
        if (flags & 32) == 0:            # format 1: not in this subset
            fail(99)
        if end - p < 6:
            fail(100)
        p += 5
        normal_block()
        ob = OUT
    while nr > 0:
        le32(xr)
        xn = v
        xr += 4
        le32(xr)
        xs = v
        xr += 4
        xb = ob + xn
        unbcj()
        nr -= 1
    emit(ob, isize)


# =====================================================================================================
# entry: one call per input byte, and one with inp > 255 at the end of the segment
#   st: 0 reading n_chunks, 1 reading csize, 2 reading the chunk, 3 finished or failed (input ignored)
# =====================================================================================================
def step(inp):
    if inp > 255:
        st = 0
        hsh = 0
        hval = 0
        return
    if st == 2:
        M[wp] = inp
        wp += 1
        if wp == need:
            st = 3
            try:
                decode_chunk()
                nch -= 1
                if nch != 0:
                    st = 1
            except Fail:
                dbg(ferr)
        return
    if st < 2:
        hval = hval | (inp << hsh)
        hsh += 8
        if hsh == 32:
            hsh = 0
            if st == 0:
                nch = hval
                st = 1
                if nch == 0:
                    st = 3
            else:
                need = hval
                wp = 0
                st = 2
                if need < 5 or need > INMAX:
                    st = 3
            hval = 0
