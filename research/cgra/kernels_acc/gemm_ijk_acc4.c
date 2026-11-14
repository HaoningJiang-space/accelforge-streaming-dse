#define N 32
// 4 partial accumulators: retaining 4 unfinished outputs breaks the serial add chain.
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict C)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) {
      float s0 = 0; float s1 = 0; float s2 = 0; float s3 = 0;
      for (int k = 0; k < N; k += 4) { s0 += A[i][k + 0] * B[k + 0][j]; s1 += A[i][k + 1] * B[k + 1][j]; s2 += A[i][k + 2] * B[k + 2][j]; s3 += A[i][k + 3] * B[k + 3][j]; }
      C[i][j] += s0 + s1 + s2 + s3;
    }
}
