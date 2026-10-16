# Open3DBench 公开案例与复现

入口从公开 DEF、LEF、Liberty 源文件构造 TaskPack 实例和参考解，再分别运行
`baseline` 与 `path-matching` 一次。它不需要先前的运行产物，也不执行上游 placer。
已有数值结果见 [结果摘要](../results/README.md)。

## 准备输入

从 [Open3DBench Place-LoL 官方说明](https://github.com/lamda-bbo/Open3DBench/blob/main/Place-LoL/README.md)
获取作者发布的文件：

1. [布局归档](https://drive.google.com/file/d/1HHbYQmv12SQ_xUKSnKMVI6RVyX3Z8hPf/view)
   中的 `binaries/converted_output/default/cadb1021/aes.def` 和 `ibex.def`。
2. [基准归档](https://drive.google.com/file/d/1wVYCgee2k7_1JdmV4o6Q4sIgDpoCkAcn/view)
   解压后的 `benchmarks/nangate45/lib/NangateOpenCellLibrary_typical.lib`。
   官方归档顶层可能名为 `benchmarks_lol`；找到其中 `nangate45/lib` 目录即可。
3. 官方仓库中的 [bottom LEF](https://github.com/lamda-bbo/Open3DBench/blob/main/OpenROAD-3D/flow/platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef)
   与 [upper LEF](https://github.com/lamda-bbo/Open3DBench/blob/main/OpenROAD-3D/flow/platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef)。
   使用页面的原始文件下载功能，保存 LEF 正文而非 HTML 页面。

只需对应输入文件，保留下载材料中的作者及库声明。本仓库不附带原始数据。
将文件放成以下布局；`--data-root` 可以指向任意本地目录：

```text
data/open3dbench/
├── placements/
│   ├── aes.def
│   └── ibex.def
├── lef/
│   ├── NangateOpenCellLibrary.macro.mod.bottom.lef
│   └── NangateOpenCellLibrary.macro.mod.upper.lef
└── lib/
    └── NangateOpenCellLibrary_typical.lib
```

只运行一个案例时，只需要该案例的 DEF。两个案例共用 LEF 和 Liberty。

## 运行与输出

在仓库根目录、完成安装后运行其中一个命令：

```bash
python scripts/compare_open3dbench.py --case aes --data-root data/open3dbench --output-dir artifacts/aes
python scripts/compare_open3dbench.py --case ibex --data-root data/open3dbench --output-dir artifacts/ibex
```

默认每个策略使用种子 0、1000 次计分上限、30 秒协作式墙钟上限。可显式传入
`--seed`、`--max-evaluations`、`--wall-seconds`；改变参数就是新的比较条件。
导入与独立验证不计入策略预算，两次求解的预算分别计算。参考 placer 的历史计算时间未知。

输出目录必须尚不存在。每次执行输出：

- `instance.json`、`reference_solution.json` 与源结构/模型说明。
- 各策略的 `*_solution.json`、`*_evaluation.json`、`*_audit.json`。
- `comparison.json` 和 `report.md`，包含约束检查、目标、耗时和胜负。
- 发生错误时保存 `failure.json` 或对应策略的 `*_failure.json`，不自动重试。

退出码 0 表示参考和两个候选均通过独立检查；1 表示至少一个策略求解或验证失败；
2 表示输入、导入或运行级错误。失败不能当成最优性结论或从结果中省略。

最小手动检查是只运行一个案例，查看报告是否有三条 `verified` 记录。
对于已有观察中使用的文件，AES 应有 381 条可调连接、1492 个 HBT；Ibex 为
389 条、1599 个。新策略的已有目标分别为 `(744915,32038820)` 和
`(1663875,47840820)`。这些是参考观察，不是对新下载文件或任意机器的承诺；
上游内容变化、参数变化和旧基线的墙钟截断可能改变结果。

2026-10-16 已用现有 AES 文件对本入口完成一次最小端到端运行：退出码为 0，
三个方案均通过独立检查，目标与上述 AES 观察一致。旧基线计分 122 次，新策略
计分 2 次，分别耗时 30.134280 秒和 1.803001 秒。没有修改策略或重试，详情见
[AES 验证记录](../results/aes_entrypoint_validation.json)。该次仅运行 AES，未增加种子。

同日随后用现有 Ibex 文件对同一入口单独运行一次，沿用相同预算，退出码为 0。
参考、旧基线和新策略均通过独立检查，目标分别为 `(1663875,47974340)`、
`(1835280,49687230)` 和 `(1663875,47840820)`。旧基线计分 134 次、耗时
30.242825 秒，新策略计分 2 次、耗时 1.310219 秒。三者均完整覆盖 1592 条
数据图跨层边，站点容量为一；全部 1599 个物理 HBT 的位置集合保持且零重叠。
7 个固定控制类 HBT 不需要数据图分配，仍纳入物理检查。未修改代码、重试或重跑
AES，详情见 [Ibex 验证记录](../results/ibex_entrypoint_validation.json)。

## 模型对应关系

导入器从真实网连接和 Liberty 组合弧构造内部数据 DAG。所有可表示的两针跨层数据网
都可调，候选站点是它们原本占用的 HBT 中心，资格域完整且全局容量为一。
多针跨层网保留同一个固定 HBT，再用固定分支连接接收端；其他 HBT 和所有单元位置固定。

源结构须包含至少两条可调跨层边的连续路径，以及最短站点集合的容量竞争。
脚本检查这些结构条件、完整匹配和几何合法性。独立源审计从 driver-to-sink 网重建
路径与几何量，对照 TaskPack 的结果，并检查所有 HBT 位置保持及重叠情况。

顺序元件内部传播被截断；I/O、时钟、复位及控制边界显式记录在模型说明中。
Ibex 的 7 个固定控制类 HBT 没有数据图跨层边，仍保留在物理检查中。
单元弧延迟设为零，连线采用整数 Manhattan 几何。因此 T 是保留 DAG 的几何路径代理，
L 是跨层边几何和；固定的同层分支不计入 L，不能把 L 的绝对值称作整芯片 HPWL。

这是公开布局上的受限重分配，原布局提供固定单元和站点坐标。它不等于从网表重新布局，
也没有执行电气时序、详细布线或物理签核。输入格式不受支持时，导入器会报错。

## Bookshelf Python 接口

`bookshelf.import_bookshelf` 也可读取作者的 `terminal.nodes`、`terminal.nets`、
`terminal.pl` 目录。示例：

```python
from pathlib import Path
from pathweaver.core.contracts import SolveBudget
from pathweaver.tasks.eda_assignment import EdaAssignmentTaskPack
from pathweaver.tasks.eda_assignment.bookshelf import import_bookshelf, audit_bookshelf_assignment

directory = Path("data/bookshelf/terminal")
bundle = import_bookshelf(directory, instance_id="bookshelf_case")
pack = EdaAssignmentTaskPack()
solution = pack.baseline(bundle["instance"], SolveBudget(30, 1000, 0))
evaluation = pack.verify(bundle["instance"], solution)
audit = audit_bookshelf_assignment(directory, solution, coordinate_scale=bundle["manifest"]["coordinate_scale"])
```

该适配器仅调整两侧各一个单元引脚的连接，图是独立的单边路径；T 表示最长选中连接。
它不用于证明真实多边路径耦合。原始格式来自 [D2D-Placer](https://github.com/liW-J/D2D-Placer-With-Differentiable-Partitioner)。
