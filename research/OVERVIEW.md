# AccelForge：整体进度与收束决策

审阅日期：2026-11-10（本地日期）。主线快照 `2c8050c6`；独立 DNN/硬件接入快照
`5245c9cc`。本文核对各研究目录、结果报告和研究分支，汇总已有证据；没有重跑整库
实验，也没有改变冻结协议或求解器。本文是当前研究优先级入口，旧文档的“下一步”
保留为历史建议，不能同时视为待执行计划。

## 1. 研究现在走到了哪里

最初目标是架构–映射联合优化。当前最扎实的成果是：**在明确的执行语法下，建立
条件容量–流量响应的精确语义，并证明某些结构允许分解、状态合并或解析替换。**
从它到通用真实 DNN Mapper、再到硬件延迟/能耗收益，中间仍有未完成的环节。

因此，当前主问题收束为：

> 固定执行语法后，哪些边界信息足以精确组合容量–流量响应？哪些图与循环结构
> 能让这种组合减少实际搜索工作，哪些不能？

“充分接口”已有具体结果；“最小接口”、一般 DAG 的复杂度上界和真实 DNN 的
稳定端到端加速仍未建立。DP、对称性和下界本身不是新颖性主张；需要对照文献确认
图映射中特有的循环、驻留与生命周期契约是否构成新贡献。

目前最重要的收束决定：**暂停新增搜索优化路线，先把已有结论组织为一个可审阅、
可复现的论证。** 不把每次失败后的开放问题自动升级为下一项工程。

## 2. 整个 research 目录的地图

| 阶段 / 目录 | 已完成的工作与价值 | 现在的定位与限制 |
| --- | --- | --- |
| [streaming_join](streaming_join/README.md)、[tracking_audit](tracking_audit/README.md) | 原生 FFM/Join、容量跟踪、候选覆盖、缓存和重定向审计；修复整数容量与 Attention 循环匹配等实际错误 | 正确性与基线资产。多种复用方法减少工作却未胜过强缓存基线；旧版本时间不能用于当前头条 |
| [graph_coopt](graph_coopt/README.md)、[joint_search](joint_search/README.md) | 图索引 Memo、条件组合、有限硬件域的精确候选与来源追踪 | 建立执行与来源契约；不等于发现通用跨架构搜索压缩 |
| [joint_synthesis](joint_synthesis/README.md) | 独立 2mm 语法，布局/驻留接口与显式转换；29,952 个完整计划核对，六维需求前沿精确 | 完整物化边界下的组合示例；83–84% 配对减少不是原生 FFM 加速或一般融合定理 |
| [motivation](motivation/README.md)、[late_binding](late_binding/README.md) | 检验物化近似选错硬件、mapping-first 与 architecture-first 的差异 | 动机与有限候选库对照。强 shortlist 会消除部分大收益，不能只引用最弱基线 |
| [physical_cost](physical_cost/README.md)、[runtime](runtime/README.md)、[joint_budget](joint_budget/protocol.py) | CACTI SRAM 成本、两阶段需求、驻留、地址/Bank 日历、预取和有限预算实验 | 已有物理模型与 EDP 证据，并非“完全没有硬件实验”；但它们是独立的有限语法，尚未接通当前 index solver |
| [graph_structure](graph_structure/README.md)、[structure_prediction](structure_prediction/README.md) | 图顺序/活跃峰值与简单摘要的冻结检验；10 个导出真实模型的原顺序已最优 | 将问题从重排和标量图分数转向循环–驻留耦合；不是所有真实图都低宽度 |
| [index_coupling](index_coupling/STATUS.md)、[response](index_coupling/response/README.md) | 条件资源语义、Cut DP、置换等价、解析响应、独立回放、失败边界 | 当前科学主线；正面结果集中在具有已证明结构的受限族 |
| [DNN 分支](https://github.com/HaoningJiang-space/accelforge-streaming-dse/tree/5245c9cc/research/dnn_benchmarks)、[workloads](workloads) | 实际 FX 子图、GEMM Mapping 导入和模拟器审计；workloads 保存输入规格 | 外部有效性检查。完整模型扩展与可信硬件时间评价仍未完成 |

这不是同一个优化器逐步积累的统一性能曲线。原生 FFM、独立物理计划语法、图求解器、
PyTorchSim 有不同的合法映射与计价，必须分别标注。

## 3. 必须统一的口径

| 口径 | 可以回答什么 | 不能直接与什么混用 |
| --- | --- | --- |
| 固定顺序图语法 v1 | 原冻结 P19/P21 等预测在原语法下是否成立 | v2 改变了合法叶子计划，不能事后覆盖旧判定 |
| 固定顺序图语法 v2 | 条件响应、驻留单调性及后续下界/闭式替换 | 不等于允许任意 consumer 重排 |
| Order-complete Fork / unified study | 在声明的合法顺序集合上证明置换等价与联合化简 | 9.80× Fork 结果不是固定顺序默认 solver 的同一实验 |
| 原生 FFM / 独立物理模型 | 各自声明的 Tile、物理资源、能量与时间 | 不能用其 EDP 证明 index solver 的 `(C,Q)` 优化更快 |
| PyTorchSim 导入 | 已编译 Mapping 的数值、DMA 和物理分配是否正确 | 当前失败未闭合，不能接受其 cycles 为性能收益 |

条件响应至少要说明子图、tile extents、驻留身份、write ownership、`solve/group`
入口、边界保留/释放契约以及合法执行集合。`Q` 是总流量还是额外流量，`C` 是否已扣除
调用者驻留，也必须显式说明。这是一组现有接口要求，不是一般图的最小状态定理。

所有效率比较至少区分：独立状态、转移与合并工作、表示构造开销、前沿搜索时间、
可执行 witness 生成时间和内存。回放验证时间另列。离线不可达工作比例不是在线加速。

## 4. 可以进入主论证的成果

| 结论 | 已有证据 | 必须保留的限定 |
| --- | --- | --- |
| 循环义务与条件驻留语义 | [FIRST_PRINCIPLES](index_coupling/FIRST_PRINCIPLES.md)、[契约核对](index_coupling/PLAN_CONTRACT_REVIEW.md)：共同循环合法秩、输入重读/部分和溢出、所有权和调用者容量 | 语法精确性不等于任意物理调度最优；部分候选界仍未证明 |
| 正确边界下可精确组合 | [Cut DP](index_coupling/SOLVER_SCALING_RESULTS.md)：与枚举相等，8 算子残差对照中位加速 8.6× | 解决划分层，不消除外层循环带来的全部驻留上下文 |
| 语义保持的对称性允许取商 | [Fork](index_coupling/FORK_QUOTIENT_RESULTS.md)：同构六消费者 106,604→6,092 响应条目，9.80× 中位时间比 | Order-complete 语法；联合驻留类型不可拆成独立计数；一般 DAG 无此规模结论 |
| 三类化简能在同一语法中协作 | [Unified search](index_coupling/UNIFIED_SEARCH_RESULTS.md)：部分对称且下游汇合的六算子族，24 arms、1,018,272 条内部响应比较、228 次精确回放 | 两个非退化案例约 4.74×/4.34×；这是受限统一实例，不是通用 DNN 框架已完成 |
| v2 恢复驻留单调性 | [v2](index_coupling/GRAMMAR_V2_RESULTS.md)：归档中 578 次违反降到 0；291 个根前沿点回放 | 19/48 根曲线改变；默认 v1 与冻结结论不能悄悄改成 v2 |
| 某些完整条件响应可直接求解 | [Contraction oracle](index_coupling/CONTRACTION_ORACLE.md)、[response](index_coupling/response/README.md)：unit-M 链及单收缩响应；原 FFN-4 前沿搜索 6.81×；随后完整原生映射生成补测 FFN-4/注意力-4 为 6.60×/6.70× | 新计时包含 witness 恢复，安装与回放另列；M8 完整生成 0.84×/0.97×，仍无收益 |
| 接口差别有独立检验 | [双收缩审计](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/14a06502/research/index_coupling/TWO_CONTRACTION_INTERFACE_RESULTS.md)：208 条完整曲线、4,000 个容量点、571 次带调用者的回放 | `solve` 与 `group` 不可替换；仍是受限条件族，不是任意链闭式 |

最合适的论文骨架不是一串优化开关，而是：**条件接口 → 语义保持的化简原则 →
三个已验证实例 → 适用边界与失败解释。** 宽泛的架构联合优化是动机，不宜作为已经
完成的头条承诺。

### 4.1 每项加速消除的是哪一种冗余

已有加速都没有被推翻。每一项只消除一种特定冗余，所以只在这种冗余占主导的图上
出现。M8 上看不到它们，有两个原因：

- 前面的成果已并入后来的基线。后续实验均以 `partitions='dp'`（Cut DP）为基线。
- M8 的主要工作来自尚未被现有化简覆盖的驻留上下文；这些计算是否冗余仍需证明。

| 化简原则 | 消除的冗余 | 实测（中位时间比，搜索结果一致、witness 回放） | 测试图族 | 为何在 M8 FFN/注意力上不再出现 |
| --- | --- | --- | --- | --- |
| [Cut DP](index_coupling/SOLVER_SCALING_RESULTS.md) | 划分方案的枚举 | 8.64× | 8 算子残差对照 | 已是 M8 及后续所有实验的基线 |
| [Fork 商化](index_coupling/FORK_QUOTIENT_RESULTS.md) | 同构分支的重复响应 | 9.80×；响应条目 106,604→6,092 | 六个同构消费者的 fork | 链式 FFN/注意力没有同构分支 |
| [统一搜索](index_coupling/UNIFIED_SEARCH_RESULTS.md) | 上述化简与下界在同一语法内协作 | 4.74× / 4.34× | 部分对称、下游汇合的六算子族 | 同上；不是通用 DNN 框架 |
| [标量桥](index_coupling/SCALAR_BRIDGE_RESULTS.md) | 标量子问题的重复求解 | 3.24× / 3.68× | fork 族（all-k、kkk/iii） | 三对计时，无一般保证 |
| [Unit-M 闭式替换](index_coupling/CONTRACTION_ORACLE.md) | 可解析 M=1 条件子树的搜索 | 历史前沿 6.81×；完整生成补测 6.60× / 6.70× | 小 FFN-4 / 注意力-4 | FFN-4 中约 99.8% 的 DP 转移可由 M=1 替换移除，M8 中仅约 30% |
| [Remainder 复用](index_coupling/REMAINDER_SEARCH_RESULTS.md) | 同构剩余子问题 | 祖先对照 4.08×；precheck 1.31/1.23/1.11× | 祖先对照、三个 stack | P19 服务器 12/12 受内存限制失败 |
| [实现常数改进](index_coupling/SPAN_SCALING_RESULTS.md) | 常数开销，不减少递归状态 | 1.19× | tiny dense fork | 不属于结构性化简 |

M8 保留了大量 M>1 状态的工作。忽略驻留集合、每个 key 只计算一次的假想核算可减少
84–88% 的 DP 工作；这不是单独 M>1 状态占比（见第 5 节的限定）。不同驻留集合的
曲线形状多数不同，并通过外层保留共享同一容量，
上述原则都不针对这一类。最近的负面结果因此标定的是**现有化简原则的适用边界**，
不否定前面的正例。

两点限定：

- 上表全部来自受控图族。真实子图研究中，完成的任务没有一致的搜索加速（见第 6 节）。
- 各项倍数不能相乘。一个工作负载只能获得它实际具有的那种结构带来的收益。

## 5. 应停止扩展、保留为边界证据的路线

| 路线 | 当前结论 | 收束决定 |
| --- | --- | --- |
| 单个图分数、简单切口族、局部宽度预测全部复杂度 | P19 曲线交叉、P21d 等失败；[width study](index_coupling/WIDTH_RESULTS.md) 中 local obligation width=1 仍有 `3^k` solve keys | 保留反例，停止以这些指标宣称层数线性扩展 |
| 简单 C2 与逐边更强下界 | [C2](index_coupling/C2_BOUND_RESULTS.md)、[算子投影](index_coupling/CONTRACTION_ORACLE.md)：M8 大量共享子状态；算子界只消除约 2–3% 原 DP 工作 | 暂停继续增加局部界；保留证明与诊断 |
| Sandwich 整状态替换 | [结果](index_coupling/SANDWICH_RESULTS.md)：认证均精确，M8 增量 DP 节省 11.3/4.4 个百分点，未达冻结门槛 | 按原规则停止，没有在线版本；不能改用更好看的 loop-choice 比例改判 |
| Prefix dominance 与完整 Loop Closure | [Prefix](index_coupling/PREFIX_DOMINANCE_RESULTS.md) 大多重复已有 Pareto 消除；[Closure](index_coupling/LOOP_CLOSURE_RESULTS.md) 49 个根点精确，但 M8 原生 witness 生成时间比仅 0.613×/0.727× | 正确分解不代表高效表示；停止增加层数或为此继续优化实现 |
| 廉价跨 Residency 共享 | [最新分析](index_coupling/RESIDENCY_SHARING.md)：gap 不恒定、存在远距交互、M>1 多数曲线不能只平移 | 三种具体复用结构未成立；不据此启动通用 symbolic solver |
| 一般 remainder 规范化作为默认加速 | [本地](index_coupling/REMAINDER_SEARCH_RESULTS.md) 正负混合；[P19 服务器](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc/research/dnn_benchmarks/P19_SERVER_RESULTS.md) remainder 12/12 受内存限制失败，precheck 慢 15.7%/18.4% | 保留等价性结果及局部正例，不宣称普遍时间/内存收益 |
| 限制顶层融合组至多 2–3 个算子 | [§19 诊断](index_coupling/CONTRACTION_ORACLE.md)：M8-2 的 U_3 总覆盖 2,038/2,211，但真正长于三算子的状态仅 20/193 相等，覆盖该层 7.11% 的独占 DP 工作 | 诊断已完成，不转为新求解器；共同逐行循环可跨长链而只需两个局部激活单元，组跨度不是物理耦合宽度 |
| 固定 M→1 后联合消去权重选择 | [条件化分解](index_coupling/LOOP_CONDITIONED_FACTORS.md)有精确递推；[§20](index_coupling/CONTRACTION_ORACLE.md) 的 36 个分支前沿点相等、324 次回放通过；但 M8 完整分支生成仅为 native 的 0.52×/0.34×，慢于现有闭式 | 直接容量扫描增加了局部因子计算，试验到此停止；不把正确分解、减少完整 mask 调用当作实际加速 |
| 固定 M→1 的断点求值与局部见证恢复 | [§21](index_coupling/CONTRACTION_ORACLE.md)：M8 前沿搜索降至 1.44/3.35 ms，但完整分支生成仍为 native 的 0.47×/0.87×；Tiny 分支为 36.05×，720 次回放通过 | 不推广 Tiny 至完整 Root；只移除根部 M→1 调用时，M8 新增不可达子状态为 0。停止该固定分支优化；局部公式也已更正为段计划模板，而非完整原生 group 曲线 |

最新 Residency 报告的 84–88% 是“若每个不含驻留集合的 key 只付一次最贵成员成本”
的假想 DP 工作节省。**曲线形状不同，不证明计算不可共享；共享上限很大，也不证明
存在廉价算法。** 现有证据仅排除已检查的三种简单结构。不得把它写成计算复杂度下界，
也不得把这个百分比写成尚未实现的加速潜力承诺。

随后计时收尾还核清了另一项限定：原 §18 的 35–42% 是特定事后选边策略的 DP 工作
节省。代码选择首个达成每个前沿点的动作，没有优化所有等价 witness 的全局共享。
它尚不是任意选边策略的上界，更不能直接换算成墙钟时间上界。原始数值不变。

## 6. 真实 DNN 与硬件验证的准确状态

[实际子图研究](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc/research/dnn_benchmarks/RESULTS.md)
的 39 个任务中，21 个完成并回放 133 个 witnesses，12 个完成搜索但超过标量回放预算，
6 个超时。当前 IR 接纳的最长 ResNet/ViT/U-Net 岛分别为 11/4/2 个 FX 算子；
16/32/64/128 前缀均未完整接纳。完成的同语法曲线相等，但没有一致搜索加速。

[PyTorchSim](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/5245c9cc/research/dnn_benchmarks/PYTORCHSIM_RESULTS.md)
已实际运行，不再是“尚未接入”：8 次 GEMM 调用有 5 次数值通过、3 次失败。
另有独立 DMA 字节地址错误和逻辑 tile/物理 SRAM 分配差异。现有 cycles 全部不作为
延迟、能量或 EDP 收益；这些还是手动 Mapping 控制，不是端到端最优 witness 接入。

旧 [physical_cost](physical_cost/README.md) 则已有地址级回放、Bank 竞争和有限硬件域
的 EDP 结果；强 grouped sweep/shortlist 在不少控制上追平。它有独立价值，但模型、
语法与当前 `(C,Q)` 求解不同。不能用这批旧收益补齐新 Mapper 尚缺的硬件证据。

## 7. Git 的收束，不再增加研究分支

本次检查有 9 个本地分支：上游 `main`、研究主线、4 个未合并研究分支、3 个已合并
历史分支。`main` 跟踪上游框架，`research/main` 是研究入口，二者不可混为“最新主线”。

| 分支 | 检查到的状态 | 处理方向 |
| --- | --- | --- |
| `research/main` | `2c8050c6`，含 response 整理与最新 Residency 诊断 | 唯一研究论证与方法开发入口 |
| `research/dnn-benchmarks` | `5245c9cc`，7 个独有提交 | 保留为现有验证工作区，限定于当前接口正确性；不另起优化器 |
| `research/independent-contract-audit` | `7e03ab3b`，1 个独有提交 | 4/5 证明与 Mapping 审计结论待统一归档，部分修复已被 DNN 分支采用 |
| `research/chain-conditional` | `14a06502`，2 个独有提交 | 保存冻结预测和带边界的双收缩验证，整合结论后归档 |
| `research/closure-review` | `3da98687`，1 个独有提交 | 整合响应成本与统计口径纠正后归档 |
| `research/constructive-heldout`、`research/index-coupling-bounds`、`research/scalar-retention-proof` | tips 已是主线祖先，远程分支已消失，本地 worktrees 仍在 | 作为历史留档；确认各工作区干净且无人使用后才能删除 |

“未合并”是 Git 祖先关系，不等于结论从未吸收。`response/` 已替换旧模块布局，不能
为了清分支盲目 cherry-pick 旧脚本。本次只整理入口，没有切换、合并、删除分支或工作区。

本轮吸收了一项具体文档纠正：[独立审计](https://github.com/HaoningJiang-space/accelforge-streaming-dse/blob/3da98687/research/index_coupling/CLOSURE_REVIEW.md)
确认算子投影原始 8 行记录合计为 **17,647 个 eligible nodes、5,796 条相等曲线**；
本轮重新汇总原始记录，将主线 `CONTRACTION_ORACLE.md §14` 的 17,857/6,416 修正。
零违反结论与归档记录不变，且不能把这些状态数当成独立模型数。这不是合并整个审计分支。

## 8. 下一阶段只交付三个东西

1. **一份主张–证据表与短论文论证。** 以第 4 节为主体，逐项列语法、前提、证明、
   Oracle、独立回放、性能计时和失败域。纳入三个审计分支的有效结论并解决统计差异。
   针对真正准备主张的新颖性读原始文献，不能以论文名称列表代替对照。
2. **一个最小复现入口。** 只选已有代表性实例：残差分解、部分对称且汇合的联合实例、
   unit-M 解析替换，以及 M8 负面对照。分别固定语法、基线与计时；不把不同语法的速度
   拼成一张“通用加速”表。unit-M 替换的完整 witness 生成计时已在 §16a 补齐；其余
   对照也应采用明确的完整生成口径，不再新增优化开关。
3. **一个受限的外部验证关口。** 沿已有 GEMM 导入处理数值、DMA 字节和真实分配契约；
   通过后才接受一个支持子图的硬件时间比较。未通过就明确报告阻塞，不扩成整网、
   多精度、重算或新 DMA overlap 搜索项目。

不以“又产生一个待研究的问题”为完成标准。收束阶段完成应当是：统一入口能准确说明
每条主张及其证据，最小集合可复现，未完成硬件接口有具体状态，历史分支结果不再游离。
如果届时只有受限族的精确性与加速，就按这个范围评价论文；不以新命名掩盖缺少通用
规模结果，也不为维持“通用 Mapper”标题不断追加算法。
