#define N 32
// T = A*B then E = T*D, fused along i. The consumer reads T[i][k] with the same row index:
// the producer's row can be consumed without a full-matrix buffer.
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict D)[N],
            float (*restrict E)[N]) {
  for (int i = 0; i < N; ++i) {
    float t[N];
    for (int j = 0; j < N; ++j) {
      float s = 0;
      for (int k = 0; k < N; ++k) s += A[i][k] * B[k][j];
      t[j] = s;
    }
    for (int j = 0; j < N; ++j) {
      float s = 0;
      for (int k = 0; k < N; ++k) s += t[k] * D[k][j];
      E[i][j] = s;
    }
  }
}
