#define N 32
// Same-index fusion pushed into one innermost body: one producer element
// t = dot(A[i,:], B[:,k]) feeds the consumer row update E[i][:] += t * D[k][:].
// Innermost loop shown here is the consumer update (j); this is the streaming form.
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict D)[N],
            float (*restrict E)[N]) {
  for (int i = 0; i < N; ++i)
    for (int k = 0; k < N; ++k) {
      float t = 0;
      for (int m = 0; m < N; ++m) t += A[i][m] * B[m][k];
      for (int j = 0; j < N; ++j) E[i][j] += t * D[k][j];
    }
}
