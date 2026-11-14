#define N 32
// 2 partial accumulators: retaining 2 unfinished outputs breaks the serial add chain.
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict C)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      float s0 = 0; float s1 = 0;
      for (int k = 0; k < N; k += 2) { s0 += A[i][k + 0] * B[k + 0][j]; s1 += A[i][k + 1] * B[k + 1][j]; }
      C[i][j] += s0 + s1;
    }
}
