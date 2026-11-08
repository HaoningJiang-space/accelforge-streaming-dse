# 本地 DAG 边界与容量分析

2026-11-08。本轮实际运行了 22 个实例，21 个得到全拓扑序范围内的精确结果；
12 分支实例达到 50,000 个前缀状态的限制，仅报告合法顺序上界。
分析总耗时约 12.68 秒（本机单次测量，不是性能 benchmark）。
完整输入图、各目标的最优顺序、逐步活跃集合与数值均在
[results/local.json](results/local.json)。

## 结果

以下容量都是 activation bytes，KiB = 1024 B、MiB = 1024² B。
每一列分别优化，不能假定各列最小值属于同一个执行顺序。

| 图 | 最优切口活跃张量数 | 最优切口字节峰值 | 最优算子执行字节峰值 |
| --- | ---: | ---: | ---: |
| 仓库 GLU | 2 | 96 KiB | 144 KiB |
| 仓库 diamond | 2 | 144.75 KiB | 217.125 KiB |
| 仓库 residual | 2 | 257 KiB | 353.375 KiB |
| 仓库 asymmetric | 2 | 168.875 KiB | 241.25 KiB |
| ResNet identity，1 / 4 / 16 blocks | 2 | 1568 KiB | 2352 KiB |
| U-Net，深度 2 / 4 / 6 / 8 | 3 / 5 / 7 / 9 | 均为 8 MiB | 均为 16 MiB |
| Attention，16 tokens，1 / 4 blocks | 3 | 24 KiB | 28 KiB |
| Attention，128 tokens，1 / 4 blocks | 3 | 384 KiB | 576 KiB |
| Attention，512 tokens，1 / 4 blocks | 3 | 4.5 MiB | 8.25 MiB |
| 2 / 4 / 8 分支 concat | 2 / 4 / 8 | 68 / 70 / 74 KiB | 69 / 71 / 75 KiB |
| 6 分支，故意使用 breadth-first 原始顺序 | 6 | 72 KiB | 73 KiB |

12 分支的原始合法顺序给出 12 个活跃张量、78 KiB 切口峰值、79 KiB 执行峰值，
但前缀 DP 没有完成，不把这些数值标为求解器证明的最优值。

最直接的顺序优化证据来自 6 分支对照：原始顺序先生成所有宽中间量，
切口峰值 384 KiB；优化后按 `wide0,end0,wide1,end1,...,merge` 执行，降为 72 KiB，
降低 81.25%。两种顺序的峰值张量数都是 6。
这说明只优化张量个数不足以优化容量；张量大小与消费顺序有实际作用。

## 对研究方向的含义

1. 重复 block 没有必然增加边界规模：这里 ResNet 从 1 增至 16 blocks，
   attention 从 1 增至 4 blocks，最优活跃张量数均不变。
   这是继续做边界状态 DP 的具体结构依据。
2. 不能把真实网络的边界规模先验写成 4–6：构造的深 U-Net 已达到 7 和 9，
   多分支 concat 达到 8。需要对这些结构采用分层处理或控制状态属性数。
3. 无权边界规模和容量压力可以脱钩。Attention 的 k 不变，序列长度却显著改变容量；
   本轮 U-Net 的 k 随深度增长，字节峰值却由最高分辨率 decoder 控制、保持不变。
4. 最值得接下来的实验是把 6 分支的两种顺序、ResNet 和 attention 的最优顺序
   送入实际 tile/lifetime 成本模型，检验哪些结构收益在 tiling 后仍然存在。
   这轮没有运行 FFM 容量扫描，也没有证明架构偏好会在这些数值处翻转。

## 测量口径

- 一个算子产生一个独立、完整 materialized 的张量；不做融合、重算、spill、in-place 或 alias。
- 外部 activation 在首次使用时进入，直到最后一个消费者结束才释放。
  这样既不会把尚未使用的输入全部预装，也不会漏掉残差 X。
- 内部张量从生产完成一直保留到最后使用；终端输出在算子完成后立即 drain。
  drain 的流量、时间未建模。独立终端输出不要求一起保留到图结束。
- `live_tensors`：算子完成后的切口上仍有未来消费者的唯一张量数。
  共享给多个消费者的张量只计一次。
- `internal_crossing_edges`：内部 producer 已完成、consumer 尚未完成的 tensor-use 边数。
  不包含外部输入边，不能与上一项混称为 cutwidth。
- `cut_bytes`：上述活跃张量的字节和。
- `event_bytes`：当前活跃张量、算子输入及新输出的集合大小之和；
  输入在输出分配之前不能释放。这个区别在 ResNet 和 concat 上尤其明显。
- 字节数排除了权重、workspace、DMA staging、bank 限制与碎片。
  `event_bytes` 是该抽象存储模型中所需的峰值，**不是任意 tiled mapping 的容量下界**；
  融合/tiling 可以减少它，实际硬件额外缓冲可以增加它。

## 图来源与覆盖范围

4 个实例来自仓库 `research.runtime.dag_cases.CASES`，使用其真实 rows/widths，
并显式选择 FP16 activation。其余 18 个是脚本中透明构造的结构实例：

- ResNet identity bottleneck 与仓库 INT8、56×56、256→64→64→256 的形状一致，
  重复 1、4、16 次；没有加入 BN/ReLU，也没有 stage 下采样。
- U-Net 使用 FP16、256×256×32 起始 activation，下采样时空间面积减四、通道翻倍，
  activation bytes 减半；decoder 有显式 upsample、concat、conv。
- Attention 为 FP16、hidden=256、heads=8 的 Q/K/V→score→softmax→AV→projection→residual；
  没有 MLP、norm，不代表完整 transformer 导出图，也不代表 FlashAttention 的存储行为。
- 多分支实例是 all-branch concat，不能当作真实动态 MoE 测量。

本机没有 torch/torchvision。本轮不是 30–50 个真实模型的 torch.fx/ONNX 调查，
没有测频繁子图覆盖率，也没有由重复构造推断“前 10 个 motif 覆盖 80%”。

## 算法与验证

按已执行算子集合（合法拓扑前缀/ideal）做 minimax DP。
在无 spill、无重算的本轮规则下，集合决定活跃张量和后续可执行算子。
对每个目标独立维护最小的历史峰值及回溯指针；转移取 `max(历史峰值, 当前值)`。
完成全部层后获得该目标在所有拓扑顺序中的最小峰值，并回放 witness 验证。
保存的四个最小值是四次独立优化，不是联合 Pareto 前沿。

前缀数仍可能指数增长；这个实现没有给出以边界宽度为参数的 FPT 算法或证明，
更没有由这次结构测量推出完整 architecture–mapping 优化的复杂度结论。
12 分支达到状态限制是实际观察到的搜索增长。

验证：4 项测试通过，包括 12 个固定随机种子的小 DAG，使用独立的区间生命周期计算，
穷举全部合法顺序对比四个最优值；另外对四个仓库 DAG 的执行容量峰值，
与现有 `dag_model.lifetimes` 交叉验证。还测试共享外部输入和状态上限。

从仓库根目录运行（Python 3.10+；分析只依赖标准库）：

```powershell
& 'C:/Users/hjiangbq/.codex/envs/accelforge/python.exe' -m pytest -q research/graph_structure/test_analyze.py
& 'C:/Users/hjiangbq/.codex/envs/accelforge/python.exe' -m research.graph_structure.analyze
```

默认结果写入 `research/graph_structure/results/local.json`。
可用 `--output` 改路径、`--state-limit` 改前缀状态预算。运行时间随机器变化。
