#define N 16
// Fused: two live accumulators (the row sum and the dot product); T is never stored.
void kernel(int (*restrict A)[N], int (*restrict B)[N], int *restrict r) {
  for (int i = 0; i < N; ++i) {
    int rs = 0;
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      rs += s;
    }
    r[i] = rs;
  }
}
