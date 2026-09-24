/*
  ZPAQFLZMA2: an LZMA2 decoder written in ZPAQL, for zpaq-std -ma:flzma2 (the
  stream fast-lzma2's FL2_compress writes). zpaq-std, 2026.

  Derived from the LZMA1 decoder in ZPAQL by Kaido Orav (kaitz), from zpaqf,
  https://github.com/kaitz/zpaqf (public domain, see LICENSE next to this
  file): the per-symbol loop is his, verbatim, except that posState and the lp
  bits count from the last dictionary reset (r39). What is new is the walk over
  LZMA2 chunks: control byte, uncompressed chunks, state / property / dictionary
  resets, and a range-coder restart per chunk.

  Input: original size (4 bytes LE), then FL2_compress's output (property byte,
  ignored; chunks; 0 end marker). M holds the whole output, then the
  compressed data behind it; zpaq-std sets pm so that both fit.

  Verified with zpaqd 7.15 against 80 fast-lzma2 streams (8 inputs x levels
  1..10), every chunk type included.

  FROZEN, like ZPAQLZ5 and ZPAQLZMA: every block carries its own copy and
  zpaq-std recognises it byte for byte. A different program gets a new tag.
*/
static const char ZPAQFLZMA2_CUERPO[] = R"ZFL2(hcomp
halt
pcomp flzma2 c ;
(ZPAQFLZMA2: decodificador LZMA2, el flujo de fast-lzma2, en ZPAQL, para
 zpaq-std -ma:flzma2. Deriva del decodificador LZMA1 de Kaido Orav - kaitz -,
 zpaqf, dominio publico: el bucle por simbolo es el suyo, textual, salvo que
 la posicion de posState y de los bits lp se cuenta desde el ultimo reinicio
 de diccionario, r39. Lo nuevo es el recorrido de los fragmentos LZMA2.
 Entrada: tamano original en 4 bytes LE, luego la salida de FL2_compress: el
 byte de propiedad, que se ignora, los fragmentos, y un 0 de fin.
 M: la salida entera al principio, los datos comprimidos detras.
 Registros nuevos: r39 base del diccionario, r40 inicio del fragmento
 siguiente, r41 tamano original, r42 control, r43 largo, r44 largo comprimido,
 r45 modo de reinicio, r46 lc+lp.)
    *c=a c++
    d=a
        a=r 24
        a< 2 ifl
            a== 0 ifl
                a=c a< 4 ifl
                    halt
                elsel
                    a= 255 b=a
                    a= 7 a<<= 8 a+= 54 r=a 26       (val1=1846 literales)
                    a= 3 a<<= 8 r=a 27              (val2=768)
                    a-= 81  r=a 31                  (val6=687)
                    a+= 115 r=a 32                  (val7=802)
                    a+= 16  r=a 30                  (val5=818)
                    a+=b a+=b a+= 4 r=a 29          (val4=1332)
                    a+=b a+=b a+= 175 r=a 28        (val3=2017)
                    a= 1 a<<= 16 a-- r=a 25         (mask=0xffff)
                    a= 3 c=a
                    a=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c a<<= 8 c-- a+=*c
                    r=a 41 r=a 23 r=a 36 c=a        (comprimido desde M[tam])
                    a= 1 r=a 24
                    halt
                endif
            elsel
                a=d
                a> 255 if
                    a= 2 r=a 24
                endif
                a=r 24 a== 1 if
                    halt
                endif
            endif
        endif
        a== 3 ifl
            halt
        endif
        a== 2 ifnot
            halt
        endif
        a=r 23 a++ r=a 36                   (salta el byte de propiedad de FL2)
        a=0 r=a 20 r=a 39 r=a 12
        do                                  (un fragmento LZMA2 por vuelta)
            c=r 36 a=*c c++ r=a 42 a=c r=a 36
            a=r 42
            a> 0 ifl
                a< 128 ifl                  (1/2: sin comprimir; 1 reinicia el diccionario)
                    a== 1 if
                        a=r 20 r=a 39
                    endif
                    c=r 36 a=*c a<<= 8 c++ a+=*c c++ a++ r=a 43 a=c r=a 36
                    do
                        c=r 36 a=*c c++ b=a a=c r=a 36
                        a=b r=a 12 c=r 20 *c=a c++ a=c r=a 20
                        a=r 43 a-- r=a 43
                    a> 0 while
                elsel                       (LZMA: 1ccuuuuu uuuuuuuu uuuuuuuu pppppppp pppppppp)
                    a&= 31 a<<= 8 c=r 36 a+=*c a<<= 8 c++ a+=*c c++ a++ r=a 43
                    a=*c a<<= 8 c++ a+=*c c++ a++ r=a 44
                    a=c r=a 36
                    a=r 42 a>>= 5 a&= 3 r=a 45
                    a> 1 ifl                (2/3: propiedades nuevas)
                        c=r 36
                        a=*c a/= 9 r=a 6
                        a=*c a%= 9 r=a 4
                        a=r 6 a%= 5 r=a 5
                        a=r 6 a/= 5 r=a 6
                        a=r 4 b=r 5 a+=b r=a 46
                        a= 1 b=r 6 a<<=b a-- r=a 6
                        a= 1 b=r 5 a<<=b a-- r=a 5
                        c++ a=c r=a 36
                    endif
                    a=r 45 a== 3 if         (3: reinicio de diccionario)
                        a=r 20 r=a 39 a=0 r=a 12
                    endif
                    a=r 45 a> 0 ifl         (1..3: reinicio de estado)
                        a= 1 r=a 0 r=a 1 r=a 2 r=a 3
                        a=0 r=a 13
                        b=r 46 a=r 27 a<<=b b=r 26 a+=b c=a
                        a= 4 a<<= 8 b=a d=0
                        do
                            a=b *d=a d++
                            a=d
                        a<c while
                    endif
                    c=r 36 a=c b=r 44 a+=b r=a 40
                    c++
                    a=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c a<<= 8 c++ a+=*c c++ r=a 8
                    a=c r=a 36
                    a=0 a-- r=a 7
                    a=r 20 b=r 43 a+=b r=a 22
                do
                    a=0 r=a 15                                    (r[15] = 0)
                    a=r 20 b=r 39 a-=b b=r 6 a&=b r=a 18 c=a                  (r[18] = r[20] & r[6])
                    a=r 13 a*= 16 a+=c r=a 34 d=a                 (p3 = r[13] * 16 + r[18])
                    a=r 7 a>>= 24 a== 0 if                        (if ((r[7] >> 24)==0))
                        a=r 7 a<<= 8 r=a 7                        (r[7] <<= 8)
                        a=r 8 a<<= 8 c=r 36 a|=*c c++
                        r=a 8 a=c r=a 36                          (r[8] = r[8] << 8 | *c)
                    endif
                    d=*d a=d r=a 9 a=r 7 a>>= 11 
                    a*=d c=a                                      (r[11] = r[9] = *p3 r[10] = r[9] * (r[7] >> 11))
                    a=r 8 a<c                                     (r[14] = r[8] < r[10])
                    if                                            (if (r[14]) r[7] = r[10], r[11] -= r[28])
                        a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                    else                                          
                        a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8         (r[7]-= r[10], r[8]-= r[10])
                    endif
                    a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 34 *d=a (*p3 = r[9]-(r[11] >> 5))
                    a=r 14
                    a> 0 ifl                                      (if (r[14]) )
                        a=r 20 b=r 39 a-=b b=r 5 a&=b                         (r[18] = r[20] & r[5])
                        b=r 4 a<<=b d=a a= 8 a-=b b=a 
                        a=r 12 a>>=b a|=d r=a 18                  (r[18] = r[18] << r[4] | r[12] >> (8 - r[4]))
                        b=r 27 a*=b b=r 26 a+=b r=a 34            (p3 = r[26] + r[27] * r[18])
                        a=0 r=a 19 r=a 16                         (r[19] = r[16] = 0)
                        a=r 13 a> 6 if                            (if ( r[13] >= 7) )
                            a= 1 a<<= 8 r=a 19                    (r[19] = 0x100)
                            a=r 20 b=r 0 a<b a=0 if a=r 23 endif  (r[16] = dict[(r[20] < r[0] ? r[23] : 0) + r[20] - r[0]])
                            b=r 20 a+=b b=r 0 a-=b b=a a=*b r=a 16
                        endif
                        a= 1 r=a 15 r=a 12                        (r[15] = r[12] = 1)
                        do
                            a=r 16 a<<= 1 r=a 16                  (r[16] <<= 1)
                            b=r 19 d=b a&=b b=r 12 a+=b a+=d
                            b=r 34 a+=b r=a 33 d=a                (p1 = p3 + r[19] + (r[16] & r[19]) + r[12])
                            a=r 7 a>>= 24 a== 0 if                (if ((r[7] >> 24)==0) )
                                a=r 7 a<<= 8 r=a 7                (r[7] <<= 8)
                                a=r 8 a<<= 8 c=r 36 a|=*c c++ 
                                r=a 8 a=c r=a 36                  (r[8] = r[8] << 8 | *c)
                            endif
                            d=*d a=d r=a 9 a=r 7 a>>= 11
                            a*=d c=a                              (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                            a=r 8 a<c                             (r[14] = r[8] < r[10])
                            if                                    (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                            else                                   (else r[7] -= r[10], r[8] -= r[10])
                                a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                            endif
                            a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                            a=r 12 a<<= 1 c=a                      (r[12] <<= 1)
                            a=r 14 a== 1 b=r 16 a=r 19 if          (if (r[14]) )
                                a&~b                                (r[19] &=~r[16])
                            else 
                                a&=b c++                            (r[12]++, r[19] &= r[16])
                            endif r=a 19
                            a= 1 a<<= 8 c<>a r=a 12
                        a<c while                                  (while (r[12] < 256))
                        a&= 255 r=a 12                             (r[12] &= 255)
                        b=r 20 *b=a b++ a=b r=a 20                 (dict[r[20]++] = r[12])
                        a=r 13 a< 4 if                             (r[13] -= r[13] < 4 ? r[13] : r[13] > 9 ? 6 : 3)
                              a=0
                        else
                            a-= 3 a> 6 if 
                                 a-= 3
                              endif
                        endif
                        r=a 13
                    elsel
                        a=r 13 a+= 192 r=a 33  d=a                 (p1 = 192 + r[13])
                        a=r 13 a< 7 a=0 ifnot a= 3 endif r=a 13    (r[13] = r[13] < 7 ? 0 : 3)
                        a=r 7 a>>= 24 a== 0 if                     (if ((r[7] >> 24)==0) )
                            a=r 7 a<<= 8 r=a 7                     (r[7] <<= 8)
                            a=r 8 a<<= 8 c=r 36 a|=*c c++
                            r=a 8 a=c r=a 36                       (r[8] = r[8] << 8 | *c)
                        endif
                        d=*d a=d r=a 9 a=r 7 a>>= 11
                        a*=d c=a                                   (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                        a=r 8 a<c                                  (r[14] = r[8] < r[10])
                        if                                         (if (r[14]) r[7] = r[10], r[11] -= r[28])
                           a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                        else                                       (else r[7] -= r[10], r[8] -= r[10])
                           a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                        endif
                        a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                        a=r 14 a> 0 ifl                            (if (r[14]) )
                            a=r 2 r=a 3 a=r 1 r=a 2 a=r 0 r=a 1    (r[3] = r[2] r[2] = r[1] r[1] = r[0])
                            a=r 30 r=a 33                          (p1 = r[30])
                        elsel
                            a=r 33 a+= 12 r=a 33  d=a              (p1 += 12)
                            a=r 7 a>>= 24 a== 0 if                 (if ((r[7] >> 24)==0) )
                                a=r 7 a<<= 8 r=a 7                 (r[7] <<= 8)
                                a=r 8 a<<= 8 c=r 36 a|=*c c++
                                r=a 8 a=c r=a 36                   (r[8] = r[8] << 8 | *c)
                            endif
                            d=*d a=d r=a 9 a=r 7 a>>= 11
                            a*=d c=a                               (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                            a=r 8 a<c                              (r[14] = r[8] < r[10])
                            if                                     (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                            else                                   (else r[7] -= r[10], r[8] -= r[10])
                                a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                            endif
                            a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                            a=r 14 a> 0 ifl                        ( if (r[14]) )
                                a=r 34 a+= 240 r=a 34 d=a          (p3 += 240)
                                a=r 7 a>>= 24 a== 0 if             (if ((r[7] >> 24)==0) )
                                    a=r 7 a<<= 8 r=a 7             (r[7] <<= 8)
                                    a=r 8 a<<= 8 c=r 36 a|=*c c++
                                    r=a 8 a=c r=a 36               (r[8] = r[8] << 8 | *c)
                                endif
                                d=*d a=d r=a 9 a=r 7 a>>= 11
                                a*=d c=a                           (r[11] = r[9] = *p3 r[10] = r[9] * (r[7] >> 11))
                                a=r 8 a<c                          (r[14] = r[8] < r[10])
                                if                                 (if (r[14])) 
                                    a= 1 r=a 14 a=r 13 a|= 9 r=a 13 a= 1 r=a 15 ( r[13] |= 9, r[15] = 1)
                                    a=c r=a 7 a=d b=r 28 a-=b d=a   (r[7] = r[10], r[11] -= r[28])
                                else                                (else r[7] -= r[10], r[8] -= r[10])
                                    a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                endif
                                a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 34 *d=a (*p3 = r[9] - (r[11] >> 5))
                            elsel
                                a=r 33 a+= 12 r=a 33 d=a            (p1 += 12)
                                a=r 7 a>>= 24 a== 0 if              (if ((r[7] >> 24)==0) )
                                    a=r 7 a<<= 8 r=a 7              (r[7] <<= 8)
                                    a=r 8 a<<= 8 c=r 36 a|=*c c++
                                    r=a 8 a=c r=a 36                (r[8] = r[8] << 8 | *c)
                                endif
                                d=*d a=d r=a 9 a=r 7 a>>= 11 
                                a*=d c=a                            (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                a=r 8 a<c                           (r[14] = r[8] < r[10])
                                if                                  (if (r[14]))
                                    a= 1 r=a 14 a=r 1 r=a 17          (r[17] = r[1])
                                    a=c r=a 7 a=d b=r 28 a-=b d=a    (r[7] = r[10], r[11] -= r[28])
                                else                                (else r[7] -= r[10], r[8] -= r[10])
                                    a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                endif
                                a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                                a=r 14 a== 0 ifl                    (if (r[14]==0) )
                                    a=r 33 a+= 12 r=a 33 d=a        (p1 += 12)
                                    a=r 7 a>>= 24 a== 0 if          (if ((r[7] >> 24)==0) )
                                        a=r 7 a<<= 8 r=a 7          (r[7] <<= 8)
                                        a=r 8 a<<= 8 c=r 36 a|=*c c++
                                        r=a 8 a=c r=a 36            (r[8] = r[8] << 8 | *c)
                                    endif
                                    d=*d a=d r=a 9 a=r 7 a>>= 11
                                    a*=d c=a                       (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                    a=r 8 a<c                  (r[14] = r[8] < r[10])
                                    if                             (if (r[14]) )
                                        a= 1 r=a 14 a=r 2 r=a 17       ( r[17] = r[2])
                                        a=c r=a 7 a=d b=r 28 a-=b d=a (r[7] = r[10], r[11] -= r[28])
                                    else                            (else r[7] -= r[10], r[8] -= r[10])
                                        a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                        a=r 3 r=a 17 a=r 2 r=a 3     (r[17] = r[3], r[3] = r[2])
                                    endif
                                    a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                                    a=r 1 r=a 2                     (r[2] = r[1])
                                endif
                                a=r 0 r=a 1 a=r 17 r=a 0            (r[1] = r[0] r[0] = r[17])
                            endif
                            a=r 15 a== 0 if                         (if (r[15]==0) p1 = r[29], r[13] |= 8)
                                a=r 29 r=a 33 a= 8
                            else                                    (else r[13] |= 9)
                                a= 9 
                            endif b=r 13 a|=b r=a 13
                        endif
                        a=r 15 a== 0 ifl                            (if (r[15]==0) )
                            a= 2 r=a 15 a= 8 r=a 17                 (r[15] = 2 r[17] = 8)
                            b=r 18 a*=b a+= 2 b=r 33 d=b a+=b r=a 34 (p3 = p1 + r[18] * 8 + 2)
                            a=r 7 a>>= 24 a== 0 if                  (if ((r[7] >> 24)==0) )
                                a=r 7 a<<= 8 r=a 7                  (r[7] <<= 8)
                                a=r 8 a<<= 8 c=r 36 a|=*c c++ 
                                r=a 8 a=c r=a 36                    (r[8] = r[8] << 8 | *c)
                            endif
                            d=*d a=d r=a 9 a=r 7 a>>= 11 
                            a*=d c=a                                (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                            a=r 8 a<c                               (r[14] = r[8] < r[10])
                            if                                      (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                            else                                    (else r[7] -= r[10], r[8] -= r[10])
                                a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                            endif
                            a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                            a=r 14 a== 0 ifl                        (if (r[14]==0) )
                                a=r 33 a++ r=a 33 d=a a= 10 r=a 15  (p1++ r[15] = 10)
                                a=r 34 a+= 128 r=a 34               (p3 += 128)
                                a=r 7 a>>= 24 a== 0 if              (if ((r[7] >> 24)==0) )
                                    a=r 7 a<<= 8 r=a 7              (r[7] <<= 8)
                                    a=r 8 a<<= 8 c=r 36 a|=*c c++
                                    r=a 8 a=c r=a 36                (r[8] = r[8] << 8 | *c)
                                endif
                                d=*d a=d r=a 9 a=r 7 a>>= 11
                                a*=d c=a                            (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                a=r 8 a<c                           (r[14] = r[8] < r[10])
                                if                                  (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                    a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                                else                                (else r[7] -= r[10], r[8] -= r[10])
                                    a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                    a= 255 a++ r=a 17               (r[17] = 255+1, p3 = p1 + r[17] + 1, r[15] += 8)
                                    a++ b=r 33 a+=b r=a 34
                                    a=r 15 a+= 8 r=a 15
                                endif
                                a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                            endif
                            a= 1 r=a 12                             (r[12] = 1)
                            do
                                b=r 34 a+=b r=a 33 d=a              (p1 = p3 + r[12])
                                a=r 7 a>>= 24 a== 0 if              (if ((r[7] >> 24)==0) )
                                    a=r 7 a<<= 8 r=a 7              (r[7] <<= 8)
                                    a=r 8 a<<= 8 c=r 36 a|=*c c++
                                    r=a 8 a=c r=a 36                (r[8] = r[8] << 8 | *c)
                                endif
                                a=r 12 a<<= 1 r=a 12                (r[12] <<= 1)
                                d=*d a=d r=a 9 a=r 7 a>>= 11 
                                a*=d c=a                            (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                a=r 8 a<c                           (r[14] = r[8] < r[10])
                                if                                  (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                    a= 1 r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a
                                else                                (else r[7] -= r[10], r[8] -= r[10])
                                    a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                    a=r 12 a++ r=a 12               (r[12]++)
                                endif
                                a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                                a=r 12 b=r 17
                            a<b while                               (while (r[12] < r[17]))
                            a-=b r=a 12  b=a                        (r[12] -= r[17])
                            a=r 15 a+=b r=a 15                      (r[15] += r[12])
                            a=r 13 a< 4 ifl                         (if (r[13] < 4) )
                                a+= 7 r=a 13 a= 64 r=a 17 b=a          (r[13] += 7, r[17] = 64)
                                                                    (p3 = 255+49 + (r[15] < 6 ? r[15] : 5) * r[17])
                                a=r 15 a< 6 ifnot a= 5 endif
                                a*=b a+= 255 a+= 49 r=a 34
                                a= 1 r=a 12                         (r[12] = 1)
                                do
                                    b=a a=r 34 a+=b r=a 33 d=a      (p1 = p3 + r[12])
                                    a=r 7 a>>= 24 a== 0 if          (if ((r[7] >> 24)==0))
                                        a=r 7 a<<= 8 r=a 7          (r[7] <<= 8)
                                        a=r 8 a<<= 8 c=r 36 a|=*c c++
                                        r=a 8 a=c r=a 36            (r[8] = r[8] << 8 | *c)
                                    endif
                                    d=*d a=d r=a 9 a=r 7 a>>= 11 
                                    a*=d c=a                        (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                    a=r 8 b= 1 a<c                       (r[14] = r[8] < r[10])
                                    if                              (r[12] <<= 1, if (r[14]) )
                                       a=r 12 a<<=b r=a 12 a=b r=a 14 a=c r=a 7 a=d b=r 28 a-=b d=a (r[7]= r[10], r[11]-= r[28])
                                    else
                                       a=r 12 a<<=b a++ r=a 12 a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8   (r[12]++, r[7]-= r[10], r[8]-= r[10])
                                    endif
                                    a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1=r[9]-(r[11]>>5))
                                    a=r 12
                                    b=r 17
                                a<b while                                  (while (r[12] < r[17]))
                                a-=b r=a 12                                (r[12] -= r[17])
                                r=a 0                                       (r[0] = r[12])
                                a> 3 ifl                                    (if (r[0] > 3) )
                                    a>>= 1 a-- r=a 17 b=a                    (r[17] = (r[12] >> 1) - 1)
                                    a= 1 a<<=b r=a 16                        (r[16] = 1 << r[17])
                                    a=r 12 a&= 1 a|= 2 a<<=b r=a 0           (r[0] = (2 | (r[12] & 1)) << r[17])
                                    a=b a< 6 if                             (if (r[17] < 6) p3 = r[31] + r[0] - r[12])
                                        a=r 31 b=r 0 a+=b b=r 12 a-=b r=a 34
                                    else
                                        d=r 8 do
                                             a=r 7 a>>= 24 a== 0 if        (if ((r[7] >> 24)==0))
                                                a=r 7 a<<= 8 r=a 7         (r[7] <<= 8)
                                                a=d a<<= 8 c=r 36 a|=*c c++
                                                d=a a=c r=a 36             (r[8] = r[8] << 8 | *c)
                                            endif
                                            a=r 16 a>>= 1 r=a 16 c=a 
                                            a=r 7 a>>= 1 r=a 7 b=a         (r[16] >>= 1 r[7] >>= 1)
                                            a=d                            (if (r[8] >= r[7]))
                                            a<b ifnot 
                                                a-=b d=a a=r 0 
                                                a+=c r=a 0                   (r[8] -= r[7], r[0] += r[16])
                                            endif
                                            a=c a-= 16
                                        a> 0 while  a=d r=a 8               (while (r[16] != 16))
                                        a=r 32 r=a 34                       (p3 = r[32])
                                    endif
                                    a= 1 r=a 17 r=a 12                      (r[17] = r[12] = 1)
                                    do
                                        a=r 34 b=r 12 a+=b r=a 33  d=a      (p1 = p3 + r[12])
                                        a=b a<<= 1 r=a 12                   (r[12] <<= 1)
                                        a=r 7 a>>= 24 a== 0 if              (if ((r[7] >> 24)==0) )
                                            a=r 7 a<<= 8 r=a 7              (r[7] <<= 8)
                                            a=r 8 a<<= 8 c=r 36 a|=*c c++
                                            r=a 8 a=c r=a 36                (r[8] = r[8] << 8 | *c)
                                        endif
                                        d=*d a=d r=a 9 a=r 7 a>>= 11 
                                        a*=d c=a                            (r[11] = r[9] = *p1 r[10] = r[9] * (r[7] >> 11))
                                        a=r 8 a<c                           (r[14] = r[8] < r[10])
                                        if                                  (if (r[14]) r[7] = r[10], r[11] -= r[28])
                                            a= 1 r=a 14 a=c r=a 7  a=d b=r 28 a-=b d=a
                                        else                                (else r[7] -= r[10], r[8] -= r[10])
                                            a=0 r=a 14 a=r 7 a-=c r=a 7 a=r 8 a-=c r=a 8
                                            a=r 12 a++ r=a 12 a=r 0 b=r 17 a|=b r=a 0 (r[12]++, r[0] |= r[17])
                                        endif
                                        a=d a>>= 5 b=a a=r 9 a-=b b=r 25 a&=b d=r 33 *d=a (*p1 = r[9] - (r[11] >> 5))
                                        a=r 17 a<<= 1 r=a 17                (r[17] <<= 1)
                                        a=r 12 b=r 16
                                    a<b while                               (while (r[12] < r[16]))
                                endif
                                a=r 0 a++ r=a 0                             (r[0]++)
                            endif
                        endif
                        c=r 15 do
                            a=r 20 d=a b=r 0 a<b a=0 if a=r 23 endif        (r[12] = dict[(r[20] < r[0] ? r[23] : 0) + r[20] - r[0]])
                            a+=d b=r 0 a-=b b=a a=*b r=a 12
                            b=d *b=a b++ a=b r=a 20                         (dict[r[20]++] = r[12])
                            c-- a=c
                        a> 0 while   r=a 15                                 (while (--r[15]))
                    endif                
                    a=r 20 b=r 22
                a<b while                                                   (pos < max_size (r[20] < r[22]))
                    a=r 40 r=a 36
                endif
            endif
            a=r 42
        a> 0 while
        b=0 d=r 20
        do
            a=*b out b++
            a=b
        a<d while
        a= 3 r=a 24
    halt
end
)ZFL2";
