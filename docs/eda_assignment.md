# EDA 路径耦合分配

给定具有固定整数坐标和层号的有向无环图，为每条跨层边恰好选择一个合法 HB 站点。
同一个站点 ID 的容量在全图、不同层对和不同连通分量之间都为一。允许空闲站点；
坐标相同的不同站点 ID 仍有独立容量。

跨层边 `e=(u,v)` 选择站点 s 后：

```text
length(e,s) = |x_u-x_s| + |y_u-y_s| + |x_s-x_v| + |y_s-y_v|
delay(e,s)  = base_delay(e) + alpha(e) * length(e,s)
```

`base_delay`、`alpha` 为非负整数。同层边采用给定的非负整数 `delay`，不占站点。
层号用于区分边类型，不额外增加距离。

精确字典序最小化 `(T,L)`：T 是完整 DAG 的最长源到汇路径代价，包含所有固定边
和不连通分量；L 是全部跨层边的几何线长之和。T 较小必定优先，只有 T 相等时才
比较 L。不会用加权和代替此排序。改变分配后必须重算完整 DAG，关键路径可以切换。

## 实例与解

实例示例：

```json
{
  "schema_version": 1,
  "task_id": "eda_assignment",
  "instance_id": "single_edge",
  "data": {
    "nodes": [{"id":"a","x":0,"y":0,"tier":0}, {"id":"b","x":4,"y":0,"tier":1}],
    "sites": [{"id":"s0","x":2,"y":0}],
    "edges": [{"id":"ab","source":"a","target":"b","base_delay":1,"alpha":1,"eligible_sites":["s0"]}]
  }
}
```

对应解：

```json
{
  "schema_version": 1,
  "task_id": "eda_assignment",
  "instance_id": "single_edge",
  "solution": {"assignment": {"ab": "s0"}}
}
```

同层边字段为 `id, source, target, delay`；跨层边字段如上。节点至少一个；站点和边
数组可为空。ID 在各自类别内唯一、非空，引用必须存在。坐标可为负整数；层号、延迟
及系数为非负整数，布尔值不能充当整数。数据对象内未知字段被拒绝，顶层可带元数据。

图必须无环。每条跨层边的资格列表不含重复站点，所有跨层边合起来必须存在完整匹配；
仅有足够数量的站点不能保证可行。解必须恰好覆盖所有跨层边，不得重复使用站点。

## 独立评估

评估器重新解析实例、检查分配并从坐标计算 `(T,L)`。解中的自报分数与证书不作为依据。
输出包含 `feasible`、`objectives`、`violations`、`diagnostics`、`lower_bound` 和 `evidence`。
诊断给出到达时间、后向路径、边松弛量、一条关键路径及站点竞争情况。

下界忽略容量，为每条跨层边独立取最短合法线长，再计算完整 DAG 的 T 和总 L。
只有合法解同时达到两个下界坐标时，评估器才标记 `finite_optimal`。只达到 T 下界
不证明字典序最优；其他合法解保留 `experimental` 标签。

## 求解与预算

`baseline` 构造长度偏好的可行匹配，再尝试空闲站点移动和成对交换；接受第一个严格
字典序改善并重启邻域扫描。`path-matching` 使用全图路径下界和全局最小代价匹配，
必要时尝试最多 8 轮路径压力与 3 次可行节点势引导的匹配。两者都没有普适最优保证。

```bash
pathweaver eda solve instance.json --seed 0 --max-evaluations 1000 --wall-seconds 30 --output solution.json
pathweaver eda solve instance.json --strategy path-matching --seed 0 --max-evaluations 1000 --wall-seconds 30 --output path-solution.json
pathweaver eda verify instance.json path-solution.json
```

每次完整 DAG 计分消耗一次评估，包括初始解和新策略可选的下界计算。解析、资格检查、
几何准备、匹配和搜索都计入求解墙钟；独立验证另计。墙钟限制在操作间协作检查，
单个操作可能使实际时间略超预算。首次计分前超时会报错，已有解时返回当前最佳解。
相同输入和种子在墙钟不触发时可重复；墙钟受限结果可能随机器变化。

CLI 退出码：0 为成功/合法解，1 为非法解，2 为实例或输入错误，3 为首次计分前超时。
Python 入口是 `EdaAssignmentTaskPack`，提供 `generate`、`validate_instance`、
`baseline`、`verify`；模块中的 `compare_objectives` 返回 −1/0/1 表示更好/相等/更差。

三个可直接使用的样例及其已有检查见 [样例目录](../benchmarks/README.md)。
