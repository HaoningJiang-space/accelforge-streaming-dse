#define N 16
// Fused: the finished accumulator goes straight to the consumer; T is never stored.
void kernel(int (*restrict A)[N], int (*restrict B)[N], int (*restrict D)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      D[i][j] = s > 0 ? s : 0;
    }
}
