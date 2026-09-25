# Generador de ZPAQLIZARD: bloques de Lizard 2.1, niveles 10-29 (fastLZ4 y LIZv1,
# sin Huffman), en ZPAQL. Macros expandidas en linea (ZPAQL no tiene subrutinas).
#   python3 gen.py salida.txt           ZPAQLIZARD, el de 10-29 (CONGELADO: tiene que
#                                        salir identico al de zpaqlizard_body.h)
#   python3 gen.py salida.txt --huff    ZPAQLIZARDH, 10-49: lo mismo mas Huff0 (huff0.py)
import sys
HUFF='--huff' in sys.argv
if HUFF: import huff0
out=[]
def e(s): out.append(s)
# registros: r4 p (entrada), r5 salida, r6 fin de entrada, r7 modo (0 LZ4, 1 LIZv1)
# r11 lenPtr, r12 p16, r13 e16, r14 p24, r15 e24, r16 fPtr, r17 fEnd, r18 lPtr, r19 lEnd
# r20 token, r21 largo, r22 offset, r23 last_off, r24 temporal, r31 fase
def RD(ptr):          # a = M[r ptr]
    e(f"c=r {ptr} a=*c")
def LE16(ptr, off=0): # a = LE16 en M[r ptr + off]
    e(f"a=r {ptr} a+= {off+1} c=a a=*c a<<= 8 c-- a+=*c")
def LE24(ptr, off=0):
    e(f"a=r {ptr} a+= {off+2} c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c")
def ADD(reg, n):
    e(f"a=r {reg} a+= {n} r=a {reg}")
def COPYLIT(nreg, ptr):   # copia r nreg bytes desde M[r ptr] a la salida
    e(f"a=r {nreg} a> 0 ifl")
    e("  do")
    e(f"    c=r {ptr} a=*c c=r 5 *c=a out a=r {ptr} a++ r=a {ptr} a=r 5 a++ r=a 5")
    e(f"    a=r {nreg} a-- r=a {nreg}")
    e("  a> 0 while")
    e("endif")
def COPYMATCH(nreg, offreg):
    e(f"a=r 5 b=r {offreg} a-=b r=a 24")
    e(f"a=r {nreg} a> 0 ifl")
    e("  do")
    e(f"    c=r 24 a=*c c=r 5 *c=a out a=r 24 a++ r=a 24 a=r 5 a++ r=a 5")
    e(f"    a=r {nreg} a-- r=a {nreg}")
    e("  a> 0 while")
    e("endif")
def EXT_AFTER(dst, base):  # largo extendido "a la LZ4": v=M[l]; 254:LE16(l+1),l+=2; 255:LE24(l+1),l+=3; +base; l++
    RD(18); e("r=a 24")
    e("a> 253 ifl")
    e("  a== 254 ifl")
    LE16(18,1); e("r=a 24"); ADD(18,2)
    e("  elsel")
    LE24(18,1); e("r=a 24"); ADD(18,3)
    e("  endif")
    e("endif")
    e(f"a=r 24 a+= {base} r=a {dst}"); ADD(18,1)
def EXT_BEFORE(dst, base): # variante del literal de LIZv1: l++ primero, luego LE16/LE24 en l
    RD(18); e("r=a 24"); ADD(18,1)
    e("a=r 24 a> 253 ifl")
    e("  a== 254 ifl")
    LE16(18); e("r=a 24"); ADD(18,2)
    e("  elsel")
    LE24(18); e("r=a 24"); ADD(18,3)
    e("  endif")
    e("endif")
    e(f"a=r 24 a+= {base} r=a {dst}")

e("hcomp")
e("halt")
if HUFF:
    e("pcomp zpaqlizardh ;")
    e("""(ZPAQLIZARDH: decodificador de Lizard 2.1, niveles 10-49 - fastLZ4 y LIZv1,
 con y sin Huffman -, en ZPAQL, para zpaq-std -ma:lizard. zpaq-std, 2026. Es
 ZPAQLIZARD mas Huff0, el Huffman de zstd 1.4 que Lizard usa en los niveles
 30-49: pesos con FSE o crudos, cuatro flujos leidos hacia atras. Los flujos
 Huffman se decodifican en M detras de la entrada. Entrada: tamano original, 4
 bytes LE, y el flujo de Lizard. M: la salida, el comprimido y los buffers.)""")
else:
  e("pcomp zpaqlizard ;")
  e("""(ZPAQLIZARD: decodificador de Lizard 2.1, niveles 10-29 - fastLZ4 y LIZv1, sin
 Huffman -, en ZPAQL, para zpaq-std -ma:lizard. zpaq-std, 2026. Cada bloque de
 Lizard lleva cinco flujos: largos, offsets de 16 y de 24 bits, tokens y
 literales, cada uno con su largo de 3 bytes delante; por eso se guarda el bloque
 entero y se decodifica al final. Entrada: tamano original, 4 bytes LE, y el flujo
 de Lizard. M: la salida al principio, el comprimido detras.)""")
e("*c=a c++")
e("d=a")
e("a=r 31")
e("a< 2 ifl")
e("  a== 0 ifl")
e("    a=c a< 4 ifl")
e("      halt")
e("    elsel")
e("      a= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c")
e("      r=a 1 r=a 4 c=a a= 1 r=a 31")
if HUFF: huff0.consts(e)
e("      halt")
e("    endif")
e("  elsel")
e("    a=d a> 255 if a= 2 r=a 31 a=c a-- r=a 6 endif")   # fin de entrada = ultimo byte real
e("    a=r 31 a== 1 if halt endif")
e("  endif")
e("endif")
e("a== 2 ifnot halt endif")
e("a=0 r=a 5")
if HUFF: RD(4); e("a/= 10 a&= 1 a^= 1 r=a 7"); ADD(4,1)   # 10-19 y 30-39: fastLZ4
else: RD(4); e("a< 20 if a=0 else a= 1 endif r=a 7"); ADD(4,1)   # byte de nivel
e("do")                                   # un bloque de Lizard por vuelta
RD(4); e("r=a 20"); ADD(4,1)
e("a=r 20 a== 128 ifl")                   # bloque sin comprimir
LE24(4); e("r=a 21"); ADD(4,3)
COPYLIT(21,4)
e("elsel")
if not HUFF:
  for (ptr,end) in [(11,None),(12,13),(14,15),(16,17),(18,19)]:
    LE24(4); e("r=a 24"); ADD(4,3)
    e(f"a=r 4 r=a {ptr} b=r 24 a+=b r=a 4")
    if end: e(f"r=a {end}")
else:
    # largos (sin Huffman nunca), y los otros cuatro en un lazo: el decodificador
    # Huff0 aparece una sola vez. Bit del flag por flujo: 4 8 2 1 (tabla en H[560]).
    LE24(4); e("r=a 24"); ADD(4,3)
    e("a=r 4 r=a 11 b=r 24 a+=b r=a 4")
    e("a=r 6 a++ r=a 34 a=0 r=a 32")
    e("do")
    huff0.HGET(e, huff0.SH, 32); e("  b=a a=r 20 a>>=b a&= 1")
    e("  a== 0 ifl")
    LE24(4); e("r=a 24"); ADD(4,3)
    e("    a=r 4 r=a 47 b=r 24 a+=b r=a 4 r=a 48")
    e("  elsel")
    LE24(4); e("r=a 37"); LE24(4,3); e("r=a 36")
    e("    a=r 4 a+= 6 r=a 35 b=r 36 a+=b r=a 4")
    e("    a=r 34 r=a 38 r=a 47 b=r 37 a+=b r=a 48 r=a 34")
    huff0.HUFF(e)
    e("  endif")
    e("  a=r 32 a<<= 1 b=r 79 a+=b d=a a=r 47 *d=a d++ a=r 48 *d=a")
    e("  a=r 32 a++ r=a 32")
    e("a< 4 while")
    e("a=r 79 d=a a=*d r=a 12 d++ a=*d r=a 13 d++ a=*d r=a 14 d++ a=*d r=a 15")
    e("d++ a=*d r=a 16 d++ a=*d r=a 17 d++ a=*d r=a 18 d++ a=*d r=a 19")
e("  a=0 r=a 23")
e("  a=r 7 a== 0 ifl")                    # fastLZ4
e("    a=r 16 b=r 17 a<b ifl")
e("    do")
RD(16); e("r=a 20"); ADD(16,1)
e("      a=r 20 a&= 15 r=a 21 a== 15 ifl")
EXT_AFTER(21,15)
e("      endif")
COPYLIT(21,18)
LE16(18); e("r=a 22"); ADD(18,2)
e("      a=r 20 a>>= 4 r=a 21 a== 15 ifl")
EXT_AFTER(21,15)
e("      endif")
e("      a=r 21 a+= 4 r=a 21")
COPYMATCH(21,22)
e("      a=r 16 b=r 17")
e("    a<b while")
e("    endif")
e("  elsel")                              # LIZv1
e("    a=r 16 b=r 17 a<b ifl")
e("    do")
RD(16); e("r=a 20"); ADD(16,1)
e("      a=r 20 a> 31 ifl")
e("        a&= 7 r=a 21 a== 7 ifl")
EXT_BEFORE(21,7)
e("        endif")
COPYLIT(21,18)
e("        a=r 13 b=r 12 a-=b a> 1 ifl")
e("          a=r 20 a>>= 7 a== 0 ifl")
LE16(12); e("r=a 23"); ADD(12,2)
e("          endif")
e("        endif")
e("        a=r 20 a>>= 3 a&= 15 r=a 21 a== 15 ifl")
EXT_AFTER(21,15)
e("        endif")
e("      elsel")
e("        a=r 20 a< 31 ifl")
e("          a+= 16 r=a 21")
LE24(14); e("r=a 23"); ADD(14,3)
e("        elsel")
EXT_AFTER(21,47)
LE24(14); e("r=a 23"); ADD(14,3)
e("        endif")
e("      endif")
COPYMATCH(21,23)
e("      a=r 16 b=r 17")
e("    a<b while")
e("    endif")
e("  endif")
e("  a=r 19 b=r 18 a-=b r=a 21")          # ultimos literales
COPYLIT(21,18)
e("endif")
e("a=r 4 b=r 6 a<b if a= 1 else a=0 endif")     # hay mas bloques si p < fin
e("a> 0 while")
e("a= 3 r=a 31")
e("halt")
e("end")
import sys
open(sys.argv[1],'w').write('\n'.join(out)+'\n'); print(len('\n'.join(out)))
