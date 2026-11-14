#define N 32
// Reduction innermost: C[i][j] can live in a register (accumulator retained, c=2).
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict C)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j)
      for (int k = 0; k < N; ++k)
        C[i][j] += A[i][k] * B[k][j];
}
