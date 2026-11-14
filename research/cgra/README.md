# CGRA 方向：E-C1 冒烟实验（CGRA-Mapper）

状态（2026-11-14）：工具链打通；只跑了 GEMM 单循环。2mm 融合**尚未测到**（见“限制”）。

## 设置

- 工具：[tancheng/CGRA-Mapper](https://github.com/tancheng/CGRA-Mapper) `f5eeba75`，基于官方 LLVM 12.0.1 预编译包构建。
- 构建与运行位置：实验服务器上的 `graph_cgra_llvm12`、`graph_cgra_mapper_f5eeba75`、`graph_cgra_sweep_f5eeba75`。
- 阵列：4×4 和 8×8 mesh，`bypassConstraint=4`，`regConstraint=8`，启发式映射。只有一条边上的 `dim` 个 PE 可以 load/store。
- 编译流程：`clang -O2 -fno-vectorize`，然后把 `llvm.loop.unroll.disable` 元数据去掉（`-fno-unroll-loops` 会写入它，导致 `opt` 拒绝 unroll），再用 `opt -loop-unroll -unroll-count=u` 展开。
  - `sweep.sh`：展开后不做清理。
  - `sweep3.sh`：展开后再跑 `-instcombine -early-cse`。
- 指标：每个 MAC 的周期数 = II /（每次迭代的 MAC 数）。

## 结果（`results/sweep_cleanup_unroll.txt`）

表中 MII 是 mapper 自己算的 `max(ResMII, RecMII)`，它不考虑访存端口。

| kernel | u | MAC/迭代 | MII | 实际 II（4×4 / 8×8） | 周期/MAC（4×4 / 8×8） |
|---|---|---|---|---|---|
| gemm_ijk（归约维在最内层） | 1 | 1 | 2 | 4 / 4 | 4 / 4 |
| gemm_ijk | 4 | 4 | 5 | 7 / 7 | 1.75 / 1.75 |
| gemm_ikj（输出维在最内层） | 1 | 1 | 2 | 4 / 4 | 4 / 4 |
| gemm_ikj | 4 | 4 | 3 / 2 | 4 / 4 | **1.0 / 1.0** |
| gemm_ijk_acc4（4 个部分和） | 1 | 4 | 3 | 10 / 14 | 2.5 / 3.5 |
| gemm_ijk_acc4 | 4 | 16 | 8 / 5 | 21 / 20 | 1.31 / 1.25 |

## 观察

1. **默认写法与最佳组合之间差 4 倍**：默认写法是 ijk、u=1，每个 MAC 4 个周期；最佳是 ikj、u=4，每个 MAC 1 个周期。E-C1 定的"中位差距 < 1.2× 就停"这条线没有触发。
   - 但最佳组合用经典规则就能找到：把不是归约维的循环放到最内层，再展开。这条规则 PolyMAP 和 DATE'15 都已经覆盖。所以单算子的结果（C1）目前**看不出新意**。
2. **展开后若不清理，RecMII 是假的**：不清理时，ikj 的 RecMII 随 u 涨到 u+1，原因是归纳变量的加法被串成了一条链。清理后 ikj 的 RecMII 固定为 2。
   - 这说明"默认工具链"的结果很依赖 pass 顺序。工具链评测论文（arXiv 2502.19114）抱怨的"没有自动展开"，其中一部分其实就是这个原因。
3. **mapper 算出的 MII 和实际 II 偏差很大**：acc4 在 8×8 上，MII 是 3，实际 II 是 14，差 4.7 倍；而且 8×8 反而比 4×4 更差。
   - 启发式映射加布线带来的损失，比访存端口和递归约束都更大。
4. **访存端口从来不是瓶颈**：MemMII（load/store 数除以访存 PE 数）始终小于实际 II，最大的一组是 acc4、u=4、4×4，MemMII 8，实际 II 21。所以"超图角色决定访存 MII"这个假设，在当前规模的 GEMM 上没有观察到效果。
5. **多个部分和（每个累加器占 c=2 的容量）比直接展开 ikj 更差**：DFG 节点数翻倍以后，布线损失把打断递归链的收益吃掉了。

## 限制

- CGRA-Mapper 每次只映射**一个最内层循环**（`targetLoopsID` 先选外层循环，再取它的第 0 个子循环）。所以 `mm2_*` 实际只映射了生产者的点积，数字和 gemm_ijk 完全相同。C2（多算子流式融合）要么用 `targetNested`，要么改用 Neura 的多 kernel 模式。
- 只有 N=32、float、单一 mesh 配置；启发式映射，没有跑穷举映射。
- 周期数只看 II，没有计入流水线填充，也没有计入外层循环的开销。
