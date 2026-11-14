# 推理图普查：已有化简在 decode 与 MoE 上能覆盖多少搜索工作（2026-11-14）

## 问题

已有的正结果（OVERVIEW §4.1）分别消除一种冗余：Unit-M 闭式、Fork 商化（同构分支）、Cut DP 等。M8 FFN 链上不见收益，是因为结构不匹配。本普查检验一个具体假设：

> 真实推理图天然具有这些结构，例如 LLM decode 的 M=1、MoE 的同构专家、SwiGLU 的 gate/up 对称。所以已有化简能覆盖其精确搜索的大部分工作。

**终止条件**（事先给定）：如果在 decode 和 MoE 上，已有化简能覆盖的工作都低于 50%，就说明这条路不成立。

## 设置

- **图**（`decode_census.py`）：用 index-coupling IR 写成的单层推理图，各 rank 的 extent 取 2。
  - `attn_chain`：Q 投影 → QK → softmax → PV → Wo → FFN，是一条纯链，没有分叉和残差。
  - `block_plain`：在上面的基础上加两条残差。
  - `block_full`：完整的 Llama 式 decoder 层，包括 QKV 三路分叉（含当前 token 的 K/V 写入）、两条残差和 SwiGLU。
  - `moe{2,4}`：2 或 4 个激活专家共享输入，输出相加。
  - KV cache（Kc、Vc）没有 M 维，在 IR 中和权重同类。
  - M = 1 对应 decode；M = 2、4 作为对照。
- **基线**：未剪枝的 v2 固定顺序语法，`partitions='dp'`，halving tile，用 `BaselineRecorder` 记录完整调用 DAG。每个案例限 1800 秒、8 GiB。
- **Unit-M 覆盖**：把 `chains.archived(..., unit_rows=True)` 识别出的状态设为终端，统计从根不再可达的独占工作，口径同 CONTRACTION_ORACLE §15。
- **对称性上限**（`symmetry_census.py`）：用 `unified_search.certified_automorphisms` 求出整图自同构，把归档状态映射到它的像。如果像也在归档里、且前沿相等，这个状态就记为冗余，冗余份额 = 每个轨道除第一个成员外的独占工作之和。前沿不等的轨道不计入。这只是上限：固定顺序下，像状态仍可能要由自己的父状态调用。
- **放宽 rank 的上限**：去掉 `chains.recognise` 中"沿链 rank 不重复"的检查后重新统计。这一项只说明结构上的可能性，不代表闭式在放宽后仍然成立。
- 下面所有比例都是 DP 转移（`dp_transitions`），是账本计数，不是墙钟时间。

## 结果

| 案例 | 状态数 | 基线耗时 | Unit-M 闭式 | 放宽 rank 后 | 对称性上限 |
|---|---:|---:|---:|---:|---:|
| attn_chain M=1 | 360 | 0.07 s | 49.0% | 100% | 0 |
| attn_chain M=2 / 4 | 2,652 / 4,990 | 1.8 / 3.7 s | 11.9% / 6.0% | | 0 / 0 |
| block_plain M=1 | 823 | 0.06 s | 17.5% | 29.8% | 0 |
| block_plain M=2 / 4 | 9,554 / 18,432 | 12 / 31 s | 0.4% / 0.2% | | 0 / 0 |
| **block_full M=1** | 2,043 | 0.31 s | **3.1%** | 4.6% | **16.3%** |
| block_full M=2 | 77,161 | 306 s | 0.01% | | 18.6% |
| block_full M=4 | — | — | 8 GiB 内存溢出 | | |
| moe2 M=1 | 896 | 0.27 s | 2.5% | 5.2% | 6.8% |
| moe2 M=2 / 4 | 6,286 / 11,806 | 1.8 / 3.7 s | 0.6% / 0.3% | | 11.8% / 10.8% |
| **moe4 M=1** | 9,778 | 9.3 s | **0.06%** | 0.1% | **46.0%** |
| moe4 M=2 / 4 | — | — | 8 GiB 内存溢出 | | |

## 读法

1. **终止条件触发。** 在完整的 decode 块上，Unit-M 闭式只覆盖 3.1%，对称性上限 16%；在 MoE 上，前者不到 3%，后者最高 46%（4 个专家）。都没有达到 50%。所以"真实推理图天然具有已有化简所需的结构"这个假设不成立。
2. **Unit-M 在真实块上失效，有两个原因：**
   - **rank 重复。** 残差要求 FFN 的输入和输出用同一个 D，attention 的 head 维 A 在 Q→S→O 中重复出现。闭式要求沿链的 rank 各不相同；FFN 小栈每层都用不同的 rank 名，所以绕开了这一点。放宽这条限制后，纯链能 100% 覆盖。
   - **分叉和汇合。** 但在完整块上，放宽后也只有 4.6%。剩下的工作主要落在 QKV 三路分叉（`EQ EK EV`）、SwiGLU 的 `EG EU`，以及跨残差汇合的跨度（如 `EWo ER1 EG EU` 占 25.5%）上，这些都不是链。
3. **对称性随专家数增长**：2 个专家时约 7–12%，4 个专家时 46%（24 个自同构）。这是 Fork 商化唯一有潜力的场景，但 top-k 路由下 decode 实际激活的专家数通常只有 2。
4. **M 才是复杂度的主要来源。** 完整块在 M=1 时只有 2,043 个状态、0.3 秒；M=2 时有 77,161 个状态、306 秒；M=4 在 8 GiB 内跑不完。decode（M=1）在这些 extent 下本身就不难；难的是 M>1，而 Unit-M 恰好不覆盖这部分。

## 结论

真实推理块里，搜索工作的主体在**带共享输入的分叉和残差汇合**，也就是 DAG 区域接口（`dag_mapping/`）的问题，而不在已有化简覆盖的链或同构分支上。这和 D1 及三项 Gate 卡住的位置相同。已有正结果仍然成立，但不能靠"换成推理工作负载"来扩大它们的适用范围。

## 复现

```sh
PYTHONPATH=. python -m research.index_coupling.decode_census OUT_DIR [CASE ...] --seconds 1800 --gib 8   # Linux only
PYTHONPATH=. python -m research.index_coupling.symmetry_census OUT_DIR CASE
PYTHONPATH=. python research/index_coupling/decode_census_attribute.py OUT_DIR CASE   # work by op span
PYTHONPATH=. python research/index_coupling/decode_census_relaxed.py OUT_DIR CASE     # rank-recurrence bound
```

每个案例的汇总在 `results/decode_census/`。调用 DAG 归档太大，没有提交。
