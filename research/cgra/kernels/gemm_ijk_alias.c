#define N 32
// No restrict: the accumulator cannot be promoted, so it is reloaded and stored each iteration.
void kernel(float (*A)[N], float (*B)[N], float (*C)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j)
      for (int k = 0; k < N; ++k)
        C[i][j] += A[i][k] * B[k][j];
}
