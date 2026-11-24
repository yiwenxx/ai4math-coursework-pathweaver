# PathWeaver

面向可验证组合优化与离散数学研究的算法发现与形式化认证框架（纯 Python 标准库 + 零 Mathlib Lean 4 内核）。

[English README](README.en.md) · [当前状态](STATUS.md) · [EDA 任务与证书](docs/eda_assignment.md) · [公开电路与复现](docs/eda_public_cases.md) · [Lean 4 形式化验证](docs/lean_proof.md) · [结果摘要](results/README.md) · [泛化边界](docs/generalization.md) · [JSP-000158 研究与证书](research/jsp158/README.md) · [来源](docs/upstream.md)

## 系统

```mermaid
flowchart LR
  A["算法发现与证据内核"] --> B["可验证任务包: EDA · WVC · JSP-000158"]
  B --> C["独立证书与零信任核验"]
  C --> D["Lean 4 形式化内核"]
```

| 模块 | 核心能力 | 入口 |
|---|---|---|
| **算法发现与证据内核** | 无损整数元组与 Pareto 排序、四层认识论记忆（L0 行为差分、槽位+UCB 检索、`MemoryConsolidator`、`ExperimentSelector`）、持久化 AST 范式逃逸、命题账本 `ClaimLedger` | `pathweaver claims` · [research/](src/pathweaver/research/) |
| **Lean 4 形式化内核** | 21 个零 Mathlib、零 `sorry` 模块（`PathWeaverFormal`），支持三任务证书导出、命题锁定发现与 `#print axioms` 审计 | `pathweaver lean` · [formal/](formal/PathWeaverFormal) |
| **EDA 路径耦合分配** | 精确字典序 `(T, L)` DAG 优化、`path-matching` 策略、独立 Hungarian 原始—对偶与 Hall 冲突有限最优证书 | `pathweaver eda` · [eda_assignment.md](docs/eda_assignment.md) |
| **加权最小顶点覆盖** | 独立验证器、边/奇环/团对偶下界、贪心局部搜索、精确分支定界证明树 `bnb_proof_tree` | `pathweaver wvc` |
| **JSP-000158 研究套件** | 4-AP 与循环模板核验、有限域反例探测、循环乘积构造、零信任证书复验 | `pathweaver jsp158` · [research/jsp158/](research/jsp158/README.md) |

## 成果

### EDA 路径耦合分配（Open3DBench）

在固定 3D 布局公开电路上，`path-matching` 在 ~1.1 秒（2 次评估）内达到理论最长路径下界 `T_lb`，并由独立于求解器的原始—对偶检查器通过 `finite_optimal` 认证：

| 电路 | 公开参考 `(T, L)` | `path-matching` `(T, L)` | 相对公开参考（相对基线） | 用时 | 认证 |
|---|---:|---:|---|---:|---|
| **AES** | `(744,915, 32,370,920)` | `(744,915, 32,038,820)` | `T` 达下界，`L` **−1.03%**（`T` −19.74%，`L` −8.92%） | 1.07 s | `finite_optimal` |
| **Ibex**（未调优迁移） | `(1,663,875, 47,974,340)` | `(1,663,875, 47,840,820)` | `T` 达下界，`L` **−0.28%**（`T` −9.34%，`L` −3.72%） | 1.15 s | `finite_optimal` |

### JSP-000158（Erdős #160）与 Lean 4 形式化认证

| 成果 | 核心结论 | 核验方式与证据 |
|---|---|---|
| **大尺度有限上界** | $h(10^{18}) \le 132\,158\,016$，零列自由边界延拓至 $3p^2+p+1 = 1\,004\,830\,828\,672\,875\,053$（$p=578\,743\,129$） | Lean 4 内核无条件证明（[CriticalSquareCertificate.lean](formal/PathWeaverFormal/CriticalSquareCertificate.lean)） |
| **小区间显式上界** | $h(137) \le 9$（模 45 九色循环模板 $h(45n) \le 9h(n)$）、$h(98) \le 8$；$N = 16/32/64/128/256$ 上 **4/5/7/10/14 色**零违规构造 | Lean 4 内核证明（[NineColorInterval.lean](formal/PathWeaverFormal/NineColorInterval.lean)、[SmallIntervalWitnesses.lean](formal/PathWeaverFormal/SmallIntervalWitnesses.lean)）与全量 4-AP 核验 |
| **必现四色精确阈值** | 任意合法至少三色 4-AP 着色中，首次必现四色 4-AP 的精确最小长度为 **19** | Lean 4 内核证明（[ForcedRainbow.lean](formal/PathWeaverFormal/ForcedRainbow.lean)） |
| **$q=121$ 混合曲线覆盖** | 全量认证 **4,880** 个降次不可约三次式、**40,656** 组参数与 **4,919,376** 个方程 | 零信任独立复验（[q121_mixed_curve_certificate.json](results/q121_mixed_curve_certificate.json)） |
| **循环模板与障碍分类** | 闭合 $(m,3), m\in[23,85]$ 全量 UNSAT 与 $(m,4)$ 3,300 个陪集商 UNSAT；给出耦合仿射置换、特征 5 非多项式刚性（$d\le 3$）、分圆特征径向坍缩（$d\le 3$）、有理分母剪切（$d\le 2$）与四次中点偶抵消（$D\le 4r$）等受限构造族障碍 | 机检反证（[jsp158_quarter_breakthrough_sweep.json](results/jsp158_quarter_breakthrough_sweep.json)）+ Lean 4 核心恒等式认证（[research/jsp158/](research/jsp158/README.md)） |
| **形式化基础库** | 覆盖 EDA 原始—对偶与 Hall 冲突、WVC 边打包对偶、JSP-000158 判定等价与 $\mathbb{F}_{121}$ 代数引理 | `PathWeaverFormal` 21 模块零 `sorry`、仅标准公理（[formal/](formal/PathWeaverFormal)） |

## 快速开始

```bash
python -m pip install -e .
pathweaver info
pathweaver tasks

# 1. EDA 求解 + 独立原始—对偶最优证书核验
pathweaver eda solve benchmarks/eda_assignment/example.json --strategy path-matching --output path-sol.json
pathweaver eda verify benchmarks/eda_assignment/example.json path-sol.json --require-certificate

# 2. 加权最小顶点覆盖
pathweaver wvc verify benchmarks/weighted_vertex_cover/example.json benchmarks/weighted_vertex_cover/example_solution.json
pathweaver wvc generate --seed 11 --size 16 --output wvc-16.json
pathweaver wvc solve wvc-16.json --strategy exact --output wvc-16-sol.json
pathweaver wvc verify wvc-16.json wvc-16-sol.json

# 3. JSP-000158 有限染色与 q=121 独立机检证书复验
python scripts/verify_jsp158_artifacts.py
python scripts/certify_q121.py verify results/q121_mixed_curve_certificate.json
```
