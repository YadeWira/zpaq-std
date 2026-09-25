# Generador de ZPAQLZFSE: flujos de lzfse (Apple lzfse 1.0) en ZPAQL. ZPAQL no tiene
# subrutinas: todo son macros expandidas en linea. Mismo algoritmo que la referencia en
# Python con la que se probo.
#   python3 gen.py salida.txt
#
# M: la entrada desde 0; los literales de un bloque en LB = n + 64 (hasta 40000); la
# salida en OB = n + 65600 (hace falta entera: las copias miran hacia atras).
# H (ph = 13): tabla de literales 0 (simbolo) 1024 (bits) 2048 (delta); L 3072 (base)
# 3136 (bits de estado) 3200 (bits de valor) 3264 (delta); M 3328 3392 3456 3520;
# D 3584 3840 4096 4352; frecuencias 4608 (360); constantes: L_bits 5120, L_base 5140,
# M_bits 5160, M_base 5180, D_bits 5200, D_base 5264, codificacion de las frecuencias
# 5328 (bits) y 5360 (valor).
# Registros:
#   r1 n, r2 p, r3 OB, r4 salida, r5 LB, r6 literal, r7 hay bloques, r8 magic, r9 n_raw,
#   r10 n_literals, r11 n_literal_payload, r12 n_matches, r13..r16 estados de literales,
#   r17 n_lmd_payload, r18 lmd_bits+7, r19 header_size, r20..r22 estados L M D, r23 D,
#   r24..r31 temporales, r32 literal_bits+7, r33 fin del bloque lzvn, r35..r37 L M D nuevos,
#   r40 POS y r41 BASE (lector hacia atras), r50 bit, r51 fin y r52 base (hacia adelante),
#   r60 valor leido, r66 r67 r69 temporales, r70..r93 bases en H
import sys
out = []
def e(s): out.append(s)
BASES = dict(LTS=0, LTK=1024, LTD=2048, LB_=3072, LK=3136, LV=3200, LD=3264,
             MB=3328, MK=3392, MV=3456, MD=3520, DB=3584, DK=3840, DV=4096, DD=4352,
             FQ=4608, LBI=5120, LBA=5140, MBI=5160, MBA=5180, DBI=5200, DBA=5264, FNB=5328, FVA=5360)
REG = {k: 70 + i for i, k in enumerate(BASES)}
R = lambda k: REG[k]

L_BITS = [0]*16 + [2,3,5,8];  L_BASE = list(range(16)) + [16,20,28,60]
M_BITS = [0]*16 + [3,5,8,11]; M_BASE = list(range(16)) + [16,24,56,312]
D_BITS = [i//4 for i in range(64)]
D_BASE = [0,1,2,3,4,6,8,10,12,16,20,24,28,36,44,52,60,76,92,108,124,156,188,220,252,316,380,444,508,636,764,892,
          1020,1276,1532,1788,2044,2556,3068,3580,4092,5116,6140,7164,8188,10236,12284,14332,16380,20476,24572,28668,
          32764,40956,49148,57340,65532,81916,98300,114684,131068,163836,196604,229372]
FNBT = [2,3,2,5,2,3,2,8,2,3,2,5,2,3,2,14]*2
FVAL = [0,2,1,4,0,3,1,0,0,2,1,5,0,3,1,0,0,2,1,6,0,3,1,0,0,2,1,7,0,3,1,0]
MAGIC_END, MAGIC_RAW, MAGIC_V2, MAGIC_LZVN = 0x24787662, 0x2d787662, 0x32787662, 0x6e787662

def LOADK(v):                 # a = v (los inmediatos de ZPAQL van de 0 a 255)
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def TABLE(k, vals):
    e(f"a=r {R(k)} d=a")
    for v in vals:
        LOADK(v); e("*d=a d++")
def HGET(base, idx):          # base: nombre de tabla; idx: registro
    e(f"a=r {idx} b=r {R(base)} a+=b d=a a=*d")
def HSET(base, idx, val):
    e(f"a=r {idx} b=r {R(base)} a+=b d=a a=r {val} *d=a")
def PUT():                    # escribe a en la salida (M y OUT)
    e("c=r 4 *c=a out a=c a++ r=a 4")
def RD8(off):                 # a = M[p + off]
    e(f"a=r 2 a+= {off} c=a a=*c")
def LE32(off, dst):
    e(f"a=r 2 a+= {off+3} c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {dst}")
def HIGHBIT(src, dst):
    e(f"a=0 r=a {dst} a=r {src} a>>= 1")
    e("a> 0 ifl")
    e("  do")
    e(f"    r=a 69 a=r {dst} a++ r=a {dst} a=r 69 a>>= 1")
    e("  a> 0 while")
    e("endif")
def READB(nreg, dst):         # r dst = r nreg bits hacia atras, el primero es el mas alto
    e(f"a=0 r=a {dst} a=r {nreg} r=a 67")
    e("a> 0 ifl")
    e("  do")
    e("    a=r 40 a-- r=a 40 a>>= 3 b=r 41 a+=b c=a a=r 40 a&= 7 b=a a=*c a>>=b a&= 1")
    e(f"    b=a a=r {dst} a<<= 1 a+=b r=a {dst}")
    e("    a=r 67 a-- r=a 67")
    e("  a> 0 while")
    e("endif")
def FPEEK(n):                 # r60 = n bits LSB primero desde el bit r50 de M[r52..r51)
    e("a=0 r=a 60 r=a 66")
    e("do")
    e("  a=r 50 b=r 66 a+=b r=a 67 a>>= 3 b=r 52 a+=b b=r 51 a<b ifl")
    e("    c=a a=r 67 a&= 7 b=a a=*c a>>=b a&= 1 b=r 66 a<<=b b=r 60 a|=b r=a 60")
    e("  endif")
    e("  a=r 66 a++ r=a 66")
    e(f"a< {n} while")
def FIELD(bit0, nb, dst):     # campo empaquetado del encabezado v2
    e(f"a= {bit0} r=a 50"); FPEEK(nb); e(f"a=r 60 r=a {dst}")

def BUILD(N_log, nsym, foff, tsym, tk, td, tv=None, vbits=None, vbase=None):
    """fse_init_decoder_table (tv None) o fse_init_value_decoder_table: estados
    contiguos por simbolo, k = log2(N) - log2(f), j0 = 2N/2^k - f."""
    e("a=0 r=a 24 r=a 25")                           # r24 simbolo, r25 estado a llenar
    e("do")
    e(f"  a=r 24 a+= {foff} b=r {R('FQ')} a+=b d=a a=*d r=a 26")    # f
    e("  a> 0 ifl")
    HIGHBIT(26, 27); e(f"    a= {N_log} b=r 27 a-=b r=a 27")     # k
    e(f"    a= 2 a<<= {N_log} b=r 27 a>>=b b=r 26 a-=b r=a 28")        # j0
    e("    a=0 r=a 29")                                                 # j
    e("    do")
    e("      a=r 29 b=r 28 a<b ifl")
    e(f"        a=r 27 r=a 30 a=r 26 b=r 29 a+=b b=r 27 a<<=b b=a a= 1 a<<= {N_log} r=a 31 a=b b=r 31 a-=b r=a 31")
    e("      elsel")
    e("        a=r 27 a-- r=a 30 a=r 29 b=r 28 a-=b b=r 30 a<<=b r=a 31")
    e("      endif")
    if tv is None:
        HSET(tsym, 25, 24)
    else:
        HGET(vbase, 24); e("      r=a 69"); HSET(tsym, 25, 69)
        HGET(vbits, 24); e("      r=a 69"); HSET(tv, 25, 69)
    HSET(tk, 25, 30); HSET(td, 25, 31)
    e("      a=r 25 a++ r=a 25 a=r 29 a++ r=a 29 b=r 26")
    e("    a<b while")
    e("  endif")
    e("  a=r 24 a++ r=a 24")
    e(f"a< {nsym} while" if nsym < 256 else "a> 255 until")

def VDECODE(tb, tk, tv, td, st, dst):
    """fse_value_decode: lee de una vez los bits de estado y los de valor."""
    HGET(tk, st); e("r=a 26"); HGET(tv, st); e("r=a 27 b=r 26 a+=b r=a 28")
    READB(28, 29)
    e("a= 1 b=r 27 a<<=b a-- b=r 29 a&=b r=a 30"); HGET(tb, st); e(f"b=r 30 a+=b r=a {dst}")
    e("a=r 29 b=r 27 a>>=b r=a 30"); HGET(td, st); e(f"b=r 30 a+=b r=a {st}")

def COPYLIT(cnt, src):        # r cnt bytes desde M[r src] a la salida
    e(f"a=r {cnt} a> 0 ifl")
    e("  do")
    e(f"    a=r {src} c=a a=*c"); PUT(); e(f"    a=r {src} a++ r=a {src} a=r {cnt} a-- r=a {cnt}")
    e("  a> 0 while")
    e("endif")
def COPYMATCH(cnt):           # r cnt bytes desde la salida - D (r23)
    e(f"a=r {cnt} a> 0 ifl")
    e("  a=r 4 b=r 23 a-=b r=a 30")
    e("  do")
    e("    a=r 30 c=a a=*c"); PUT(); e(f"    a=r 30 a++ r=a 30 a=r {cnt} a-- r=a {cnt}")
    e("  a> 0 while")
    e("endif")

e("hcomp")
e("halt")
e("pcomp zpaqlzfse ;")
e("""(ZPAQLZFSE: decodificador de lzfse en ZPAQL, para zpaq-std -ma:lzfse. zpaq-std, 2026.
 Guarda el flujo entero en M y lo decodifica al final: bloques bvx2 - FSE, literales
 con cuatro estados y L M D con decodificadores de valor -, bvxn - LZVN -, bvx- y bvx$.
 La salida queda en M, detras, y sale con out.)""")
e("a> 255 ifl")
e("  a=c r=a 1")
for k, v in BASES.items():
    LOADK(v); e(f"r=a {R(k)}")
TABLE('LBI', L_BITS); TABLE('LBA', L_BASE); TABLE('MBI', M_BITS); TABLE('MBA', M_BASE)
TABLE('DBI', D_BITS); TABLE('DBA', D_BASE); TABLE('FNB', FNBT); TABLE('FVA', FVAL)
e("  a=r 1 a+= 64 r=a 5 a= 1 a<<= 16 a+= 64 b=r 1 a+=b r=a 3 r=a 4")   # LB, OB
e("  a=0 r=a 2 a= 1 r=a 7")
e("  do")
e("  a=r 2 a+= 4 b=r 1 a>b ifl a=0 r=a 7 endif")
e("  a=r 7 a> 0 ifl")
LE32(0, 8)
LOADK(MAGIC_END); e("    b=a a=r 8 a==b ifl")
e("      a=0 r=a 7")
e("    elsel")
LE32(4, 9)
LOADK(MAGIC_RAW); e("    b=a a=r 8 a==b ifl")                      # bvx-: crudo
e("      a=r 2 a+= 8 r=a 24"); COPYLIT(9, 24); e("      a=r 24 r=a 2")
e("    elsel")
LOADK(MAGIC_LZVN); e("    b=a a=r 8 a==b ifl")                     # bvxn: LZVN
LE32(8, 33); e("      a=r 2 a+= 12 r=a 2 b=r 33 a+=b r=a 33 a=0 r=a 23")
e("      do")
e("      a=r 2 b=r 33 a<b ifl")
RD8(0); e("        r=a 24 a=0 r=a 25 r=a 26 r=a 27")          # r25 L, r26 M, r27 hay D nuevo
e("        a=r 24 a== 6 ifl")                                  # eos
e("          a=r 33 r=a 2")
e("        elsel")
e("        a=r 24 a== 14 ifl a=r 2 a++ r=a 2 elsel a=r 24 a== 22 ifl a=r 2 a++ r=a 2 elsel")   # nop
e("        a=r 24 a> 239 ifl")                                 # solo match, D previa
e("          a== 240 ifl"); RD8(1); e("            a+= 16 r=a 26 a=r 2 a+= 2 r=a 2")
e("          elsel a&= 15 r=a 26 a=r 2 a++ r=a 2 endif")
e("        elsel")
e("        a=r 24 a> 223 ifl")                                 # solo literal
e("          a== 224 ifl"); RD8(1); e("            a+= 16 r=a 25 a=r 2 a+= 2 r=a 2")
e("          elsel a&= 15 r=a 25 a=r 2 a++ r=a 2 endif")
e("        elsel")
e("        a=r 24 a> 159 ifl a< 192 ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("        a> 0 ifl")                                          # med_d: 101LLMMM DDDDDDMM DDDDDDDD
e("          a=r 24 a>>= 3 a&= 3 r=a 25")
e("          a=r 2 a+= 2 c=a a=*c a<<= 8 c-- a+=*c r=a 28")
e("          a=r 24 a&= 7 a<<= 2 r=a 26 a=r 28 a&= 3 b=r 26 a+=b a+= 3 r=a 26")
e("          a=r 28 a>>= 2 r=a 28 a= 1 r=a 27 a=r 2 a+= 3 r=a 2")
e("        elsel")
e("          a=r 24 a>>= 6 r=a 25 a=r 24 a>>= 3 a&= 7 a+= 3 r=a 26")
e("          a=r 24 a&= 7 a== 7 ifl")                           # lrg_d: LLMMM111 + D de 16 bits
e("            a=r 2 a+= 2 c=a a=*c a<<= 8 c-- a+=*c r=a 28 a= 1 r=a 27 a=r 2 a+= 3 r=a 2")
e("          elsel a== 6 ifl")                                 # pre_d: LLMMM110, D previa
e("            a=r 2 a++ r=a 2")
e("          elsel")                                           # sml_d: LLMMMDDD DDDDDDDD
e("            a=r 24 a&= 7 a<<= 8 r=a 28"); RD8(1); e("            b=r 28 a+=b r=a 28 a= 1 r=a 27 a=r 2 a+= 2 r=a 2")
e("          endif endif")
e("        endif")
e("        endif")
e("        endif")
COPYLIT(25, 2)
e("        a=r 27 a> 0 ifl a=r 28 r=a 23 endif")
COPYMATCH(26)
e("        endif endif")
e("        endif")
e("      endif")
e("      a=r 2 b=r 33")
e("      a<b while")
e("      a=r 33 r=a 2")
e("    elsel")                                                  # bvx2: FSE
e("      a=r 2 a+= 8 r=a 52 a+= 24 r=a 51")
FIELD(0, 20, 10); FIELD(20, 20, 11); FIELD(40, 20, 12); FIELD(60, 3, 32)
FIELD(64, 10, 13); FIELD(74, 10, 14); FIELD(84, 10, 15); FIELD(94, 10, 16)
FIELD(104, 20, 17); FIELD(124, 3, 18); FIELD(128, 32, 19)
FIELD(160, 10, 20); FIELD(170, 10, 21); FIELD(180, 10, 22)
# frecuencias: 360 valores con la codificacion fija de lzfse
e("      a=r 2 a+= 32 r=a 52 a=r 2 b=r 19 a+=b r=a 51 a=0 r=a 50 r=a 25")
LOADK(360); e("      r=a 24")
e("      do")
FPEEK(14)
e("        a=r 60 a&= 31 r=a 27"); HGET('FNB', 27); e("        r=a 26")
e("        a== 8 ifl")
e("          a=r 60 a>>= 4 a&= 15 a+= 8")
e("        elsel a== 14 ifl")
e("          a=r 60 a>>= 4 a&= 255 r=a 28 a=r 60 a>>= 12 a&= 3 a<<= 8 b=r 28 a+=b a+= 24")
e("        elsel"); HGET('FVA', 27)
e("        endif endif")
e("        r=a 28"); HSET('FQ', 25, 28)
e("        a=r 50 b=r 26 a+=b r=a 50 a=r 25 a++ r=a 25 a=r 24 a-- r=a 24")
e("      a> 0 while")
BUILD(6, 20, 0, 'LB_', 'LK', 'LD', 'LV', 'LBI', 'LBA')
BUILD(6, 20, 20, 'MB', 'MK', 'MD', 'MV', 'MBI', 'MBA')
BUILD(8, 64, 40, 'DB', 'DK', 'DD', 'DV', 'DBI', 'DBA')
BUILD(10, 256, 104, 'LTS', 'LTK', 'LTD')
# literales: cuatro estados, desde el final del payload de literales
e("      a=r 2 b=r 19 a+=b r=a 2 r=a 41 a=r 11 a<<= 3 b=r 32 a+=b a-= 7 r=a 40")
e("      a=r 5 r=a 6 a=r 10 r=a 25")
e("      a> 0 ifl")
e("      do")
for st in (13, 14, 15, 16):
    HGET('LTS', st); e("        c=r 6 *c=a a=c a++ r=a 6")
    HGET('LTK', st); e("        r=a 26"); READB(26, 27); HGET('LTD', st); e(f"        b=r 27 a+=b r=a {st}")
e("        a=r 25 a-= 4 r=a 25")
e("      a> 0 while")
e("      endif")
# L, M, D
e("      a=r 2 b=r 11 a+=b r=a 41 a=r 17 a<<= 3 b=r 18 a+=b a-= 7 r=a 40")
e("      a=r 5 r=a 6 a=0 r=a 23 a=r 12 r=a 25")
e("      a> 0 ifl")
e("      do")
VDECODE('LB_', 'LK', 'LV', 'LD', 20, 35)
VDECODE('MB', 'MK', 'MV', 'MD', 21, 36)
VDECODE('DB', 'DK', 'DV', 'DD', 22, 37)
e("        a=r 37 a> 0 ifl r=a 23 endif")
COPYLIT(35, 6)
COPYMATCH(36)
e("        a=r 25 a-- r=a 25")
e("      a> 0 while")
e("      endif")
e("      a=r 2 b=r 11 a+=b b=r 17 a+=b r=a 2")
e("    endif")
e("    endif")
e("    endif")
e("  endif")
e("  a=r 7")
e("  a> 0 while")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
