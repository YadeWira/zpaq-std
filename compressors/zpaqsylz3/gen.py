#!/usr/bin/env python3
# Generates ZPAQSYLZ3: a ZPAQL post-processor that decodes one sylzec block per
# segment: sylz format v3 (syc v0.2.14, frozen), or a plain v2 block, which is a
# valid v3 one. The segment is the original size (u32le) and the block. Same
# algorithm as ref3.py next to this file, which decodes syc's 220 test vectors:
# the whole segment goes into M; at its end the literals are decoded into a
# buffer (Huffman chunks of 65536 literals, four streams each, or raw ones), then
# v2's sequences rebuild the output from that buffer. Every loop is bounded by a
# count known before it starts, so damaged data ends at once (short output, and
# zpaq's SHA-1 reports it).
#   gen.py PH PM > zpaqsylz3.cfg    or    gen.py body > body.txt
# M (2^PM bytes): the segment, 32 bytes, the literal buffer (litCount), the output.
# H (2^PH words, PH >= 12): token table 0..255, code lengths 256..511, counts
# 512..527, next codes 528..543, the decoding table 2048..4095.
import sys, re, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sylz', 'sylz.pas')).read()
t = src[src.index('SYLZ_TOKENS: array[0..255] of UInt32 = ('):]; t = t[:t.index(');')]
T = [int(x, 16) for x in re.findall(r'\$([0-9A-F]+)', t)]; assert len(T) == 256

out = []
def e(s): out.append(s)

def K(v):                      # a = v
    if v < 256: e(f'a= {v}'); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f'a= {bs[-1]}')
    for b in reversed(bs[:-1]):
        e(f'a<<= 8 a+= {b}' if b else 'a<<= 8')

# registers
N, ORIG, CE, CP, LS, LE, OB, OUTN, ERR, LC, P, LP, LEFT, CC = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
Q, KS, SP, SE, BUF, NB, USED, NS, EE, LL, LIT, ML, OFF = 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27
T1, T2, T3, S, KR, NSYM, CODE, I, RR, J, SZ = 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 40  # SZ..SZ+3
TOK, LEN, CNT, NXT, TAB = 0, 256, 512, 528, 2048

def get(reg, dst):             # r dst = M[r reg]
    e(f'a=r {reg} c=a a=*c r=a {dst}')
def u16(reg, dst):             # r dst = M[reg] | M[reg+1] << 8
    e(f'a=r {reg} c=a a=*c r=a {T3} c++ a=*c a<<= 8 b=r {T3} a+=b r=a {dst}')
def u32(reg, dst):             # r dst = u32le at M[reg]
    e(f'a=r {reg} a+= 3 c=a a=*c')
    for _ in range(3):
        e('a<<= 8 c-- b=a a=*c a+=b')
    e(f'r=a {dst}')
def err(): e(f'a= 1 r=a {ERR}')
def okthen(): e(f'a=r {ERR} a== 0 ifl')
def hget(base, reg, dst):      # r dst = H[base + r reg]
    K(base); e(f'b=a a=r {reg} a+=b d=a a=*d r=a {dst}')
def hset(base, reg, src):      # H[base + r reg] = r src
    K(base); e(f'b=a a=r {reg} a+=b d=a a=r {src} *d=a')
def ltR(x, y): e(f'a=r {x} b=r {y} a<b')   # f = r x < r y
def gtR(x, y): e(f'a=r {x} b=r {y} a>b')

def table():                   # the token table into H[0..255], once per block
    e('a=0 d=a')
    for v in T:
        K(v); e('*d=a d++')

def huff_chunk():
    """mode 2 chunk at r P (after the mode byte): r CC symbols into M[r LP..]; r P after it"""
    K(256); e(f'b=a a=r {CC} a<b ifl'); err(); e('endif')
    okthen()
    e(f'a=r {P} a+= 136 b=r {N} a>b ifl'); err(); e('endif')
    e('endif')
    okthen()
    # lengths, counts, Kraft sum
    e(f'a=0 r=a {S}')
    e('do')
    e(f'  a=r {S} a<<= 1 r=a {T1} a=r {S} b=r {P} a+=b c=a a=*c r=a {T2} a&= 15 r=a {T3}')
    hset(LEN, T1, T3)
    e(f'  a=r {T2} a>>= 4 r=a {T3} a=r {T1} a++ r=a {T1}')
    hset(LEN, T1, T3)
    e(f'  a=r {S} a++ r=a {S} a< 128')
    e('while')
    e(f'a=0 r=a {S}')
    e('do')
    e(f'  a=0 r=a {T3}'); hset(CNT, S, T3)
    e(f'  a=r {S} a++ r=a {S} a< 16')
    e('while')
    e(f'a=0 r=a {KR} r=a {NSYM} r=a {S}')
    e('do')
    hget(LEN, S, LL)
    e(f'  a=r {LL} a> 11 ifl'); err(); e('  endif')
    e(f'  a=r {LL} a> 0 ifl')
    e(f'    a=r {LL} a< 12 ifl')
    hget(CNT, LL, T1); e(f'      a=r {T1} a++ r=a {T1}'); hset(CNT, LL, T1)
    e(f'      a= 11 b=r {LL} a-=b b=a a= 1 a<<=b b=r {KR} a+=b r=a {KR} a=r {NSYM} a++ r=a {NSYM}')
    e('    endif')
    e('  endif')
    e(f'  a=r {S} a++ r=a {S} a> 255')
    e('until')
    K(2048); e(f'b=a a=r {KR} a==b ifnotl'); err(); e('endif')
    e(f'a=r {NSYM} a< 2 ifl'); err(); e('endif')
    e('endif')
    okthen()
    # next codes: nxt[1] = 0, nxt[b+1] = (nxt[b] + cnt[b]) << 1
    e(f'a=0 r=a {CODE} a= 1 r=a {S}')
    e('do')
    hset(NXT, S, CODE)
    hget(CNT, S, T1)
    e(f'  a=r {CODE} b=r {T1} a+=b a<<= 1 r=a {CODE}')
    e(f'  a=r {S} a++ r=a {S} a< 12')
    e('while')
    # the decoding table: for each symbol, its reversed code at every 1 << len
    e(f'a=0 r=a {S}')
    e('do')
    hget(LEN, S, LL)
    e(f'  a=r {LL} a> 0 ifl')
    hget(NXT, LL, CODE); e(f'    a=r {CODE} a++ r=a {T1}'); hset(NXT, LL, T1)
    e(f'    a=0 r=a {RR} r=a {J}')
    e('    do')
    e(f'      a=r {CODE} b=r {J} a>>=b a&= 1 r=a {T1} a=r {RR} a<<= 1 b=r {T1} a+=b r=a {RR}')
    e(f'      a=r {J} a++ r=a {J} b=r {LL} a<b')
    e('    while')
    e(f'    a=r {LL} a<<= 8 b=r {S} a+=b r=a {EE}')
    e(f'    a=r {RR} r=a {I}')
    e('    do')
    hset(TAB, I, EE)
    e(f'      a= 1 b=r {LL} a<<=b b=r {I} a+=b r=a {I}')
    K(2048); e(f'      b=a a=r {I} a<b')
    e('    while')
    e('  endif')
    e(f'  a=r {S} a++ r=a {S} a> 255')
    e('until')
    # sizes and streams
    e(f'a=r {P} a+= 128 r=a {P}')
    for k in range(4):
        e(f'a=r {P} a+= {2 * k} r=a {T2}'); u16(T2, SZ + k)
    e(f'a=r {P} a+= 8 r=a {P}')
    e(f'a=r {SZ} b=r {SZ + 1} a+=b b=r {SZ + 2} a+=b b=r {SZ + 3} a+=b b=r {P} a+=b b=r {N} a>b ifl'); err(); e('endif')
    e('endif')
    okthen()
    e(f'a=r {CC} a+= 3 a>>= 2 r=a {Q}')
    for k in range(4):
        if k < 3:
            e(f'a=r {Q} r=a {NS}')
        else:
            e(f'a=r {Q} a<<= 1 b=r {Q} a+=b b=a a=r {CC} a-=b r=a {NS}')
        e(f'a=r {P} r=a {SP} b=r {SZ + k} a+=b r=a {SE}')
        e(f'a=0 r=a {BUF} r=a {NB} r=a {USED}')
        e(f'a=r {NS} a> 0 ifl')
        e('  do')
        e(f'    a=r {NB} a< 11 ifl')
        e('      do')
        e(f'        a=r {SP} b=r {SE} a<b ifl a=r {SP} c=a a=*c elsel a=0 endif')
        e(f'        b=r {NB} a<<=b b=r {BUF} a|=b r=a {BUF} a=r {SP} a++ r=a {SP} a=r {NB} a+= 8 r=a {NB}')
        e(f'        a< 11')
        e('      while')
        e('    endif')
        e(f'    a=r {BUF} a&= 255 r=a {T1} a=r {BUF} a>>= 8 a&= 7 a<<= 8 b=r {T1} a+=b r=a {T1}')
        hget(TAB, T1, EE)
        e(f'    a=r {EE} a&= 255 r=a {T2} a=r {LP} c=a a=r {T2} *c=a a=r {LP} a++ r=a {LP}')
        e(f'    a=r {EE} a>>= 8 r=a {LL} b=a a=r {BUF} a>>=b r=a {BUF} a=r {NB} a-=b r=a {NB} a=r {USED} a+=b r=a {USED}')
        e(f'    a=r {NS} a-- r=a {NS} a> 0')
        e('  while')
        e('endif')
        e(f'a=r {SZ + k} a<<= 3 b=a a=r {USED} a>b ifl'); err(); e('endif')
        e(f'a=r {SE} r=a {P}')
    e('endif')

def literals_v3():
    e(f'a=r {CE} r=a {P} a+= 4 b=r {N} a>b ifl'); err(); e('endif')
    okthen()
    u32(P, LC); e(f'a=r {P} a+= 4 r=a {P}')
    e(f'a=r {LC} a== 0 ifl'); err(); e('endif')
    gtR(LC, ORIG); e('ifl'); err(); e('endif')
    e('endif')
    okthen()
    e(f'a=r {N} a+= 32 r=a {LP} r=a {LS} a=r {LC} r=a {LEFT}')
    e('do')
    K(65536); e(f'b=a a=r {LEFT} a<b ifl a=r {LEFT} elsel a=b endif r=a {CC}')
    e(f'  a=r {P} b=r {N} a<b ifnotl'); err(); e('  endif')
    e(f'  a=r {ERR} a== 0 ifl')
    get(P, T1); e(f'    a=r {P} a++ r=a {P}')
    e(f'    a=r {T1} a== 0 ifl')
    e(f'      a=r {P} b=r {CC} a+=b b=r {N} a>b ifl'); err(); e('      elsel')
    e(f'        a=r {CC} r=a {T2}')
    e('        do')
    e(f'          a=r {P} c=a a=*c r=a {T3} a=r {LP} c=a a=r {T3} *c=a a=r {P} a++ r=a {P} a=r {LP} a++ r=a {LP}')
    e(f'          a=r {T2} a-- r=a {T2} a> 0')
    e('        while')
    e('      endif')
    e('    elsel a== 2 ifl')
    huff_chunk()
    e('    elsel')
    err()
    e('    endif endif')
    e(f'    a=r {LEFT} b=r {CC} a-=b r=a {LEFT}')
    e('  endif')
    e(f'  a=r {ERR} a== 0 ifl a=r {LEFT} a> 0 ifl a= 1 elsel a=0 endif elsel a=0 endif')
    e('a> 0 while')
    e(f'a=r {P} b=r {N} a==b ifnotl'); err(); e('endif')
    e(f'a=r {LS} b=r {LC} a+=b r=a {LE} r=a {OB}')
    e('endif')

def ext(dst):                  # r dst += 255-run bytes from the control stream
    e('do')
    e(f'  a=r {CP} b=r {CE} a<b ifnotl'); err(); e('  a=0 elsel')
    get(CP, T1); e(f'    a=r {CP} a++ r=a {CP} a=r {dst} b=r {T1} a+=b r=a {dst}')
    e(f'    a=r {T1} a== 255 ifl a= 1 elsel a=0 endif')
    e('  endif')
    e('a> 0 while')

def copy(srcreg, nreg):        # nreg bytes from M[srcreg] to the output; srcreg advances
    e(f'a=r {nreg} a> 0 ifl')
    e('  do')
    e(f'    a=r {srcreg} c=a a=*c r=a {T1} a=r {OB} b=r {OUTN} a+=b c=a a=r {T1} *c=a out')
    e(f'    a=r {srcreg} a++ r=a {srcreg} a=r {OUTN} a++ r=a {OUTN}')
    e(f'    a=r {nreg} a-- r=a {nreg} a> 0')
    e('  while')
    e('endif')

def sequences():
    e(f'a=0 r=a {OUTN}')
    e('do')
    e(f'  a=r {CP} b=r {CE} a<b ifl')
    e(f'    a=r {CP} a+= 3 b=r {CE} a>b ifl'); err(); e('    endif')
    e(f'    a=r {ERR} a== 0 ifl')
    get(CP, T1); hget(TOK, T1, EE)
    e(f'      a=r {CP} a++ r=a {T2}'); u16(T2, OFF); e(f'      a=r {OFF} a++ r=a {OFF} a=r {CP} a+= 3 r=a {CP}')
    e(f'      a=r {EE} a&= 255 r=a {LIT} a=r {EE} a>>= 8 a&= 255 r=a {ML}')
    e(f'      a=r {EE} a>>= 16 a&= 1 a> 0 ifl'); ext(LIT); e('      endif')
    e(f'      a=r {EE} a>>= 17 a&= 1 a> 0 ifl'); ext(ML); e('      endif')
    e('    endif')
    e(f'    a=r {ERR} a== 0 ifl')
    e(f'      a=r {LS} b=r {LIT} a+=b b=r {LE} a>b ifl'); err(); e('      endif')
    e(f'      a=r {OUTN} b=r {LIT} a+=b b=r {ORIG} a>b ifl'); err(); e('      endif')
    e('    endif')
    e(f'    a=r {ERR} a== 0 ifl')
    copy(LS, LIT)
    e(f'      a=r {OFF} b=r {OUTN} a>b ifl'); err(); e('      endif')
    e(f'      a=r {OUTN} b=r {ML} a+=b b=r {ORIG} a>b ifl'); err(); e('      endif')
    e('    endif')
    e(f'    a=r {ERR} a== 0 ifl')
    e(f'      a=r {OB} b=r {OUTN} a+=b b=r {OFF} a-=b r=a {T2}')
    copy(T2, ML)
    e('    endif')
    e(f'    a=r {ERR} a== 0 ifl a= 1 elsel a=0 endif')
    e('  elsel a=0 endif')
    e('a> 0 while')
    e(f'a=r {ERR} a== 0 ifl')
    e(f'  a=r {LE} b=r {LS} a-=b r=a {T2} a=r {ORIG} b=r {OUTN} a-=b b=r {T2} a==b ifl')
    copy(LS, T2)
    e('  endif')
    e('endif')

e('hcomp')
e('  halt')
e('pcomp zpaqsylz3 ;')
e('(ZPAQSYLZ3: sylz format v3 (syc v0.2.14, frozen) or v2, for zpaq-std -ma:sylzec.')
e(' zpaq-std, 2026. The segment into M; at its end: literals, then sequences.)')
e('a> 255 ifl')
e(f'  a=c r=a {N} a=0 r=a {ERR}')
e(f'  a=r {N} a< 8 ifl'); err(); e('  endif')
e(f'  a=r {ERR} a== 0 ifl')
table()
e(f'    a=0 r=a {T2}'); u32(T2, ORIG)
e(f'    a= 4 r=a {T2}'); u32(T2, T1)
e(f'    a=r {T1} a<<= 1 a>>= 1 r=a {CE} a+= 8 r=a {CE} a= 8 r=a {CP}')
e(f'    a=r {CE} b=r {N} a>b ifl'); err(); e('    endif')
e('  endif')
e(f'  a=r {ERR} a== 0 ifl')
e(f'    a=r {T1} a>>= 31 a> 0 ifl')
literals_v3()
e('    elsel')
e(f'      a=r {CE} r=a {LS} a=r {N} r=a {LE} a+= 32 r=a {OB}')
e('    endif')
e('  endif')
e(f'  a=r {ERR} a== 0 ifl')
sequences()
e('  endif')
e('  a=0 c=a')
e('elsel')
e('  *c=a c++')
e('endif')
e('halt')
e('end')

body = '\n'.join(out) + '\n'
if len(sys.argv) > 1 and sys.argv[1] == 'body':
    sys.stdout.write(body)
else:
    ph = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    pm = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    sys.stdout.write(f'comp 0 0 {ph} {pm} 0\n' + body)
