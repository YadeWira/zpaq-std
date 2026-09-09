#ifndef ZPAQ_STD_DIVSUFSORT_H
#define ZPAQ_STD_DIVSUFSORT_H

/// libdivsufsort-lite: construccion de arreglo de sufijos (BWT).
/// Ver libdivsufsort/divsufsort.cpp por que esta en su propio namespace.

namespace divsuf
{
/// Construye en SA el arreglo de sufijos de T[0..n-1]. Devuelve 0 si anduvo,
/// -1 argumentos invalidos, -2 sin memoria.
int divsufsort(const unsigned char *T, int *SA, int n);
} // namespace divsuf

#endif // ZPAQ_STD_DIVSUFSORT_H
