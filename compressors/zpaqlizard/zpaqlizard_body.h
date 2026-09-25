/*
  ZPAQLIZARD: a Lizard 2.1 decoder written in ZPAQL, for zpaq-std -ma:lizard,
  levels 10-29 (fastLZ4 and LIZv1; levels 30-49 add Huffman and have their
  own program, ZPAQLIZARDH, in zpaqlizardh_body.h). zpaq-std, 2026. Generated
  by gen.py next to this file (ZPAQL has no subroutines: the stream reads and
  copies are macros expanded in place).

  Each Lizard block holds five streams (lengths, 16- and 24-bit offsets, tokens,
  literals), each with a 3-byte length in front, so the whole block is kept in M
  and decoded at the end of the segment. Input: original size (4 bytes LE), then
  Lizard_compress's output. M holds the whole output, then the compressed data.

  Verified with zpaqd 7.15 on 110 Lizard streams (11 inputs x levels 10, 12, 15,
  17, 19, 20, 22, 25, 27, 29): fastLZ4 tokens, the three LIZv1 token classes
  (new / repeated 16-bit offset, 24-bit offset, token 31) and stored blocks.

  FROZEN, like the other portable decoders.
*/
static const char ZPAQLIZARD_CUERPO[] = R"ZLZD(hcomp
halt
pcomp zpaqlizard ;
(ZPAQLIZARD: decodificador de Lizard 2.1, niveles 10-29 - fastLZ4 y LIZv1, sin
 Huffman -, en ZPAQL, para zpaq-std -ma:lizard. zpaq-std, 2026. Cada bloque de
 Lizard lleva cinco flujos: largos, offsets de 16 y de 24 bits, tokens y
 literales, cada uno con su largo de 3 bytes delante; por eso se guarda el bloque
 entero y se decodifica al final. Entrada: tamano original, 4 bytes LE, y el flujo
 de Lizard. M: la salida al principio, el comprimido detras.)
*c=a c++
d=a
a=r 31
a< 2 ifl
  a== 0 ifl
    a=c a< 4 ifl
      halt
    elsel
      a= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
      r=a 1 r=a 4 c=a a= 1 r=a 31
      halt
    endif
  elsel
    a=d a> 255 if a= 2 r=a 31 a=c a-- r=a 6 endif
    a=r 31 a== 1 if halt endif
  endif
endif
a== 2 ifnot halt endif
a=0 r=a 5
c=r 4 a=*c
a< 20 if a=0 else a= 1 endif r=a 7
a=r 4 a+= 1 r=a 4
do
c=r 4 a=*c
r=a 20
a=r 4 a+= 1 r=a 4
a=r 20 a== 128 ifl
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 21
a=r 4 a+= 3 r=a 4
a=r 21 a> 0 ifl
  do
    c=r 4 a=*c c=r 5 *c=a out a=r 4 a++ r=a 4 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
elsel
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 4 a+= 3 r=a 4
a=r 4 r=a 11 b=r 24 a+=b r=a 4
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 4 a+= 3 r=a 4
a=r 4 r=a 12 b=r 24 a+=b r=a 4
r=a 13
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 4 a+= 3 r=a 4
a=r 4 r=a 14 b=r 24 a+=b r=a 4
r=a 15
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 4 a+= 3 r=a 4
a=r 4 r=a 16 b=r 24 a+=b r=a 4
r=a 17
a=r 4 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 4 a+= 3 r=a 4
a=r 4 r=a 18 b=r 24 a+=b r=a 4
r=a 19
  a=0 r=a 23
  a=r 7 a== 0 ifl
    a=r 16 b=r 17 a<b ifl
    do
c=r 16 a=*c
r=a 20
a=r 16 a+= 1 r=a 16
      a=r 20 a&= 15 r=a 21 a== 15 ifl
c=r 18 a=*c
r=a 24
a> 253 ifl
  a== 254 ifl
a=r 18 a+= 2 c=a a=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 2 r=a 18
  elsel
a=r 18 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 3 r=a 18
  endif
endif
a=r 24 a+= 15 r=a 21
a=r 18 a+= 1 r=a 18
      endif
a=r 21 a> 0 ifl
  do
    c=r 18 a=*c c=r 5 *c=a out a=r 18 a++ r=a 18 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
a=r 18 a+= 1 c=a a=*c a<<= 8 c-- a+=*c
r=a 22
a=r 18 a+= 2 r=a 18
      a=r 20 a>>= 4 r=a 21 a== 15 ifl
c=r 18 a=*c
r=a 24
a> 253 ifl
  a== 254 ifl
a=r 18 a+= 2 c=a a=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 2 r=a 18
  elsel
a=r 18 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 3 r=a 18
  endif
endif
a=r 24 a+= 15 r=a 21
a=r 18 a+= 1 r=a 18
      endif
      a=r 21 a+= 4 r=a 21
a=r 5 b=r 22 a-=b r=a 24
a=r 21 a> 0 ifl
  do
    c=r 24 a=*c c=r 5 *c=a out a=r 24 a++ r=a 24 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
      a=r 16 b=r 17
    a<b while
    endif
  elsel
    a=r 16 b=r 17 a<b ifl
    do
c=r 16 a=*c
r=a 20
a=r 16 a+= 1 r=a 16
      a=r 20 a> 31 ifl
        a&= 7 r=a 21 a== 7 ifl
c=r 18 a=*c
r=a 24
a=r 18 a+= 1 r=a 18
a=r 24 a> 253 ifl
  a== 254 ifl
a=r 18 a+= 1 c=a a=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 2 r=a 18
  elsel
a=r 18 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 3 r=a 18
  endif
endif
a=r 24 a+= 7 r=a 21
        endif
a=r 21 a> 0 ifl
  do
    c=r 18 a=*c c=r 5 *c=a out a=r 18 a++ r=a 18 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
        a=r 13 b=r 12 a-=b a> 1 ifl
          a=r 20 a>>= 7 a== 0 ifl
a=r 12 a+= 1 c=a a=*c a<<= 8 c-- a+=*c
r=a 23
a=r 12 a+= 2 r=a 12
          endif
        endif
        a=r 20 a>>= 3 a&= 15 r=a 21 a== 15 ifl
c=r 18 a=*c
r=a 24
a> 253 ifl
  a== 254 ifl
a=r 18 a+= 2 c=a a=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 2 r=a 18
  elsel
a=r 18 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 3 r=a 18
  endif
endif
a=r 24 a+= 15 r=a 21
a=r 18 a+= 1 r=a 18
        endif
      elsel
        a=r 20 a< 31 ifl
          a+= 16 r=a 21
a=r 14 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 23
a=r 14 a+= 3 r=a 14
        elsel
c=r 18 a=*c
r=a 24
a> 253 ifl
  a== 254 ifl
a=r 18 a+= 2 c=a a=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 2 r=a 18
  elsel
a=r 18 a+= 3 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 24
a=r 18 a+= 3 r=a 18
  endif
endif
a=r 24 a+= 47 r=a 21
a=r 18 a+= 1 r=a 18
a=r 14 a+= 2 c=a a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
r=a 23
a=r 14 a+= 3 r=a 14
        endif
      endif
a=r 5 b=r 23 a-=b r=a 24
a=r 21 a> 0 ifl
  do
    c=r 24 a=*c c=r 5 *c=a out a=r 24 a++ r=a 24 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
      a=r 16 b=r 17
    a<b while
    endif
  endif
  a=r 19 b=r 18 a-=b r=a 21
a=r 21 a> 0 ifl
  do
    c=r 18 a=*c c=r 5 *c=a out a=r 18 a++ r=a 18 a=r 5 a++ r=a 5
    a=r 21 a-- r=a 21
  a> 0 while
endif
endif
a=r 4 b=r 6 a<b if a= 1 else a=0 endif
a> 0 while
a= 3 r=a 31
halt
end
)ZLZD";
