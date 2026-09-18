# Los `.cu` de bsc se quitaron; los `.cuh` NO

bsc trae soporte CUDA opcional (`libcubwt` para el BWT en GPU, `st.cu` para el
sort transform). zpaq-std **nunca lo compila**: `LIBBSC_CUDA_SUPPORT` no se define
en ningún lado, no hay `nvcc` en el Makefile, y el binario no tiene un solo
símbolo CUDA ni enlaza librería alguna de CUDA.

Se quitaron las dos **implementaciones**, que no se compilaban:

    compressors/bsc/bwt/libcubwt/libcubwt.cu   (~130 KB)
    compressors/bsc/st/st.cu                   (~50 KB)

**Los headers `.cuh` se quedan y no se pueden borrar**: `bwt.cpp:41` y
`st.cpp:43` los incluyen SIN guard de preprocesador. El código CUDA que declaran
está detrás de `#ifdef LIBBSC_CUDA_SUPPORT` y por eso nunca se compila, pero el
`#include` se evalúa igual. Borrarlos rompe el build; verificado.

Consecuencia para quien re-vendorice bsc: esta copia ya NO es idéntica a upstream.
Si se actualiza, o se vuelven a traer los `.cu`, o se re-aplica este recorte.
Nada más está tocado.
