#define N 16
// Producer and element-wise consumer as two loop nests in one function.
void kernel(int (*restrict A)[N], int (*restrict B)[N], int (*restrict T)[N], int (*restrict D)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      T[i][j] = s;
    }
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) D[i][j] = T[i][j] > 0 ? T[i][j] : 0;
}
