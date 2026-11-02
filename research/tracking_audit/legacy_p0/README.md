# Legacy P0 scripts

Join profiling and CPU-vs-GPU Pareto microbenchmarks from the first profiling round.
They were written against upstream `04cf894e` (not tag1) and import its module layout,
so they do not run on this branch as is. They are kept for reference only.

- `p0_profile.py`: serial join with timing hooks; dumps the largest Pareto inputs.
- `p0_bench.py`: CPU numba SFS vs a CuPy rank-transform kernel on those dumps (at most 32 dims).
- `p0_diag.py`: explains CPU/GPU mask differences with an exact check on mismatched rows.
- `sumprof.py`: summarizes `profile.json` files from `p0_profile.py`.
