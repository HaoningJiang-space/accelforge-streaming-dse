#define N 16
void kernel(int (*restrict A)[N], int (*restrict B)[N], int (*restrict T)[N], int *restrict r) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      T[i][j] = s;
    }
  for (int i = 0; i < N; ++i) {
    int s = 0;
    for (int j = 0; j < N; ++j) s += T[i][j];
    r[i] = s;
  }
}
