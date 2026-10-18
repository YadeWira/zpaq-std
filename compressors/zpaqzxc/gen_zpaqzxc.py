#!/usr/bin/env python3
# Generates ZPAQZXC: a ZPAQL post-processor that decodes one zxc frame (format 9,
# no dictionary) per segment, written for zpaq-std from docs/FORMAT.md, the same
# algorithm as zxc_ref.py. The segment is the original size (u32le) and the frame.
# The input is kept in M from 0; at the end of the segment it is decoded: RAW,
# GLO and GHI blocks, RLE and PivCo Huffman literals, Huffman tokens (level 7).
# M: input [0,n), literal buffer LB = n, token buffer TB = n + bs, output from
# OB = n + 2*bs (bs = the frame's block size). H: the Huffman tree (see below).
# The decoder never writes more than the original size, and stops on a broken
# table or block (the SHA-1 check then reports it).
#   gen_zpaqzxc.py body > body.txt     (the config line comes from zpaq-std)
import sys
out = []
def e(s): out.append(s)

R = {}
def reg(name):
    if name not in R: R[name] = 10 + len(R)
    return R[name]
for n in ['N', 'IP', 'BS', 'CK', 'LB', 'TB', 'REM', 'TYP', 'SIZE', 'P', 'Q', 'NSEQ', 'NLIT', 'EL', 'ET', 'EO',
          'LP', 'LEND', 'TP', 'OFF', 'EX', 'I', 'LL', 'ML', 'OFS', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
          'HS', 'HN', 'HD', 'HPB', 'MAXD', 'NPRES', 'DD', 'II', 'GG', 'KK', 'TOT', 'CC', 'FF', 'ONES', 'PP',
          'BAD', 'J', 'SQ', 'STOP', 'TMP', 'TMP2', 'WID', 'FST', 'OUTP', 'LC', 'TC']:
    reg(n)
r = lambda n: R[n]

# H layout (words)
H_L, H_BLC, H_FIRST, H_SYMS, H_LB, H_NB, H_FN, H_POS, H_FLAT, H_CNT, H_CUR = 0, 256, 272, 288, 544, 560, 576, 592, 640, 1200, 1800

def K(v):                       # a = constant
    if v < 256: e(f'a= {v}'); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f'a= {bs[-1]}')
    for b in reversed(bs[:-1]): e(f'a<<= 8 a+= {b}' if b else 'a<<= 8')
def SETK(name, v): K(v); e(f'r=a {r(name)}')
def MOV(dst, src): e(f'a=r {r(src)} r=a {r(dst)}')
def INC(name, by=1):
    e(f'a=r {r(name)} a+= {by} r=a {r(name)}' if by != 1 else f'a=r {r(name)} a++ r=a {r(name)}')
def ADDR(dst, x, y):           # dst = x + y (registers)
    e(f'a=r {r(y)} b=a a=r {r(x)} a+=b r=a {r(dst)}')
def MB(addrname, plus=0):      # a = M[r addr + plus]
    e(f'a=r {r(addrname)}')
    if plus: e(f'a+= {plus}')
    e('c=a a=*c')
def U32(dst, addrname, plus=0):  # dst = u32le at M[addr+plus]
    e(f'a=r {r(addrname)}')
    if plus: e(f'a+= {plus}')
    e(f'c=a a=*c r=a {r(dst)} c++ a=*c a<<= 8 b=a a=r {r(dst)} a+=b r=a {r(dst)}')
    e(f'c++ a=*c a<<= 16 b=a a=r {r(dst)} a+=b r=a {r(dst)} c++ a=*c a<<= 24 b=a a=r {r(dst)} a+=b r=a {r(dst)}')
def HGET(base, idxname):       # a = H[base + r idx]
    e(f'a=r {r(idxname)} a+= 0')
    K_add(base); e('d=a a=*d')
def K_add(v):                  # a += constant
    if v == 0: return
    if v < 256: e(f'a+= {v}'); return
    e('b=a'); K(v); e('a+=b')
def HSETV(base, idxname, valname):   # H[base + r idx] = r val
    e(f'a=r {r(idxname)}'); K_add(base); e(f'd=a a=r {r(valname)} *d=a')
def OUTB():                    # write a (byte) to output: M[b] = a, out, b++, REM--
    e(f'*b=a out b++ a=r {r("REM")} a-- r=a {r("REM")}')

# ---------------------------------------------------------------- Huffman section
# input: HS = section start in M, HN = symbols, HD = destination in M. Sets BAD on a bad table.
def huffman():
    # lengths
    SETK('I', 0)
    e('do')
    e(f'  a=r {r("I")} c=r {r("HS")} a+=c c=a a=*c r=a {r("T")}')
    e(f'  a=r {r("I")} a<<= 1 d=a a=r {r("T")} a&= 15 *d=a d++ a=r {r("T")} a>>= 4 *d=a')
    INC('I'); e(f'a=r {r("I")} a< 128')
    e('while')
    # BLC, max depth, present count
    e(f'a=0 r=a {r("MAXD")} r=a {r("NPRES")} r=a {r("I")}')
    e('do'); e(f'  a=r {r("I")}'); K_add(H_BLC); e('  d=a a=0 *d=a'); INC('I'); e(f'a=r {r("I")} a< 14'); e('while')
    SETK('I', 0)
    e('do')
    e(f'  a=r {r("I")} d=a a=*d a> 0 if')
    e(f'    r=a {r("T")}'); K_add(H_BLC); e('    d=a a=*d a++ *d=a')
    e(f'    a=r {r("NPRES")} a++ r=a {r("NPRES")}')
    e(f'    a=r {r("T")} b=r {r("MAXD")} a>b if r=a {r("MAXD")} endif')
    e('  endif')
    INC('I'); e(f'a= 255 a++ b=a a=r {r("I")} a<b'); e('while')
    # validation: lengths <= 11, Kraft
    e(f'a=r {r("MAXD")} a> 11 if a= 1 r=a {r("BAD")} endif')
    e(f'a=r {r("NPRES")} a== 0 if a= 1 r=a {r("BAD")} endif')
    e(f'a=r {r("NPRES")} a== 1 ifl')
    e(f'  a= {H_BLC+1} d=a a=*d a== 1 ifnot a= 1 r=a {r("BAD")} endif')
    e('elsel')
    e(f'  a=0 r=a {r("T")} a= 1 r=a {r("I")}')
    e('  do')
    e(f'    a=r {r("I")}'); K_add(H_BLC); e(f'    d=a a=*d r=a {r("U")} a= 11 b=r {r("I")} a-=b c=a a=r {r("U")} a<<=c b=a a=r {r("T")} a+=b r=a {r("T")}')
    INC('I'); e(f'  a=r {r("I")} a< 12')
    e('  while')
    K(2048); e(f'  b=a a=r {r("T")} a==b ifnot a= 1 r=a {r("BAD")} endif')
    e('endif')
    e(f'a=r {r("BAD")} a== 0 ifl')
    # FIRST canonical codes; LEAFBASE; node bases
    e(f'  a=0 r=a {r("T")} a= {H_FIRST+1} d=a a=0 *d=a a= 2 r=a {r("I")}')
    e('  do')
    e(f'    a=r {r("I")}'); K_add(H_BLC - 1); e(f'    d=a a=*d b=a a=r {r("T")} a+=b a<<= 1 r=a {r("T")}')
    e(f'    a=r {r("I")}'); K_add(H_FIRST); e(f'    d=a a=r {r("T")} *d=a')
    INC('I'); e(f'    a=r {r("I")} a< 12')
    e('  while')
    e(f'  a= {H_LB} d=a a=0 *d=a a=0 r=a {r("I")}')
    e('  do')
    e(f'    a=r {r("I")}'); K_add(H_LB); e(f'    d=a a=*d r=a {r("T")} a=r {r("I")}'); K_add(H_BLC); e(f'    d=a a=*d b=a a=r {r("T")} a+=b r=a {r("T")}')
    e(f'    a=r {r("I")}'); K_add(H_LB + 1); e(f'    d=a a=r {r("T")} *d=a')
    e(f'    a=r {r("I")}'); K_add(H_POS); e(f'    d=a a=r {r("I")}'); K_add(H_LB); e('    c=a d=a a=*d r=a 250'); e(f'    a=r {r("I")}'); K_add(H_POS); e('    d=a a=r 250 *d=a')
    INC('I'); e(f'    a=r {r("I")} a< 13')
    e('  while')
    # SYMS in canonical order
    e(f'  a=0 r=a {r("I")}')
    e('  do')
    e(f'    a=r {r("I")} d=a a=*d a> 0 if')
    e(f'      '); K_add(H_POS); e(f'      d=a a=*d r=a {r("T")} a++ *d=a a=r {r("T")}'); K_add(H_SYMS); e(f'      d=a a=r {r("I")} *d=a')
    e('    endif')
    INC('I'); e(f'    a= 255 a++ b=a a=r {r("I")} a<b')
    e('  while')
    # node bases: width, first
    e(f'  a= {H_NB} d=a a=0 *d=a a= 1 r=a {r("WID")} a=0 r=a {r("FST")} r=a {r("DD")}')
    e('  do')
    e(f'    a=r {r("DD")}'); K_add(H_FN); e(f'    d=a a=r {r("FST")} *d=a')
    e(f'    a=r {r("DD")}'); K_add(H_NB); e(f'    d=a a=*d b=a a=r {r("WID")} a+=b r=a {r("T")} d++ a=r {r("T")} *d=a')
    e(f'    a=r {r("DD")}'); K_add(H_BLC); e(f'    d=a a=*d r=a {r("U")} b=a a=r {r("FST")} a+=b a<<= 1 r=a {r("FST")}')
    e(f'    a=r {r("DD")} a== 0 if a=r {r("NPRES")} a== 1 endif ifl a= 1 r=a {r("WID")} elsel a=r {r("U")} b=a a=r {r("WID")} a-=b a<<= 1 r=a {r("WID")} endif')
    INC('DD'); e(f'    a=r {r("MAXD")} b=a a=r {r("DD")} a>b')
    e('  until')
    # FLAT heights, bottom up; slot = 0; INCOMPLETE = 254
    e(f'  a=r {r("MAXD")} a++'); K_add(H_NB); e('  d=a a=*d'); K_add(H_FLAT); e('  d=a a=0 *d=a')
    e(f'  a=r {r("MAXD")} r=a {r("DD")}')
    e('  do')
    e(f'    a=r {r("DD")}'); K_add(H_NB); e(f'    d=a a=*d r=a {r("GG")} d++ a=*d r=a {r("KK")} d++ a=*d r=a {r("PP")}')   # GG=nb[d] KK=nb[d+1] PP=nb[d+2]
    e(f'    a=r {r("DD")}'); K_add(H_BLC); e(f'    d=a a=*d r=a {r("U")}')                        # leaves
    e(f'    a=0 r=a {r("I")}')
    e(f'    a=r {r("KK")} b=r {r("GG")} a-=b r=a {r("V")}')                                         # N
    e(f'    a=r {r("V")} a> 0 ifl')
    e('      do')
    e(f'        a=r {r("I")} b=r {r("GG")} a+=b'); K_add(H_FLAT); e(f'        r=a {r("X")}')
    e(f'        a=r {r("I")} b=r {r("U")} a<b ifl')
    e(f'          a=r {r("X")} d=a a=0 *d=a')
    e('        elsel')
    e(f'          a=r {r("I")} b=r {r("U")} a-=b a<<= 1 b=r {r("KK")} a+=b'); K_add(H_FLAT); e(f'          d=a a=*d r=a {r("Y")} d++ a=*d r=a {r("Z")}')
    e(f'          a=r {r("Y")} b=r {r("Z")} a==b ifl a=r {r("Y")} a== 254 ifnot a++ r=a {r("Y")} endif elsel a= 254 r=a {r("Y")} endif')
    e(f'          a=r {r("X")} d=a a=r {r("Y")} *d=a')
    e('        endif')
    INC('I'); e(f'        a=r {r("V")} b=a a=r {r("I")} a<b')
    e('      while')
    e('    endif')
    e(f'    a=r {r("DD")} a== 0 ifl a= 1 r=a {r("STOP")} elsel a-- r=a {r("DD")} a=0 r=a {r("STOP")} endif')
    e(f'    a=r {r("STOP")} a== 0')
    e('  while')
    # top down: covered = 255, flat if height >= 2
    e(f'  a=0 r=a {r("DD")}')
    e(f'  a=r {r("MAXD")} a> 0 ifl')
    e('  do')
    e(f'    a=r {r("DD")}'); K_add(H_NB); e(f'    d=a a=*d r=a {r("GG")} d++ a=*d r=a {r("KK")}')
    e(f'    a=r {r("DD")}'); K_add(H_BLC); e(f'    d=a a=*d r=a {r("U")} r=a {r("I")}')
    e(f'    a=r {r("DD")} a> 0 ifl a-- r=a {r("T")}'); K_add(H_NB); e(f'      d=a a=*d r=a {r("PP")} a=r {r("T")}'); K_add(H_BLC); e(f'      d=a a=*d b=r {r("PP")} a+=b r=a {r("PP")} endif')  # PP = first internal of d-1
    e(f'    a=r {r("I")} b=r {r("KK")} c=a a=r {r("GG")} a+=c a<b ifl')
    e('      do')
    e(f'        a=r {r("I")} b=r {r("GG")} a+=b'); K_add(H_FLAT); e(f'        d=a a=*d r=a {r("Y")} a=0 r=a {r("Z")}')
    e(f'        a=r {r("DD")} a> 0 ifl a=r {r("I")} a>>= 1 b=r {r("PP")} a+=b'); K_add(H_FLAT); e(f'          d=a a=*d a> 0 if a= 1 r=a {r("Z")} endif endif')
    e(f'        a=r {r("I")} b=r {r("GG")} a+=b'); K_add(H_FLAT); e('        d=a')
    e(f'        a=r {r("Z")} a== 1 ifl a= 255 *d=a elsel a=r {r("Y")} a< 2 if a=0 *d=a else a== 254 if a=0 *d=a endif endif endif')
    INC('I'); e(f'        a=r {r("KK")} b=r {r("GG")} a-=b b=a a=r {r("I")} a<b')
    e('      while')
    e('    endif')
    INC('DD'); e(f'    a=r {r("MAXD")} b=a a=r {r("DD")} a<b')
    e('  while')
    e('  endif')
    # counts and cursors (bit positions from HPB = HS + 128)
    e(f'  a=r {r("HS")} a+= 128 r=a {r("HPB")} a=0 r=a {r("TOT")}')
    e(f'  a= {H_CNT} d=a a=r {r("HN")} *d=a a=0 r=a {r("DD")}')
    e(f'  a=r {r("MAXD")} a> 0 ifl')
    e('  do')
    e(f'    a=r {r("DD")}'); K_add(H_NB); e(f'    d=a a=*d r=a {r("GG")} d++ a=*d r=a {r("KK")}')
    e(f'    a=r {r("DD")}'); K_add(H_BLC); e(f'    d=a a=*d r=a {r("U")} r=a {r("I")}')
    e(f'    a=r {r("I")} b=r {r("GG")} a+=b b=r {r("KK")} a<b ifl')
    e('    do')
    e(f'      a=r {r("I")} b=r {r("GG")} a+=b r=a {r("X")}'); K_add(H_FLAT); e(f'      d=a a=*d r=a {r("FF")}')
    e(f'      a=r {r("FF")} a== 255 ifnotl')
    e(f'        a=r {r("X")}'); K_add(H_CUR); e(f'        d=a a=r {r("TOT")} a<<= 3 *d=a')
    e(f'        a=r {r("X")}'); K_add(H_CNT); e(f'        d=a a=*d r=a {r("CC")}')
    e(f'        a=r {r("FF")} a> 0 ifl')
    e(f'          a=r {r("CC")} b=r {r("FF")} a*=b a+= 7 a>>= 3 b=a a=r {r("TOT")} a+=b r=a {r("TOT")}')
    e('        elsel')
    # popcount of CC bits from TOT*8
    e(f'          a=0 r=a {r("ONES")} r=a {r("J")} a=r {r("TOT")} b=r {r("HPB")} a+=b r=a {r("PP")}')
    e(f'          a=r {r("CC")} a> 0 ifl')
    e('          do')
    e(f'            a=r {r("J")} a>>= 3 b=r {r("PP")} a+=b c=a a=r {r("J")} a&= 7 b=a a=*c a>>=b a&= 1 b=a a=r {r("ONES")} a+=b r=a {r("ONES")}')
    INC('J'); e(f'            a=r {r("CC")} b=a a=r {r("J")} a<b')
    e('          while')
    e('          endif')
    e(f'          a=r {r("I")} b=r {r("U")} a-=b a<<= 1 b=r {r("KK")} a+=b'); K_add(H_CNT)
    e(f'          d=a a=r {r("ONES")} b=a a=r {r("CC")} a-=b *d=a d++ a=r {r("ONES")} *d=a')
    e(f'          a=r {r("CC")} a+= 7 a>>= 3 b=a a=r {r("TOT")} a+=b r=a {r("TOT")}')
    e('        endif')
    e('      endif')
    INC('I'); e(f'      a=r {r("KK")} b=a a=r {r("I")} c=r {r("GG")} a+=c a<b')
    e('    while')
    e('    endif')
    INC('DD'); e(f'    a=r {r("MAXD")} b=a a=r {r("DD")} a<b')
    e('  while')
    e('  endif')
    # decode HN symbols into M[HD..]
    e(f'  a=0 r=a {r("I")}')
    e(f'  a=r {r("HN")} a> 0 ifl')
    e('  do')
    e(f'    a=0 r=a {r("DD")} r=a {r("PP")} r=a {r("STOP")}')
    e('    do')
    e(f'      a=r {r("DD")}'); K_add(H_FN); e(f'      d=a a=*d b=a a=r {r("PP")} a-=b r=a {r("KK")}')          # idx
    e(f'      a=r {r("DD")}'); K_add(H_BLC); e(f'      d=a a=*d b=a a=r {r("KK")} a<b ifl')                  # leaf
    e(f'        a=r {r("DD")}'); K_add(H_LB); e(f'        d=a a=*d b=r {r("KK")} a+=b'); K_add(H_SYMS)
    e(f'        d=a a=*d r=a {r("T")} a=r {r("I")} b=r {r("HD")} a+=b c=a a=r {r("T")} *c=a a= 1 r=a {r("STOP")}')
    e('      elsel')
    e(f'        a=r {r("DD")} b=r {r("MAXD")} a<b ifnotl a=0 r=a {r("PP")} a= 1 r=a {r("STOP")} elsel')
    e(f'        a=r {r("DD")}'); K_add(H_NB); e(f'        d=a a=*d b=r {r("KK")} a+=b r=a {r("X")}'); K_add(H_FLAT); e(f'        d=a a=*d r=a {r("FF")}')
    e(f'        a=r {r("X")}'); K_add(H_CUR); e(f'        d=a a=*d r=a {r("J")}')
    e(f'        a=r {r("FF")} a> 0 ifl a== 255 if a=0 r=a {r("FF")} endif endif')
    e(f'        a=r {r("FF")} a== 0 if a= 1 r=a {r("FF")} endif')
    # read FF bits MSB first from J
    e(f'        a=0 r=a {r("V")} r=a {r("W")}')
    e('        do')
    e(f'          a=r {r("J")} a>>= 3 b=r {r("HPB")} a+=b c=a a=r {r("J")} a&= 7 b=a a=*c a>>=b a&= 1 b=a a=r {r("V")} a<<= 1 a+=b r=a {r("V")}')
    INC('J'); INC('W'); e(f'          a=r {r("FF")} b=a a=r {r("W")} a<b')
    e('        while')
    e(f'        a=r {r("X")}'); K_add(H_CUR); e(f'        d=a a=r {r("J")} *d=a')
    e(f'        a=r {r("FF")} c=a a=r {r("PP")} a<<=c b=r {r("V")} a+=b r=a {r("PP")} a=r {r("DD")} b=r {r("FF")} a+=b r=a {r("DD")}')
    e('        endif')
    e('      endif')
    e(f'    a=r {r("STOP")} a== 0')
    e('    while')
    INC('I'); e(f'    a=r {r("HN")} b=a a=r {r("I")} a<b')
    e('  while')
    e('  endif')
    e('endif')

def varint(dst):               # r dst = varint at M[EX], EX advanced
    e(f'a=r {r("EX")} c=a a=*c r=a {r("T")}')
    e(f'a< 128 ifl a=r {r("T")} r=a {r(dst)} a=r {r("EX")} a++ r=a {r("EX")}')
    e(f'elsel a=r {r("T")} a< 192 ifl')
    e(f'  c++ a=*c a<<= 6 b=a a=r {r("T")} a&= 63 a+=b r=a {r(dst)} a=r {r("EX")} a+= 2 r=a {r("EX")}')
    e(f'elsel')
    e(f'  c++ a=*c a<<= 5 b=a c++ a=*c a<<= 13 a+=b b=a a=r {r("T")} a&= 31 a+=b r=a {r(dst)} a=r {r("EX")} a+= 3 r=a {r("EX")}')
    e('endif endif')

def copy_lits():               # LL literals from LP (clamped to REM)
    e(f'a=r {r("LL")} b=r {r("REM")} a>b if a=b r=a {r("LL")} endif')
    e(f'a=r {r("LL")} a> 0 ifl')
    e(f'  a=r {r("OUTP")} b=a a=r {r("LP")} c=a')
    e('  do')
    e('    a=*c'); OUTB(); e(f'    c++ a=r {r("LL")} a-- r=a {r("LL")}')
    e('  a> 0 while')
    e(f'  a=c r=a {r("LP")} a=b r=a {r("OUTP")}')
    e('endif')

def copy_match():              # ML bytes from b - OFS (clamped to REM)
    e(f'a=r {r("ML")} b=r {r("REM")} a>b if a=b r=a {r("ML")} endif')
    e(f'a=r {r("ML")} a> 0 ifl')
    e(f'  a=r {r("OUTP")} b=a c=r {r("OFS")} a-=c c=a')
    e('  do')
    e('    a=*c'); OUTB(); e(f'    c++ a=r {r("ML")} a-- r=a {r("ML")}')
    e('  a> 0 while')
    e(f'  a=b r=a {r("OUTP")}')
    e('endif')

def tail():                    # literals left after the last sequence
    e(f'a=r {r("LEND")} b=r {r("LP")} a-=b r=a {r("LL")}')
    copy_lits()

# ---------------------------------------------------------------- program
e('hcomp')
e('  halt')
e('pcomp zpaqzxc ;')
e('  (zxc format 9; see gen_zpaqzxc.py)')
e(f'a> 255 ifl')
# ---- end of segment: decode M[0..N)
e(f'  a=0 r=a {r("BAD")}')
U32('REM', 'IP')                     # IP is 0 here: original size
e(f'  a= 4 r=a {r("IP")}')
e(f'  a=r {r("IP")} a+= 5 c=a a=*c r=a {r("T")} a< 12 if a= 1 r=a {r("BAD")} endif a=r {r("T")} a> 21 if a= 1 r=a {r("BAD")} endif')
e(f'  a=r {r("BAD")} a== 0 ifl')
e(f'  a=r {r("T")} c=a a= 1 a<<=c r=a {r("BS")}')
e(f'  a=r {r("IP")} a+= 6 c=a a=*c a>>= 7 a<<= 2 r=a {r("CK")}')
e(f'  a=r {r("N")} r=a {r("LB")} b=r {r("BS")} a+=b r=a {r("TB")} a+=b r=a {r("OUTP")}')
e(f'  a=r {r("IP")} a+= 16 r=a {r("IP")}')
e('  do')                                                     # blocks
e(f'    a=r {r("IP")} c=a a=*c r=a {r("TYP")}')
U32('SIZE', 'IP', 3)
e(f'    a=r {r("IP")} a+= 8 r=a {r("P")} r=a {r("Q")}')
e(f'    a=r {r("SIZE")} b=r {r("BS")} a>b if a=r {r("TYP")} a< 3 if a= 1 r=a {r("BAD")} endif endif')
e(f'    a=r {r("TYP")} a> 2 if a= 1 r=a {r("BAD")} endif')
e(f'    a=r {r("BAD")} a== 0 ifl')
e(f'    a=r {r("TYP")} a== 0 ifl')                            # RAW
e(f'      a=r {r("P")} r=a {r("LP")} a=r {r("SIZE")} r=a {r("LL")}')
copy_lits()
e('    elsel')
U32('NSEQ', 'P'); U32('NLIT', 'P', 4)
e(f'      a=r {r("P")} a+= 8 c=a a=*c r=a {r("EL")} c++ a=*c r=a {r("ET")} c++ c++ a=*c r=a {r("EO")}')
e(f'      a=r {r("P")} a+= 12 r=a {r("Q")}')
e(f'      a=r {r("NLIT")} b=r {r("BS")} a>b if a= 1 r=a {r("BAD")} endif a=r {r("NSEQ")} a>b if a= 1 r=a {r("BAD")} endif')
e(f'      a=r {r("TYP")} a== 2 ifl')                           # GHI
e(f'        a=r {r("Q")} r=a {r("LP")} b=r {r("NLIT")} a+=b r=a {r("LEND")} r=a {r("SQ")} a=r {r("NSEQ")} a<<= 2 b=a a=r {r("SQ")} a+=b r=a {r("EX")}')
e(f'      elsel')                                              # GLO
e(f'        a=r {r("EL")} a> 0 if'); U32('LC', 'Q'); e(f'a=r {r("Q")} a+= 4 r=a {r("Q")} endif')
e(f'        a=r {r("ET")} a== 2 if'); U32('TC', 'Q'); e(f'a=r {r("Q")} a+= 4 r=a {r("Q")} endif')
e(f'        a=r {r("EL")} a== 0 ifl')
e(f'          a=r {r("Q")} r=a {r("LP")} b=r {r("NLIT")} a+=b r=a {r("Q")}')
e(f'        elsel a=r {r("EL")} a== 1 ifl')
# RLE into LB
e(f'          a=r {r("Q")} r=a {r("X")} a=r {r("LB")} r=a {r("Y")} a=r {r("NLIT")} r=a {r("Z")}')
e(f'          a=r {r("Z")} a> 0 ifl')
e('          do')
e(f'            a=r {r("X")} c=a a=*c r=a {r("T")} c++ a=c r=a {r("X")}')
e(f'            a=r {r("T")} a< 128 ifl')
e(f'              a++ r=a {r("W")} b=r {r("Z")} a>b if a=b r=a {r("W")} endif')
e(f'              a=r {r("Z")} b=r {r("W")} a-=b r=a {r("Z")}')
e('              do')
e(f'                a=r {r("X")} c=a a=*c r=a {r("T")} c++ a=c r=a {r("X")} a=r {r("Y")} c=a a=r {r("T")} *c=a c++ a=c r=a {r("Y")}')
e(f'              a=r {r("W")} a-- r=a {r("W")} a> 0 while')
e('            elsel')
e(f'              a&= 127 a+= 4 r=a {r("W")} b=r {r("Z")} a>b if a=b r=a {r("W")} endif')
e(f'              a=r {r("Z")} b=r {r("W")} a-=b r=a {r("Z")}')
e(f'              a=r {r("X")} c=a a=*c r=a {r("T")} c++ a=c r=a {r("X")}')
e('              do')
e(f'                a=r {r("Y")} c=a a=r {r("T")} *c=a c++ a=c r=a {r("Y")}')
e(f'              a=r {r("W")} a-- r=a {r("W")} a> 0 while')
e('            endif')
e(f'          a=r {r("Z")} a> 0 while')
e('          endif')
e(f'          a=r {r("LB")} r=a {r("LP")} a=r {r("Q")} b=r {r("LC")} a+=b r=a {r("Q")}')
e(f'        elsel a=r {r("EL")} a== 2 ifl')
e(f'          a=r {r("Q")} r=a {r("HS")} a=r {r("NLIT")} r=a {r("HN")} a=r {r("LB")} r=a {r("HD")}')
huffman()
e(f'          a=r {r("LB")} r=a {r("LP")} a=r {r("Q")} b=r {r("LC")} a+=b r=a {r("Q")}')
e(f'        elsel a= 1 r=a {r("BAD")} endif endif endif')
e(f'        a=r {r("LP")} b=r {r("NLIT")} a+=b r=a {r("LEND")}')
e(f'        a=r {r("ET")} a== 2 ifl')
e(f'          a=r {r("Q")} r=a {r("HS")} a=r {r("NSEQ")} r=a {r("HN")} a=r {r("TB")} r=a {r("HD")}')
huffman()
e(f'          a=r {r("TB")} r=a {r("TP")} a=r {r("Q")} b=r {r("TC")} a+=b r=a {r("Q")}')
e(f'        elsel a=r {r("ET")} a> 0 if a= 1 r=a {r("BAD")} endif a=r {r("Q")} r=a {r("TP")} b=r {r("NSEQ")} a+=b r=a {r("Q")} endif')
e(f'        a=r {r("Q")} r=a {r("OFF")} a=r {r("EO")} a> 0 ifl a=r {r("NSEQ")} elsel a=r {r("NSEQ")} a<<= 1 endif b=a a=r {r("Q")} a+=b r=a {r("EX")}')
e('      endif')
# sequences
e(f'      a=0 r=a {r("I")}')
e(f'      a=r {r("BAD")} a== 0 ifl a=r {r("NSEQ")} a> 0 ifl')
e('      do')
e(f'        a=r {r("TYP")} a== 2 ifl')
e(f'          a=r {r("SQ")} c=a a=*c r=a {r("OFS")} c++ a=*c a<<= 8 b=a a=r {r("OFS")} a+=b a++ r=a {r("OFS")}')
e(f'          c++ a=*c r=a {r("ML")} c++ a=*c r=a {r("LL")} a=r {r("SQ")} a+= 4 r=a {r("SQ")}')
e(f'          a=r {r("LL")} a== 255 if'); varint('T'); e(f'a=r {r("T")} b=r {r("LL")} a+=b r=a {r("LL")} endif')
e(f'          a=r {r("ML")} a== 255 if'); varint('T'); e(f'a=r {r("T")} b=r {r("ML")} a+=b r=a {r("ML")} endif')
e('        elsel')
e(f'          a=r {r("TP")} b=r {r("I")} a+=b c=a a=*c r=a {r("T")} a>>= 4 r=a {r("LL")} a=r {r("T")} a&= 15 r=a {r("ML")}')
e(f'          a=r {r("LL")} a== 15 if'); varint('T'); e(f'a=r {r("T")} b=r {r("LL")} a+=b r=a {r("LL")} endif')
e(f'          a=r {r("ML")} a== 15 if'); varint('T'); e(f'a=r {r("T")} b=r {r("ML")} a+=b r=a {r("ML")} endif')
e(f'          a=r {r("EO")} a> 0 ifl a=r {r("OFF")} b=r {r("I")} a+=b c=a a=*c a++ r=a {r("OFS")}')
e(f'          elsel a=r {r("I")} a<<= 1 b=r {r("OFF")} a+=b c=a a=*c r=a {r("OFS")} c++ a=*c a<<= 8 b=a a=r {r("OFS")} a+=b a++ r=a {r("OFS")} endif')
e('        endif')
e(f'        a=r {r("ML")} a+= 5 r=a {r("ML")}')
copy_lits(); copy_match()
INC('I'); e(f'        a=r {r("REM")} a== 0 ifl a=r {r("NSEQ")} r=a {r("I")} endif a=r {r("NSEQ")} b=a a=r {r("I")} a<b')
e('      while')
e('      endif endif')
tail()
e('    endif')
e(f'    a=r {r("P")} b=r {r("SIZE")} a+=b b=r {r("CK")} a+=b r=a {r("IP")}')
e('    endif')
e(f'    a=r {r("TYP")} a> 2 if a= 1 r=a {r("BAD")} endif a=r {r("REM")} a== 0 if a= 1 r=a {r("BAD")} endif')
e(f'    a=r {r("IP")} b=r {r("N")} a<b ifnot a= 1 r=a {r("BAD")} endif')
e(f'  a=r {r("BAD")} a== 0 while')
e('  endif')
e(f'  a=0 r=a {r("N")} r=a {r("IP")}')
e('  halt')
e('endif')
# ---- a byte: keep it
e(f'c=a a=r {r("N")} b=a a=c *b=a b++ a=b r=a {r("N")}')
e('halt')
e('end')

def kseq(v):                   # instructions that leave the constant v in a
    if v < 256: return [f'a= {v}']
    bs = []
    while v: bs.append(v & 255); v >>= 8
    o = [f'a= {bs[-1]}']
    for x in reversed(bs[:-1]): o += ['a<<= 8'] + ([f'a+= {x}'] if x else [])
    return o

def expand(lines):             # 8-bit immediates only: expand larger ones (b, r252, r253 are scratch)
    import re
    res = []
    for ln in lines:
        toks = ln.split(' '); o = []; i = 0
        while i < len(toks):
            t = toks[i]
            if t in ('a=', 'a+=', 'a<', 'a>', 'a==', 'a-=') and i + 1 < len(toks) and toks[i + 1].isdigit() and int(toks[i + 1]) > 255:
                v = int(toks[i + 1]); i += 2
                if t == 'a=': o += kseq(v); continue
                o += ['r=a 253'] + kseq(v) + ['r=a 252', 'a=r 253', 'b=r 252']
                o += [{'a+=': 'a+=b', 'a<': 'a<b', 'a>': 'a>b', 'a==': 'a==b', 'a-=': 'a-=b'}[t]]
                continue
            o.append(t); i += 1
        res.append(' '.join(o))
    return res

if __name__ == '__main__':
    sys.stdout.write('\n'.join(expand(out)) + '\n')
