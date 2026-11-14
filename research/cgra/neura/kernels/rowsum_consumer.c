#define N 16
// Row-reduction consumer: reduces over the producer's output index j; each T element used once.
void kernel(int (*restrict T)[N], int *restrict r) {
  for (int i = 0; i < N; ++i) {
    int s = 0;
    for (int j = 0; j < N; ++j) s += T[i][j];
    r[i] = s;
  }
}
