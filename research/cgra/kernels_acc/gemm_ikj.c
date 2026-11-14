#define N 32
// Output index innermost: A[i][k] is invariant (input retained, c=1); C streams.
void kernel(float (*restrict A)[N], float (*restrict B)[N], float (*restrict C)[N]) {
  for (int i = 0; i < N; ++i)
    for (int k = 0; k < N; ++k)
      for (int j = 0; j < N; ++j)
        C[i][j] += A[i][k] * B[k][j];
}
