/*
  ZPAQLZ6: the decoder of zpaq-std -ma:lz6 blocks, written in ZPAQL. zpaq-std, 2026.

  lz6 (github.com/YadeWira/lz6) writes its frozen "portable profile" for -ma:lz6:
  the LZ5 v1.5 raw block format. Up to 65.4m-pre42 those blocks carried ZPAQLZ5,
  the -ma:lz5 decoder, byte for byte. From pre43 on lz6 has its own program, so
  that lz5 and lz6 no longer share a decoder: if one of them ever needs a new one,
  the other is not touched.

  It decodes exactly what ZPAQLZ5 decodes (streamed, one byte at a time, the
  window is M = 2^pm, declared in the block header). The only difference is the
  match copy loop, which counts with register d instead of r3. That is what
  makes the bytecode different, and it has to be: pre24 to pre42 recognise
  ZPAQLZ5's bytecode and skip the ZPAQL; with a tag they do not know, they would
  hand back the compressed bytes. With a bytecode they do not know, they run this
  program and get the data right. Same speed as ZPAQLZ5 (measured).

  Verified with zpaqd 7.15 on lz6's 23 test vectors (fast and HC, windows 2^16
  to 2^24), identical to ZPAQLZ5's output.

  FROZEN, like the other portable decoders.
*/
static const char ZPAQLZ6_CUERPO[] = R"ZLZ6(hcomp
  halt
pcomp zpaqlz6 ;
  a> 255 if
    a=0 b=a r=a 1 r=a 2 r=a 3 r=a 4 r=a 6 r=a 7 r=a 8 r=a 9
    halt
  endif
  d=a
  a=r 9 a== 0 if
    a= 1 r=a 5 r=a 9
  endif
  a=r 1
  a== 0 ifl
    a=d r=a 6
    a&= 7 r=a 3
    a=d a>>= 6 a== 0 if
      a=d a>>= 3 a&= 7 r=a 2
      a== 7 if a= 1 r=a 1 else a= 6 r=a 1 endif
    else
      a=d a>>= 3 a&= 3 r=a 2
      a== 3 if a= 1 r=a 1 else a= 6 r=a 1 endif
    endif
  elsel
    a== 1 ifl
      a=r 2 a+=d r=a 2
      a=d a== 255 ifnot a= 6 r=a 1 endif
    elsel
      a== 2 ifl
        a=d *b=a out b++
        a=r 2 a-- r=a 2
        a== 0 if a= 7 r=a 1 endif
      elsel
        a== 3 ifl
          a=r 4 a+=d r=a 4
          a= 8 r=a 1
        elsel
          a== 4 ifl
            a=d c=r 8 a<<=c c=a a=r 4 a+=c r=a 4
            a=r 8 a+= 8 r=a 8
            a=r 7 a-- r=a 7
            a== 0 if a= 8 r=a 1 endif
          elsel
            a=r 3 a+=d r=a 3
            a=d a== 255 ifnot a= 9 r=a 1 endif
          endif
        endif
      endif
    endif
  endif
  do
    a=r 1
    a== 6 ifl
      a=r 2 a== 0 if a= 7 r=a 1 else a= 2 r=a 1 endif
    elsel
      a== 7 ifl
        a=r 6 a>>= 7 a== 1 ifl
          a=r 6 a>>= 5 a&= 3 a<<= 8 r=a 4
          a= 3 r=a 1
        elsel
          a=r 6 a>>= 6 a== 0 ifl
            a=0 r=a 4 r=a 8 a= 2 r=a 7 a= 4 r=a 1
          elsel
            a=r 6 a>>= 5 a== 2 ifl
              a=0 r=a 4 r=a 8 a= 3 r=a 7 a= 4 r=a 1
            elsel
              a=r 5 r=a 4 a= 8 r=a 1
            endif
          endif
        endif
      elsel
        a== 8 ifl
          a=r 4 r=a 5
          a=r 3 a== 7 if a= 5 r=a 1 else a= 9 r=a 1 endif
        elsel
          a== 9 ifl
            a=r 3 a+= 3 d=a
            a=b c=r 4 a-=c c=a
            do
              a=*c *b=a out b++ c++ d--
              a=d
            a> 0 while
            a=0 r=a 1
          endif
        endif
      endif
    endif
  a=r 1 a> 5 while
  halt
end
)ZLZ6";
