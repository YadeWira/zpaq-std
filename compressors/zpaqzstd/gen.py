# Generador de ZPAQZSTD: flujos de zstd (RFC 8878; zstd 1.5.7, niveles 1-22) en ZPAQL.
# ZPAQL no tiene subrutinas: todo son macros expandidas en linea. El Huff0 de los
# literales y el FSE (lectura de NCount y armado de tablas) son los de ZPAQLIZARDH
# (../zpaqlizard/huff0.py). Mismo algoritmo que la referencia en Python con la que se probo.
#   python3 gen.py salida.txt
#
# M: la entrada (el frame de zstd) desde 0; los literales de un bloque en LB = n;
# la salida en OB = n + 131136 (hace falta entera: las copias miran hacia atras).
# H (ph = 13): lo de huff0 hasta 1303 (pesos, simbolos, tablas canonicas, NCount,
# tabla FSE de los pesos); tablas FSE de las secuencias: LL 1536/2048/2560,
# ML 3072/3584/4096, OF 4608/4864/5120 (simbolo, nbBits, newState); constantes:
# LL_base 5376, LL_bits 5440, ML_base 5504, ML_bits 5568, normas por defecto LL 5632,
# ML 5696, OF 5760; parametros de las tres tablas 5824 (8 por tabla).
# Registros propios (huff0 usa r34-r95):
#   r1 n, r2 p, r3 OB, r4 salida, r6 literal leido, r7 fin de literales, r8 ultimo bloque,
#   r9 tipo, r10 tamano, r11 fin del bloque, r12 hay frame, r13 descriptor, r14 tipo de
#   literales, r15 formato, r16 regenerado, r17 comprimido, r18 secuencias, r19 modos,
#   r20 quedan, r21 ll, r22 ml, r23 offset, r24..r31 temporales
#   r100..r102 offsets repetidos, r103..r105 tableLog LL/OF/ML, r106..r108 estados
#   LL/OF/ML, r109 tabla (0 LL, 1 OF, 2 ML), r110..r125 bases en H, r126 LB
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'zpaqlizard'))
import huff0
from huff0 import HGET, HSET, READB, INITB

out = []
def e(s): out.append(s)
LLS, LLN, LLX, MLS, MLN, MLX, OFS, OFN, OFX = 110, 111, 112, 113, 114, 115, 116, 117, 118
LLB, LLE, MLB, MLE, LLD, MLD, OFD, PAR = 119, 120, 121, 122, 123, 124, 125, 127

LL_BITS = [0]*16 + [1,1,1,1,2,2,3,3,4,6,7,8,9,10,11,12,13,14,15,16]
LL_BASE = list(range(16)) + [16,18,20,22,24,28,32,40,48,64,0x80,0x100,0x200,0x400,0x800,0x1000,0x2000,0x4000,0x8000,0x10000]
ML_BITS = [0]*32 + [1,1,1,1,2,2,3,3,4,4,5,7,8,9,10,11,12,13,14,15,16]
ML_BASE = list(range(3,35)) + [35,37,39,41,43,47,51,59,67,83,99,0x83,0x103,0x203,0x403,0x803,0x1003,0x2003,0x4003,0x8003,0x10003]
LL_DEF = [4,3,2,2,2,2,2,2,2,2,2,2,2,1,1,1,2,2,2,2,2,2,2,2,2,3,2,1,1,1,1,1,-1,-1,-1,-1]
ML_DEF = [1,4,3,2,2,2,2,2,2]+[1]*37+[-1]*7
OF_DEF = [1,1,1,1,1,1,2,2,2]+[1]*15+[-1]*5

def LOADK(v):                 # a = v (los inmediatos de ZPAQL van de 0 a 255)
    if v < 256: e(f"a= {v}"); return
    bs = []
    while v: bs.append(v & 255); v >>= 8
    e(f"a= {bs[-1]}")
    for b in reversed(bs[:-1]):
        e(f"a<<= 8 a+= {b}" if b else "a<<= 8")
def RDM():                    # a = M[r2], p++
    e("a=r 2 c=a a=*c r=a 24 a=r 2 a++ r=a 2 a=r 24")
def PUT():                    # escribe a en la salida (M y OUT)
    e("c=r 4 *c=a out a=c a++ r=a 4")
def TABLE(base, vals):        # H[base..] = vals (valores >= 0)
    e(f"a=r {base} d=a")
    for v in vals:
        LOADK(v); e("*d=a d++")

e("hcomp")
e("halt")
e("pcomp zpaqzstd ;")
e("""(ZPAQZSTD: decodificador de zstd en ZPAQL, para zpaq-std -ma:zstd. zpaq-std, 2026.
 Guarda el frame entero en M y lo decodifica al final: bloques crudos, RLE y
 comprimidos; literales crudos, RLE y Huff0 con o sin arbol, de 1 o 4 flujos;
 secuencias con tablas FSE predefinidas, RLE, transmitidas o repetidas; los tres
 offsets repetidos. La salida queda en M, detras, y sale con out. El Huff0 y el
 FSE son los de ZPAQLIZARDH.)""")
e("a> 255 ifl")
e("  a=c r=a 1")
# constantes de huff0 (pesos y tablas canonicas) y las propias
huff0.consts(e)
for reg, v, sh in [(LLS, 3, 9), (LLN, 1, 11), (LLX, 5, 9), (MLS, 3, 10), (MLN, 7, 9), (MLX, 1, 12),
                   (OFS, 9, 9), (OFN, 19, 8), (OFX, 5, 10), (LLB, 21, 8), (LLE, 85, 6), (MLB, 43, 7),
                   (MLE, 87, 6), (LLD, 11, 9), (MLD, 89, 6), (OFD, 45, 7), (PAR, 91, 6)]:
    e(f"a= {v} a<<= {sh} r=a {reg}")
TABLE(LLB, LL_BASE); TABLE(LLE, LL_BITS); TABLE(MLB, ML_BASE); TABLE(MLE, ML_BITS)
# normas por defecto como cuentas de NCount SIN restar 1 (0 es -1)
TABLE(LLD, [x+1 for x in LL_DEF]); TABLE(MLD, [x+1 for x in ML_DEF]); TABLE(OFD, [x+1 for x in OF_DEF])
# parametros por tabla, en el orden del flujo (LL, OF, ML):
#   0 base simbolo, 1 base nbBits, 2 base newState, 3 base de la norma, 4 simbolos,
#   5 log por defecto, 6 desplazamiento del modo, 7 tableLog guardado
e(f"a=r {PAR} d=a")
for (s_, n_, x_, d_, nsym, dl, sh) in [(LLS, LLN, LLX, LLD, 36, 6, 6), (OFS, OFN, OFX, OFD, 29, 5, 4), (MLS, MLN, MLX, MLD, 53, 6, 2)]:
    e(f"a=r {s_} *d=a d++ a=r {n_} *d=a d++ a=r {x_} *d=a d++ a=r {d_} *d=a d++")
    e(f"a= {nsym} *d=a d++ a= {dl} *d=a d++ a= {sh} *d=a d++ a=0 *d=a d++")
e("  a=r 1 r=a 126 r=a 38")                      # LB = n
e("  a= 2 a<<= 16 a+= 64 b=r 1 a+=b r=a 3 r=a 4")   # OB = n + 131136
e("  a=0 r=a 2 a= 1 r=a 12")
e("  do")                                            # un frame por vuelta
e("  a=r 2 a+= 4 b=r 1 a>b ifl a=0 r=a 12 endif")
e("  a=r 12 a> 0 ifl")
e("    a=r 2 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a>>= 4 r=a 24")
e("    a=r 2 a+= 4 r=a 2")
e("    a= 24 a<<= 8 a+= 77 a<<= 8 a+= 42 a<<= 4 a+= 5 b=a a=r 24 a==b ifl")   # frame saltable
e("      a=r 2 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a+= 4 b=r 2 a+=b r=a 2")
e("    elsel")
RDM(); e("      r=a 13")
e("      a>>= 5 a&= 1 a== 0 ifl a=r 2 a++ r=a 2 endif")        # Window_Descriptor
e("      a=r 13 a&= 3 a> 0 ifl a== 3 ifl a= 4 endif b=a a=r 2 a+=b r=a 2 endif")   # Dictionary_ID
e("      a=r 13 a>>= 6 a== 0 ifl a=r 13 a>>= 5 a&= 1")          # Frame_Content_Size
e("      elsel a== 1 ifl a= 2 elsel a== 2 ifl a= 4 elsel a= 8 endif endif endif")
e("      b=a a=r 2 a+=b r=a 2")
e("      a= 1 r=a 100 a= 4 r=a 101 a= 8 r=a 102")
e("      a=0 r=a 8")
e("      do")                                          # un bloque por vuelta
e("        a=r 2 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c r=a 24 a=r 2 a+= 3 r=a 2")
e("        a=r 24 a&= 1 r=a 8 a=r 24 a>>= 1 a&= 3 r=a 9 a=r 24 a>>= 3 r=a 10")
e("        a=r 9 a== 0 ifl")                            # bloque crudo
e("          a=r 10 a> 0 ifl")
e("            do")
RDM(); PUT()
e("              a=r 10 a-- r=a 10")
e("            a> 0 while")
e("          endif")
e("        elsel")
e("        a=r 9 a== 1 ifl")                            # bloque RLE
RDM(); e("          r=a 25 a=r 10 a> 0 ifl")
e("            do")
e("              a=r 25"); PUT()
e("              a=r 10 a-- r=a 10")
e("            a> 0 while")
e("          endif")
e("        elsel")                                      # bloque comprimido
e("          a=r 2 b=r 10 a+=b r=a 11")
RDM(); e("          r=a 25 a&= 3 r=a 14 a=r 25 a>>= 2 a&= 3 r=a 15")
e("          a=r 14 a< 2 ifl")
e("            a=r 15 a&= 1 a== 0 ifl")
e("              a=r 25 a>>= 3 r=a 16")
e("            elsel")
RDM(); e("              a<<= 4 r=a 16 a=r 25 a>>= 4 b=r 16 a+=b r=a 16")
e("              a=r 15 a== 3 ifl")
RDM(); e("                a<<= 12 b=r 16 a+=b r=a 16")
e("              endif")
e("            endif")
e("            a=r 14 a== 0 ifl")                       # literales crudos: se leen en su lugar
e("              a=r 2 r=a 6 b=r 16 a+=b r=a 2 r=a 7")
e("            elsel")                                  # literales RLE
RDM(); e("              r=a 25 a=r 126 r=a 6 c=a a=r 16 r=a 26")
e("              a> 0 ifl")
e("                do")
e("                  a=r 25 *c=a c++ a=r 26 a-- r=a 26")
e("                a> 0 while")
e("              endif")
e("              a=r 6 b=r 16 a+=b r=a 7")
e("            endif")
e("          elsel")                                    # literales Huff0
RDM(); e("            r=a 26"); RDM(); e("            r=a 27")            # b1, b2
e("            a=r 15 a< 2 ifl")                             # 3 bytes, 10 + 10 bits
e("              a=r 26 a&= 63 a<<= 4 r=a 16 a=r 25 a>>= 4 b=r 16 a+=b r=a 16")
e("              a=r 27 a<<= 2 r=a 17 a=r 26 a>>= 6 b=r 17 a+=b r=a 17")
e("            elsel")
RDM(); e("              r=a 28")                                    # b3
e("              a=r 15 a== 2 ifl")                           # 4 bytes, 14 + 14 bits
e("                a=r 27 a&= 3 a<<= 12 r=a 16 a=r 26 a<<= 4 b=r 16 a+=b r=a 16 a=r 25 a>>= 4 b=r 16 a+=b r=a 16")
e("                a=r 28 a<<= 6 r=a 17 a=r 27 a>>= 2 b=r 17 a+=b r=a 17")
e("              elsel")                                      # 5 bytes, 18 + 18 bits
RDM(); e("                r=a 29")                                  # b4
e("                a=r 27 a&= 63 a<<= 12 r=a 16 a=r 26 a<<= 4 b=r 16 a+=b r=a 16 a=r 25 a>>= 4 b=r 16 a+=b r=a 16")
e("                a=r 29 a<<= 10 r=a 17 a=r 28 a<<= 2 b=r 17 a+=b r=a 17 a=r 27 a>>= 6 b=r 17 a+=b r=a 17")
e("              endif")
e("            endif")
e("            a=r 2 r=a 35 a=r 17 r=a 36 a=r 16 r=a 37 a=r 126 r=a 38 r=a 6 b=r 16 a+=b r=a 7")
e("            a=r 14 a== 2 ifl")
e("              a= 139 a<<= 3 r=a 76 a= 147 a<<= 3 r=a 77 a= 155 a<<= 3 r=a 78")   # tabla FSE de los pesos
huff0.HUF_TREE(e)
e("            elsel")
e("              a=r 2 r=a 87")                         # sin arbol: el de antes
e("            endif")
e("            a=r 15 a== 0 ifl")
huff0.HUF_1STREAM(e)
e("            elsel")
huff0.HUF_4STREAMS(e)
e("            endif")
e("            a=r 2 b=r 17 a+=b r=a 2")
e("          endif")
# secuencias
RDM(); e("          r=a 18")
e("          a> 127 ifl")
e("            a== 255 ifl")
RDM(); e("              r=a 25"); RDM(); e("              a<<= 8 b=r 25 a+=b r=a 26 a= 127 a<<= 8 b=r 26 a+=b r=a 18")   # + 0x7F00
e("            elsel")
e("              a-= 128 a<<= 8 r=a 25"); RDM(); e("              b=r 25 a+=b r=a 18")
e("            endif")
e("          endif")
e("          a=r 18 a> 0 ifl")
RDM(); e("            r=a 19")
e("            a=0 r=a 109")
e("            do")
e("              a=r 109 a<<= 3 b=r 127 a+=b d=a a=*d r=a 76 d++ a=*d r=a 77 d++ a=*d r=a 78")
e("              d++ a=*d r=a 29 d++ a=*d r=a 30 d++ a=*d r=a 31 d++ a=*d b=a a=r 19 a>>=b a&= 3 r=a 28")
e("              a== 0 ifl")                            # predefinida
e("                a=0 r=a 66")
e("                do")
e("                  a=r 66 b=r 29 a+=b d=a a=*d r=a 69"); HSET(e, huff0.NC, 66, 69)
e("                  a=r 66 a++ r=a 66 b=r 30")
e("                a<b while")
e("                a=r 30 r=a 57 a=r 31 r=a 53")
huff0.FSE_BUILD(e)
e("                a=r 53 r=a 25")
e("              elsel")
e("              a=r 28 a== 1 ifl")                     # RLE: un simbolo, 0 bits
RDM(); e("                c=a a=r 76 d=a a=c *d=a a=r 77 d=a a=0 *d=a a=r 78 d=a a=0 *d=a r=a 25")
e("              elsel")
e("              a=r 28 a== 2 ifl")                     # transmitida
e("                a=r 11 b=r 2 a-=b r=a 51 a=r 2 r=a 52")
huff0.FSE_NCOUNT(e)
huff0.FSE_BUILD(e)
e("                a=r 50 a+= 7 a>>= 3 b=r 2 a+=b r=a 2 a=r 53 r=a 25")
e("              elsel")                                # repetida: la de antes
e("                a=r 109 a<<= 3 b=r 127 a+=b a+= 7 d=a a=*d r=a 25")
e("              endif")
e("              endif")
e("              endif")
e("              a=r 109 a<<= 3 b=r 127 a+=b a+= 7 d=a a=r 25 *d=a")
e("              a=r 109 a++ r=a 109")
e("            a< 3 while")
e("            a=r 127 a+= 7 d=a a=*d r=a 103 a=r 127 a+= 15 d=a a=*d r=a 104 a=r 127 a+= 23 d=a a=*d r=a 105")
e("            a=r 11 b=r 2 a-=b r=a 29 a=r 2 r=a 30")
INITB(e, 30, 29)
READB(e, 103, 106); READB(e, 104, 107); READB(e, 105, 108)
e("            a=r 18 r=a 20")
e("            do")
HGET(e, OFS, 107); e("              r=a 26"); HGET(e, MLS, 108); e("              r=a 27"); HGET(e, LLS, 106); e("              r=a 28")
READB(e, 26, 23); e("              a= 1 b=r 26 a<<=b b=r 23 a+=b r=a 23")
HGET(e, MLE, 27); e("              r=a 29"); READB(e, 29, 24); HGET(e, MLB, 27); e("              b=r 24 a+=b r=a 22")
HGET(e, LLE, 28); e("              r=a 29"); READB(e, 29, 24); HGET(e, LLB, 28); e("              b=r 24 a+=b r=a 21")
# offsets repetidos
e("              a=r 23 a> 3 ifl")
e("                a-= 3 r=a 23 a=r 101 r=a 102 a=r 100 r=a 101 a=r 23 r=a 100")
e("              elsel")
e("                a=r 21 a== 0 ifl a=r 23 a++ r=a 23 endif")
e("                a=r 23 a== 1 ifl")
e("                  a=r 100 r=a 23")
e("                elsel")
e("                a=r 23 a== 2 ifl")
e("                  a=r 101 r=a 23 a=r 100 r=a 101 a=r 23 r=a 100")
e("                elsel")
e("                a=r 23 a== 3 ifl")
e("                  a=r 102 r=a 23 a=r 101 r=a 102 a=r 100 r=a 101 a=r 23 r=a 100")
e("                elsel")
e("                  a=r 100 a-- r=a 23 a=r 101 r=a 102 a=r 100 r=a 101 a=r 23 r=a 100")
e("                endif")
e("                endif")
e("                endif")
e("              endif")
# literales y copia
e("              a=r 21 a> 0 ifl")
e("                do")
e("                  a=r 6 c=a a=*c"); PUT(); e("                  a=r 6 a++ r=a 6 a=r 21 a-- r=a 21")
e("                a> 0 while")
e("              endif")
e("              a=r 4 b=r 23 a-=b r=a 24 a=r 22")
e("              a> 0 ifl")
e("                do")
e("                  a=r 24 c=a a=*c"); PUT(); e("                  a=r 24 a++ r=a 24 a=r 22 a-- r=a 22")
e("                a> 0 while")
e("              endif")
e("              a=r 20 a-- r=a 20")
e("              a> 0 ifl")
for (st, nb_, ns_) in [(106, LLN, LLX), (108, MLN, MLX), (107, OFN, OFX)]:
    HGET(e, nb_, st); e("                r=a 29"); READB(e, 29, 24); HGET(e, ns_, st); e(f"                b=r 24 a+=b r=a {st}")
e("              endif")
e("              a=r 20")
e("            a> 0 while")
e("          endif")
e("          a=r 7 b=r 6 a>b ifl")                       # los literales que quedan
e("            do")
e("              a=r 6 c=a a=*c"); PUT(); e("              a=r 6 a++ r=a 6 b=r 7")
e("            a<b while")
e("          endif")
e("          a=r 11 r=a 2")
e("        endif")
e("        endif")
e("        a=r 8")
e("      a== 0 while")
e("      a=r 13 a>>= 2 a&= 1 a> 0 ifl a=r 2 a+= 4 r=a 2 endif")   # checksum: se salta
e("    endif")
e("  endif")
e("  a=r 12")
e("  a> 0 while")
e("  a=0 c=a")
e("elsel")
e("  *c=a c++")
e("endif")
e("halt")
e("end")
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
