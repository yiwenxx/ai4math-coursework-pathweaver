# ai4math课程作业——PathWeaver

**面向可验证组合优化的研究原型：首个可运行 EDA 路径耦合分配 TaskPack。**

[当前状态](STATUS.md) · [任务格式](docs/eda_assignment.md) · [公开案例与复现](docs/eda_public_cases.md) · [结果摘要](results/README.md) · [泛化边界](docs/generalization.md) · [来源](docs/upstream.md)

给定一个具有固定坐标的 DAG，把每条跨层边分配到一个合法 HB 站点，每个站点
全局容量为一。按精确字典序最小化 `(T,L)`：先降低完整 DAG 的最长路径代价，
T 相同时再降低跨层总几何线长。独立评估器重新计算约束与目标，不采信解自报的分数。

当前提供实例生成、JSON 格式、独立验证、两种求解策略、三个手工样例，以及
Open3DBench AES / Ibex 的公开案例比较入口。完整自主算法发现循环、执行隔离和
其他数学任务仍在开发中。

## 快速开始

需要 Python 3.11–3.13；轻量包无第三方运行依赖，也不调用模型。

```bash
git clone https://github.com/yiwenxx/ai4math-coursework-pathweaver.git
cd ai4math-coursework-pathweaver
python -m venv .venv
# PowerShell: .venv/Scripts/Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e .
pathweaver info
pathweaver tasks --json
pathweaver eda verify benchmarks/eda_assignment/example.json benchmarks/eda_assignment/example_solution.json
pathweaver eda solve benchmarks/eda_assignment/example.json --output solution.json
pathweaver eda verify benchmarks/eda_assignment/example.json solution.json
```

样例的目标为 `(5,8)`。可选用全局路径匹配策略或生成合成实例：

```bash
pathweaver eda solve benchmarks/eda_assignment/example.json --strategy path-matching --output path-solution.json
pathweaver eda generate --seed 0 --size 6 --output instance.json
```

生成器产生一个有限合成族，不代表真实电路分布。其运行覆盖及新公开入口的验证范围
列在 [STATUS](STATUS.md)。

## 两种策略与已有结果

- `baseline`：按几何长度偏好构造可行匹配，尝试空闲站点移动和成对交换。
- `path-matching`：使用完整 DAG 路径下界限制候选站点，以全局最小代价匹配处理
  容量竞争，必要时尝试路径压力与节点势引导的后续匹配。候选始终按真实 `(T,L)` 接受。

已有运行使用种子 0、最多 1000 次完整 DAG 计分、每个策略 30 秒协作式墙钟上限。

| 案例 | 旧基线 `(T,L)` | 新策略 `(T,L)` | 公开参考 `(T,L)` |
|---|---|---|---|
| AES | `(928085,35175360)` | `(744915,32038820)` | `(744915,32370920)` |
| Ibex | `(1835280,49687230)` | `(1663875,47840820)` | `(1663875,47974340)` |

AES 用于策略开发，Ibex 未参与此次调优。两例中，新策略均保持参考 T 并降低 L，
但它们属于同一套件、工艺库和 placer，且都在首次匹配后达到 T 下界。这是一次
未调优电路迁移的正面证据，尚非广泛泛化或系统自主发现的证据。

目标是固定布局上的几何代理量，不是实测时序或 PPA。公开参考 placer 未重跑，
其计算预算未知。完整数据说明、单次运行记录和局限见 [结果摘要](results/README.md)。

## 使用公开电路

按 [输入准备说明](docs/eda_public_cases.md)从作者提供的文件中准备 DEF、LEF 和 Liberty，
然后从仓库根目录运行：

```bash
python scripts/compare_open3dbench.py --case aes --data-root data/open3dbench --output-dir artifacts/aes
python scripts/compare_open3dbench.py --case ibex --data-root data/open3dbench --output-dir artifacts/ibex
```

每个命令导入一个电路，分别运行两个策略一次，独立检查参考解和候选解，并输出实例、
解、评估诊断、源几何审计、JSON 摘要及 Markdown 报告。输入直接来自公开源文件，
不依赖之前的运行目录。

本项目采用 Apache-2.0；第三方数据与库由原作者提供并保留各自声明。
贡献方式见 [CONTRIBUTING](CONTRIBUTING.md)，功能方向见 [ROADMAP](ROADMAP.md)。
