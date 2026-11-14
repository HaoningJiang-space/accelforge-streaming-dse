#define N 16
// Producer alone: T = A * B.
void kernel(int (*restrict A)[N], int (*restrict B)[N], int (*restrict T)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      int s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      T[i][j] = s;
    }
}
