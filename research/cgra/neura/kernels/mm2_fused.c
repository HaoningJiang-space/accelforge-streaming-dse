#define N 16
// Fused along i with a one-row buffer: the reused intermediate still goes through memory.
void kernel(int (*restrict A)[N], int (*restrict B)[N], int (*restrict D)[N], int (*restrict E)[N]) {
  for (int i = 0; i < N; ++i) {
    int t[N];
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      t[j] = s;
    }
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += t[k] * D[k][j];
      E[i][j] = s;
    }
  }
}
