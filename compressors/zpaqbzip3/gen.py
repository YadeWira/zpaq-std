# Generador de ZPAQBZIP3: flujos de bzip3 (libbz3 1.5.4, niveles 1-9) en ZPAQL. ZPAQL no
# tiene subrutinas: todo son macros expandidas en linea. Mismo algoritmo que la referencia
# en Python con la que se probo.
#   python3 gen.py salida.txt
#
# Por bloque: el CM de bzip3 (C0 por contexto de bits, C1 por byte anterior, APM C2 con
# interpolacion; aritmetico de 32 bits), BWT inverso (convencion de libsais: el centinela
# en la fila del indice primario), LZP y el RLE de bzip3. La salida sale con out.
# M: la entrada desde 0; B1 = n + 16 y B2 = B1 + 2^20 + 2^17 (buffers de un bloque).
# H (ph = 21): C1 0 (65536), C0 65536, C2 65792 (512 x 17), tabla del RLE 74496,
# frecuencias 74752, cftab 75008, tabla de LZP 131072 (2^18), tt 524288 (el bloque).
# Registros:
#   r1 n, r2 p (entrada), r3 B1, r4 B2, r5 bloques que quedan, r6 fin del bloque,
#   r7 tamano comprimido, r8 tamano original, r9 bwt_idx, r10 model, r11 tamano lzp,
#   r12 tamano rle, r13 bytes para el CM, r14 entrada del CM, r15 fin de la entrada del CM
#   r16 high, r17 low, r18 code, r19 c1, r20 c2, r21 run, r22 f, r23 ctx, r24 p (prediccion),
#   r25 j, r26 x1, r27 x2, r28 ssep, r29 mid, r30 bit, r31 contador de bytes
#   r32..r39 temporales, r40..r49 bases en H
import sys
out = []
def e(s): out.append(s)
C1B, C0B, C2B, RLT, FTB, CFB, LUTB, TTB = 40, 41, 42, 43, 44, 45, 46, 47
BASES = {C1B: 0, C0B: 65536, C2B: 65792, RLT: 74496, FTB: 74752, CFB: 75008, LUTB: 131072, TTB: 524288}

def LOADK(v):
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def HGET(base, idx):
    e(f"a=r {idx} b=r {base} a+=b d=a a=*d")
def HSET(base, idx, val):
    e(f"a=r {idx} b=r {base} a+=b d=a a=r {val} *d=a")
def LE32(addr_reg, dst):      # r dst = LE32 en M[r addr]
    e(f"a=r {addr_reg} a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a {dst}")
def RDIN():                   # a = siguiente byte de la entrada del CM, o 0xFFFFFFFF pasado el fin
    e("a=r 14 b=r 15 a<b ifl c=a a=*c elsel a=0 a-- endif r=a 32 a=r 14 a++ r=a 14 a=r 32")
def UPD1(addr, k):            # H[d] += (H[d] ^ 65535) >> k   (d ya apunta)
    e(f"a=*d b=a a= 255 a<<= 8 a+= 255 a^=b a>>= {k} a+=b *d=a")
def UPD0(k):
    e(f"a=*d b=a a>>= {k} r=a 33 a=b b=r 33 a-=b *d=a")

e("hcomp")
e("halt")
e("pcomp zpaqbzip3 ;")
e("""(ZPAQBZIP3: decodificador de bzip3 en ZPAQL, para zpaq-std -ma:bzip3. zpaq-std, 2026.
 Guarda el flujo en M y lo decodifica al final, bloque por bloque: el CM de bzip3,
 el BWT inverso, LZP y RLE. La salida sale con out.)""")
e("a> 255 ifl")
e("  a=c r=a 1")
for reg, v in BASES.items(): LOADK(v); e(f"  r=a {reg}")
e("  a=r 1 a+= 16 r=a 3 a= 18 a<<= 16 b=r 3 a+=b r=a 4")        # B1, B2 = B1 + 1179648
e("  a= 9 r=a 32"); LE32(32, 5)                                   # numero de bloques
e("  a= 13 r=a 2")
e("  a=r 5 a> 0 ifl")
e("  do")
LE32(2, 7); e("    a=r 2 a+= 4 r=a 32"); LE32(32, 8)
e("    a=r 2 a+= 8 r=a 2 b=r 7 a+=b r=a 6")                        # p al bloque, r6 fin
e("    a=r 2 a+= 4 r=a 32"); LE32(32, 9)
e("    a=r 9 a++ a== 0 ifl")                                       # bloque crudo (idx = -1)
e("      a=r 2 a+= 8 r=a 32")
e("      a=r 32 b=r 6 a<b ifl")
e("        do")
e("          a=r 32 c=a a=*c out a=r 32 a++ r=a 32 b=r 6")
e("        a<b while")
e("      endif")
e("    elsel")
e("      a=r 2 a+= 8 c=a a=*c r=a 10 a=r 2 a+= 9 r=a 32")
e("      a=r 10 a&= 2 a> 0 ifl"); LE32(32, 11); e("        a=r 32 a+= 4 r=a 32 endif")
e("      a=r 10 a&= 4 a> 0 ifl"); LE32(32, 12); e("        a=r 32 a+= 4 r=a 32 endif")
e("      a=r 32 r=a 14 a=r 6 r=a 15")
e("      a=r 10 a&= 2 a> 0 ifl a=r 11 elsel a=r 10 a&= 4 a> 0 ifl a=r 12 elsel a=r 8 endif endif r=a 13")
# ---- CM: tablas iniciales
e("      a=0 r=a 32 a= 128 a<<= 8 r=a 33")
e("      do"); HSET(C1B, 32, 33); e("        a=r 32 a++ r=a 32 a>>= 16")      # 65536 entradas
e("      a== 0 while")
e("      a=0 r=a 32")
e("      do"); HSET(C0B, 32, 33); e("        a=r 32 a++ r=a 32")
e("      a> 255 until")
e("      a=0 r=a 32")                                    # C2[i][k] = (k << 12) - (k == 16)
e("      do")
e("        a=0 r=a 34")
e("        do")
e("          a=r 34 a<<= 12 r=a 35 a=r 34 a== 16 ifl a=r 35 a-- r=a 35 endif")
e("          a=r 32 a*= 17 b=r 34 a+=b b=r 42 a+=b d=a a=r 35 *d=a")
e("          a=r 34 a++ r=a 34")
e("        a< 17 while")
e("        a=r 32 a++ r=a 32 a>>= 9")                                        # 512 filas
e("      a== 0 while")
# ---- CM: decodificacion, r13 bytes al tt (byte en los 8 bits de abajo)
e("      a=0 r=a 16 a-- r=a 16 a=0 r=a 17 r=a 18 r=a 19 r=a 20 r=a 21 r=a 31")
for _ in range(4):
    RDIN(); e("      b=a a=r 18 a<<= 8 a+=b r=a 18")
e("      a=r 13 a> 0 ifl")
e("      do")
e("        a=r 19 b=r 20 a==b ifl a=r 21 a++ elsel a=0 endif r=a 21")
e("        a> 2 ifl a= 1 elsel a=0 endif r=a 22 a= 1 r=a 23")
e("        do")
HGET(C0B, 23); e("          r=a 32")
e("          a=r 19 a<<= 8 b=r 23 a+=b d=a a=*d r=a 33 a=r 20 a<<= 8 b=r 23 a+=b d=a a=*d r=a 34")
e("          a=r 32 b=r 33 a+=b a*= 7 b=r 34 a+=b a+=b a>>= 4 r=a 24")          # p
e("          a>>= 12 r=a 25")                                                    # j
e("          a=r 23 a+=a b=r 22 a+=b a*= 17 b=r 25 a+=b b=r 42 a+=b r=a 35")    # &C2[2ctx+f][j]
e("          d=a a=*d r=a 26 d++ a=*d r=a 27")
e("          a=r 24 a<<= 20 a>>= 20 r=a 36")                                 # p & 4095
e("          a=r 27 b=r 26 a<b ifl")                    # x2 < x1: el >> de C es aritmetico (piso)
e("            a=r 26 b=r 27 a-=b b=r 36 a*=b a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 255 a+= 15 a>>= 12 b=a a=r 26 a-=b")
e("          elsel")
e("            a=r 27 b=r 26 a-=b b=r 36 a*=b a>>= 12 b=r 26 a+=b")
e("          endif")
e("          r=a 28 a+=a b=r 28 a+=b b=r 24 a+=b r=a 37")      # w = 3 ssep + p (< 2^18)
# mid = low + ((high - low) * w) >> 18, sin pasar de 32 bits: R = a*2^18 + b1*2^9 + b0
e("          a=r 16 b=r 17 a-=b r=a 38 a>>= 18 b=r 37 a*=b r=a 29")
e("          a=r 38 a<<= 14 a>>= 23 b=r 37 a*=b r=a 39")                      # b1 * w
e("          a=r 38 a&= 255 r=a 32 a=r 38 a>>= 8 a&= 1 a<<= 8 b=r 32 a+=b b=r 37 a*=b a>>= 9 b=r 39 a+=b a>>= 9")
e("          b=r 29 a+=b b=r 17 a+=b r=a 29")
e("          a=r 18 b=r 29 a>b ifl a=0 elsel a= 1 endif r=a 30")      # bit = code <= mid
e("          a> 0 ifl a=r 29 r=a 16 elsel a=r 29 a++ r=a 17 endif")
e("          do")
e("            a=r 17 b=r 16 a^=b a>>= 24 a== 0 ifl")
e("              a=r 17 a<<= 8 r=a 17 a=r 16 a<<= 8 a+= 255 r=a 16")
RDIN(); e("              b=a a=r 18 a<<= 8 a+=b r=a 18 a= 1")
e("            elsel a=0 endif")
e("          a> 0 while")
e("          a=r 30 a> 0 ifl")
HGET(C0B, 23); UPD1(None, 2)
e("            a=r 19 a<<= 8 b=r 23 a+=b d=a"); UPD1(None, 4)
e("            a=r 35 d=a"); UPD1(None, 6); e("            d++"); UPD1(None, 6)
e("            a=r 23 a+=a a++ r=a 23")
e("          elsel")
HGET(C0B, 23); UPD0(2)
e("            a=r 19 a<<= 8 b=r 23 a+=b d=a"); UPD0(4)
e("            a=r 35 d=a"); UPD0(6); e("            d++"); UPD0(6)
e("            a=r 23 a+=a r=a 23")
e("          endif")
e("          a=r 23")
e("        a> 255 until")
e("        a=r 19 r=a 20 a=r 23 a&= 255 r=a 19")
e("        a=r 31 b=r 47 a+=b d=a a=r 19 *d=a a=r 31 a++ r=a 31 b=r 13")
e("      a<b while")
e("      endif")
# ---- BWT inverso: filas 0..n, el centinela en la fila bwt_idx (r9); salida a B1 de atras hacia adelante
e("      a=0 r=a 32 r=a 33")
e("      do"); HSET(FTB, 32, 33); e("        a=r 32 a++ r=a 32")
e("      a> 255 until")
e("      a=0 r=a 32")
e("      a=r 13 a> 0 ifl")
e("      do"); HGET(TTB, 32); e("        a&= 255 r=a 34"); HGET(FTB, 34); e("        a++ r=a 35"); HSET(FTB, 34, 35)
e("        a=r 32 a++ r=a 32 b=r 13")
e("      a<b while")
e("      endif")
e("      a=0 r=a 32 a= 1 r=a 33")                       # C[c] desde 1 (la fila 0 es el centinela)
e("      do"); HSET(CFB, 32, 33); HGET(FTB, 32); e("        b=r 33 a+=b r=a 33 a=r 32 a++ r=a 32")
e("      a> 255 until")
e("      a=0 r=a 32")                                   # j (indice en L)
e("      a=r 13 a> 0 ifl")
e("      do")
HGET(TTB, 32); e("        a&= 255 r=a 34"); HGET(CFB, 34); e("        r=a 35 a++ r=a 36"); HSET(CFB, 34, 36)
e("        a=r 35 a<<= 8 b=r 34 a+=b r=a 35"); HSET(TTB, 32, 35)
e("        a=r 32 a++ r=a 32 b=r 13")
e("      a<b while")
e("      a=0 r=a 33 a=r 13 r=a 32")                     # r33 fila; r32 = k (de n hacia 0)
e("      do")
e("        a=r 32 a-- r=a 32")
e("        a=r 33 b=r 9 a<b ifnot a-- endif r=a 34")    # j = fila < idx ? fila : fila - 1
HGET(TTB, 34); e("        r=a 35 a&= 255 r=a 36 a=r 32 b=r 3 a+=b c=a a=r 36 *c=a a=r 35 a>>= 8 r=a 33")
e("        a=r 32")
e("      a> 0 while")
e("      endif")
# ---- LZP (B1 -> B2) si model & 2
e("      a=r 3 r=a 36 a=r 13 r=a 37")                   # r36 datos actuales, r37 su largo
e("      a=r 10 a&= 2 a> 0 ifl")
e("        a=0 r=a 32 r=a 33 a= 4 a<<= 16 r=a 34")
e("        do"); HSET(LUTB, 32, 33); e("          a=r 32 a++ r=a 32 b=r 34")
e("        a<b while")
e("        a=r 10 a&= 4 a> 0 ifl a=r 12 elsel a=r 8 endif r=a 38")   # maximo de salida
e("        a=r 3 c=a a=*c r=a 32 c++ a=*c r=a 33 c++ a=*c r=a 34 c++ a=*c r=a 35")
e("        a=r 4 c=a a=r 32 *c=a c++ a=r 33 *c=a c++ a=r 34 *c=a c++ a=r 35 *c=a")
e("        a=r 32 a<<= 8 b=r 33 a+=b a<<= 8 b=r 34 a+=b a<<= 8 b=r 35 a+=b r=a 39")   # ctx
e("        a=r 3 a+= 4 r=a 32 b=r 3 a=r 13 a+=b r=a 33 a=r 4 a+= 4 r=a 34")      # r32 in, r33 fin, r34 out
e("        a=r 38 b=r 4 a+=b r=a 38")                     # r38 fin de salida (absoluto)
e("        do")
e("          a=r 32 b=r 33 a<b ifl a=r 34 b=r 38 a<b ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("          a> 0 ifl")
e("            a=r 39 a>>= 15 r=a 35 a=r 39 a>>= 3 b=r 35 a^=b b=r 39 a^=b a<<= 14 a>>= 14 r=a 35")   # hash de 18 bits
HGET(LUTB, 35); e("            r=a 36 a=r 34 b=r 4 a-=b r=a 37"); HSET(LUTB, 35, 37)
e("            a=r 32 c=a a=*c a== 242 ifl a=r 36 a> 0 ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("            a> 0 ifl")
e("              a=r 32 a++ r=a 32 c=a a=*c a== 255 ifnotl")
e("                a= 40 r=a 35")
e("                do")
e("                  a=r 32 c=a a=*c r=a 37 b=r 35 a+=b r=a 35 a=r 32 a++ r=a 32 a=r 37 a== 254")
e("                while")
e("                a=r 36 b=r 4 a+=b r=a 36")                                   # ref
e("                do")
e("                  a=r 34 b=r 38 a<b ifl a=r 35 a> 0 ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("                  a> 0 ifl a=r 36 c=a a=*c c=r 34 *c=a a=c a++ r=a 34 a=r 36 a++ r=a 36 a=r 35 a-- r=a 35 a= 1 endif")
e("                a> 0 while")
e("              elsel")
e("                a=r 32 a++ r=a 32 a=r 34 c=a a= 242 *c=a a=c a++ r=a 34")
e("              endif")
e("              a=r 34 a-- c=a a=*c r=a 39 c-- a=*c a<<= 8 b=r 39 a+=b r=a 39 c-- a=*c a<<= 16 b=r 39 a+=b r=a 39 c-- a=*c a<<= 24 b=r 39 a+=b r=a 39")
e("            elsel")
e("              a=r 32 c=a a=*c c=r 34 *c=a r=a 37 a=c a++ r=a 34 a=r 32 a++ r=a 32 a=r 39 a<<= 8 b=r 37 a+=b r=a 39")
e("            endif")
e("            a= 1")
e("          endif")
e("        a> 0 while")
e("        a=r 4 r=a 36 a=r 34 b=r 4 a-=b r=a 37")
e("      endif")
# ---- RLE (r36 datos, r37 largo) -> out, si model & 4; si no, out directo
e("      a=r 10 a&= 4 a> 0 ifl")
e("        a=0 r=a 32")
e("        do")
e("          a=r 32 a>>= 3 b=r 36 a+=b c=a a=r 32 a&= 7 b=a a=*c a>>=b a&= 1 r=a 33"); HSET(RLT, 32, 33)
e("          a=r 32 a++ r=a 32")
e("        a> 255 until")
e("        a=r 36 a+= 32 r=a 32 b=r 37 a=r 36 a+=b r=a 33 a=0 r=a 34")   # r32 in, r33 fin, r34 salida
e("        do")
e("          a=r 34 b=r 8 a<b ifl a=r 32 b=r 33 a<b ifl a= 1 elsel a=0 endif elsel a=0 endif")
e("          a> 0 ifl")
e("            a=r 32 c=a a=*c r=a 35 a=r 32 a++ r=a 32"); HGET(RLT, 35)
e("            a> 0 ifl")
e("              a=0 r=a 38")
e("              do")
e("                a=r 32 b=r 33 a<b ifl a=r 32 c=a a=*c r=a 39 a=r 32 a++ r=a 32 a=r 39 a== 255 ifl a=r 38 a+= 255 r=a 38 a= 1 elsel a=0 endif elsel a=0 r=a 39 endif")
e("              a> 0 while")
e("              a=r 38 b=r 39 a+=b a++ r=a 38")
e("              do")
e("                a=r 38 a> 0 ifl a=r 34 b=r 8 a<b ifl a=r 35 out a=r 34 a++ r=a 34 a=r 38 a-- r=a 38 a= 1 elsel a=0 endif elsel a=0 endif")
e("              a> 0 while")
e("            elsel")
e("              a=r 35 out a=r 34 a++ r=a 34")
e("            endif")
e("            a= 1")
e("          endif")
e("        a> 0 while")
e("      elsel")
e("        a=r 37 a> 0 ifl")
e("          do")
e("            a=r 36 c=a a=*c out a=r 36 a++ r=a 36 a=r 37 a-- r=a 37")
e("          a> 0 while")
e("        endif")
e("      endif")
e("    endif")
e("    a=r 6 r=a 2 a=r 5 a-- r=a 5")
e("  a> 0 while")
e("  endif")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
