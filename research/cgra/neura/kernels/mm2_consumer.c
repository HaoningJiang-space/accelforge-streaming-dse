#define N 16
// Matmul consumer: each T[i][k] is reused N times (once per j).
void kernel(int (*restrict T)[N], int (*restrict D)[N], int (*restrict E)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += T[i][k] * D[k][j];
      E[i][j] = s;
    }
}
