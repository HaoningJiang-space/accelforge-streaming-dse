#define N 16
// Element-wise consumer: each T element is used once at the same (i, j).
void kernel(int (*restrict T)[N], int (*restrict D)[N]) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) D[i][j] = T[i][j] > 0 ? T[i][j] : 0;
}
