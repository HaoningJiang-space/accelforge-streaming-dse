# 真实模型实现导出的 DAG：结果与限制

2026-11-08，Torch 2.15.0+cpu、Torchvision 0.29.2+cpu、Python 3.12。
从已安装 Torchvision 的完整模型实现调用 FX 导出，11 个尝试中 10 个成功。
模型采用 `weights=None`、eval 模式、FP32、输入 1×3×224×224；没有下载预训练权重。
这是实际模型程序的图，不是手写拓扑；结果仍属于明确的抽象内存语义。

## 主要结果

所有 10 个成功导出的图都在 5000 状态 / 10 秒的单图 DP 限制内精确完成。
**这 10 个图的原始顺序、四种一步贪心、两步前瞻，在执行期峰值这个指标上全部达到精确最优。**
本轮没有观察到重排带来的全图峰值收益。

| 模型 | 张量产出算子数 | 精确最小边界张量数 | 精确最小执行峰值 KiB | 合法前缀状态数 |
| --- | ---: | ---: | ---: | ---: |
| ResNet-18 | 69 | 2 | 6272 | 100 |
| ResNet-50 | 175 | 2 | 9408 | 240 |
| MobileNet-V2 | 152 | 2 | 9408 | 153 |
| MobileNet-V3 Small | 156 | 3 | 1764 | 157 |
| EfficientNet-B0 | 239 | 3 | 9408 | 240 |
| DenseNet-121 | 431 | 25 | 8232 | 432 |
| SqueezeNet-1.1 | 65 | 2 | 6160.5 | 98 |
| ConvNeXt Tiny | 184 | 2 | 10584 | 185 |
| ViT-B/16（MHA 未展开） | 104 | 2 | 5319 | 105 |
| DeepLabV3 ResNet-50 | 198 | 5 | 18816 | 1781 |

每列的最小值分别优化，不隐含共同 witness；原始顺序也达到这里列出的执行峰值。
计数不包含 FX 的非张量形状查询、参数读取和输出包装，不能与其他 IR 的节点数直接比较。

DenseNet-121 是小边界假设的直接反例：25 个活跃张量；内部跨切口 tensor-use 边数的最优峰值则是 169。
同一个张量供多处使用不能重复算成多份存储，因此这两个宽度指标不可混用。
同时，DenseNet 的 431 个算子只有 432 个合法前缀，执行顺序基本被依赖固定。
这说明“大边界”可能增加物理状态组合，却不必增加拓扑顺序的选择数。

7 个图的执行最优值还等于简单下界 `max_op(sum(unique_inputs + output))`：
ResNet-18/50、MobileNet-V2/V3、EfficientNet、SqueezeNet、DeepLabV3。
在本轮全张量语义下，单个算子本身就决定全图瓶颈，单靠重排无法降低它。
DenseNet、ConvNeXt、ViT 的精确峰值高于此局部下界，但原始顺序仍已最优。

## 图忠实性与计费口径

- [FX](https://docs.pytorch.org/docs/2.15/fx.html) 保留其默认叶子模块粒度：例如 Conv2d 是一个算子，
  ViT 的 MultiheadAttention 也是一个算子。其内部 Q/K/V、score、softmax 和 workspace 未展开；
  **ViT 的 k=2 不可解释为细粒度 attention 的边界只有 2，也不可直接与首轮手写 attention 比较。**
- [Meta execution](https://docs.pytorch.org/docs/2.15/meta.html) 提供真实算子的形状和 dtype，
  不执行数值训练或测量实际内存。另行 CPU 执行用于验证形状及归一化前后的输出。
- 将模块及函数的 `inplace=True` 显式改成 False。所有不同 Tensor 对象的输出，包括 reshape/permute 等 view，
  按独立完整物化计费；同一 Tensor 对象的 tuple projection/Identity 不复制计费。
  这是统一的 functional materialization 模型，不是 PyTorch allocator 的峰值。
- get_attr 参数/缓冲不计；参数派生的小张量（如 ViT class-token expand）作为只读外部张量，
  从首次使用到最后使用计入。所有这些处理逐节点记录，未把它们静默删除。
- FX 的形状/标量节点不作为存储算子，形状固定为本次输入；不声称覆盖动态控制流或其他输入形状。
- 没有融合、tiling、spill、重算、布局约束、权重流量、算子 workspace、DMA staging 或 allocator 碎片。
  原地覆盖和 alias-aware 规划可能降低字节数，真实 workspace/权重会增加存储压力。
- 无预训练权重足以确定这些静态形状与拓扑，但本轮不是精度或真实运行性能评价。
  FP32 数值也不能直接与首轮 FP16/INT8 容量做横向比较。

ShuffleNet-V2-x1.0 在 `chunk` 处产生多个 Tensor，当前单输出 IR 无法表示其原子产生与 alias 关系，
因此显式记录失败并排除，不伪造多个可独立调度的算子。其余模型没有此类失败。
未覆盖真实 U-Net、动态 MoE 或展开后的 transformer attention，也未做 motif 挖掘。

## 证据、验证与复现

- [real_models.json.gz](results/real_models.json.gz)：版本、输入、模型类与实现文件 SHA256、FX 代码、
  每个张量的 shape/dtype/bytes、被省略或归一化节点、完整 DAG、各策略顺序及逐步 trace、精确 witness。
- [export_validation.json](results/export_validation.json)：对每个成功模型执行 CPU eager 与归一化 FX，
  比较输出并逐项核对 CPU/Meta 张量形状。固定随机种子 19、随机初始化权重，容差 rtol=1e-4、atol=1e-5；
  这验证本次输入的导出/归一化，没有把抽象存储模型当作真实物理执行验证。
- [test_real_models.py](test_real_models.py)：fork 与 view 计费、函数原地操作归一化、多输出拒绝、
  下界匹配与 DP 完成的区分，以及 ResNet CPU/Meta shape 交叉验证。
- [environment.txt](environment.txt)：导出环境的依赖版本，独立于原有 FFM 环境。

本次 10 个模型的 CPU/FX 对比全部通过，最大绝对输出误差均为 0；所有记录的张量形状匹配。
测试套件为 10 passed。以上结果只针对记录的输入形状与随机权重，不是任意输入的形式化等价证明。

在独立 Python 3.12 环境安装环境清单中的版本（CPU wheels 来自 PyTorch 官方 index）：

```powershell
python -m pip install torch==2.15.0+cpu torchvision==0.29.2+cpu --index-url https://download.pytorch.org/whl/cpu
python -m pip install pytest==9.2.0
python -m research.graph_structure.real_models
python -m research.graph_structure.validate_exports
python -m pytest -q research/graph_structure
```

Windows 本次使用 `%USERPROFILE%/.codex/envs/graph-analysis/Scripts/python.exe`；
未修改已有 `accelforge` FFM 环境。所有命令从仓库根目录执行。
导出脚本支持 `--models`、`--state-limit`、`--time-limit`、`--output`。
完整导出默认覆盖结果文件；单模型调试请另设 `--output`，避免覆盖完整套件。

## 修正后的研究判断

asymmetric 的贪心差距被两步前瞻消除；这组真实模型的全张量执行峰值又没有调度改进空间。
因此，目前没有证据把“更强的全图顺序搜索”作为主要贡献。
更合适的后续问题是：在小于完整张量峰值的 SRAM 下，边界驻留、tile 和 spill 决策能否产生
强基线尚未覆盖的流量/能耗收益。该问题不能由本轮峰值结果替代，也尚未在这里求解。
