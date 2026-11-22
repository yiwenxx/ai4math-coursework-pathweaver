# PathWeaver

**极简、可独立验证的 AI4Math 算法发现与数学研究核心（`0.2.0.dev1`）。**

[English README](README.en.md) · [当前状态](STATUS.md) · [EDA 任务与证书](docs/eda_assignment.md) · [公开电路与复现](docs/eda_public_cases.md) · [Lean 4 形式化验证](docs/lean_proof.md) · [结果摘要](results/README.md) · [泛化边界](docs/generalization.md) · [JSP-000158 研究与证书](research/jsp158/README.md) · [来源](docs/upstream.md)

---

## 精简后的核心组件（零第三方依赖即可离线运行）

我们主动剔除了离线 Markdown/Git Vault、假演示、规则反思空壳与历史一次性脚本，将系统收缩为直接服务**创新性算法与数学结论发现**的五个极简支柱：

| 支柱 | 核心能力 | 入口 |
|---|---|---|
| **EDA 路径耦合分配** | 精确字典序 `(T,L)`、`path-matching`、**独立 Hungarian 原始—对偶与 Hall 冲突有限最优证书（`finite_optimal`）**、Open3DBench AES/Ibex 与强冲突诊断 | `pathweaver eda ...` / `scripts/compare_open3dbench.py` / `scripts/run_eda_capacity_gap_case.py` |
| **加权最小顶点覆盖（跨结构迁移）** | 独立验证器 + 边/奇环/团有效不等式对偶下界、加权贪心+局部搜索、微例精确分支定界与 `bnb_proof_tree` 证明树 | `pathweaver wvc ...` |
| **JSP-000158（Erdős #160）** | 全量/增量 4-AP 独立核验器、合法种子、**$q=121$ 混合曲线 40,656 组 / 4,919,376 方程独立机检证书**、小有限域反例探针（`ff_probe.py`） | `pathweaver jsp158 ...` / `scripts/certify_q121.py` / `scripts/verify_jsp158_artifacts.py` |
| **Lean 4 形式化验证内核** | 零 Mathlib 纯 Lean 4 库 `PathWeaverFormal`、三任务 Lean 证书导出、命题锁定 `lean_proof` 任务包与 `#print axioms` 公理审计 | `pathweaver lean ...` / `formal/` |
| **极简科研内核** | 无损原始整数元组 + Pareto 垫脚石排序（`exact_ordering.py`）、AST 范式逃逸（`strategy_escape.py`）、分级抗遗忘与污染追踪 SQLite 账本、影响力排序命题图（`pathweaver claims`） | `pathweaver claims ...` / `pathweaver.backends.skydiscover` |

---

## 快速开始

```bash
python -m pip install -e .
pathweaver info
pathweaver tasks

# 1. EDA 求解 + 独立原始—对偶最优证书核验
pathweaver eda solve benchmarks/eda_assignment/example.json --strategy path-matching --output path-sol.json
pathweaver eda verify benchmarks/eda_assignment/example.json path-sol.json --require-certificate

# 2. 加权最小顶点覆盖（跨决策结构迁移任务）
pathweaver wvc verify benchmarks/weighted_vertex_cover/example.json benchmarks/weighted_vertex_cover/example_solution.json
pathweaver wvc generate --seed 11 --size 16 --output wvc-16.json
pathweaver wvc solve wvc-16.json --strategy exact --output wvc-16-sol.json
pathweaver wvc verify wvc-16.json wvc-16-sol.json

# 3. JSP-000158 有限染色与 q=121 独立机检证书复验
python scripts/verify_jsp158_artifacts.py
python scripts/certify_q121.py verify results/q121_mixed_curve_certificate.json
```

---

## 核心已核验成果

- **Open3DBench AES / Ibex**：`path-matching` 在 ~1.1 秒内均达到理论最长路径下界 `T_lb`，总几何线长较公开参考分别降低 **1.03%**（可调部分 −4.01%）和 **0.28%**（可调部分 −1.86%），并已通过不导入求解器的独立原始—对偶检查器 **`finite_optimal`** 认证。
- **JSP-000158（Erdős #160）**：独立核验 $N=16/32/64/128/256$ 上零违规的 **4/5/7/10/14 色**有限上界；独立机检证书 [q121_mixed_curve_certificate.json](results/q121_mixed_curve_certificate.json) 零信任复验全部 **4,880** 个降次不可约三次式、**40,656** 组归一化参数与 **4,919,376** 个目标方程（约 3.1 秒）。

详见 [STATUS.md](STATUS.md) 与 [泛化边界](docs/generalization.md)。Apache-2.0 许可。
