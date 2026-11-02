# JSP-000158：候选定量细化研究稿 v0.1.0

**2026-11-02 · 四项等差数列至少三色 · 对应 Erdős 问题 160**

[完整候选证明](NOTE.zh-CN.md) · [审阅与查新状态](REVIEW.md) · [有限构造数据](finite-colorings.json) · [引用](CITATION.md)

本版公开一个有完整文字推导的候选结果：对某个绝对常数 C，

$$
h(N)\le C N^{1/4}\sqrt{\log N}\exp\!\left(2\sqrt{\log12\,\log N}\right),\qquad N\ge3.
$$

候选构造的具体特点是 12 值数字标签，以及在已有范数核心上只对模 p² 投影施加辅助染色。**正确性仍待外部独立确认，新颖性尚未确认。** 它没有突破 1/4 主指数，不是原题完整解。发布意在提供可审阅的具体命题和证据，不宣称首次发现。

This release contains an AI-assisted proof draft for an explicit subexponential refinement, together with finite coloring artifacts. The leading exponent 1/4 is already known. Correctness and novelty have not been independently established. See the [English abstract and full Chinese argument](NOTE.zh-CN.md).

## 哪些结果已经过有限核验

| N | 本轮种子颜色数 | 最佳有限上界 | 已记录的 AP 检查数 | 违规 |
|---:|---:|---:|---:|---:|
| 16 | 4 | 4 | 35 | 0 |
| 32 | 6 | 5 | 155 | 0 |
| 64 | 9 | 7 | 651 | 0 |
| 128 | 12 | 10 | 2667 | 0 |
| 256 | 17 | 14 | 10795 | 0 |

这些是可重算的有限上界，没有最优性证明，也没有新纪录认定。种子在相同实例和单次执行配置下评估；整个搜索额外消耗了多轮评估，表格不是等总计算成本的算法优越性实验。

循环 ABBA 搜索中，最佳整套候选在 (m,r)=(22,3)、(82,3)、(257,4)、(626,5) 的违规数分别为 0、344、2140、7330。仅第一项有效，颜色表与 [Deng–Tidor–Zhao §1](https://arxiv.org/html/2307.06914v2) 已公布的模 22 模板相同。22<3⁴，未跨过改善 1/4 指数的模板阈值。失败搜索不是不存在性证明。

ABBA 条件只禁止首尾同色且中间两项同色，不等同于“每条 AP 至少三色”。循环核验包括全部非零步长、回绕和重复位置。完整区间条件的模式排除另见证明稿。

## 重算方法

从公共仓库根目录运行，只需 Python 3.11–3.13 标准库：

```bash
python scripts/verify_jsp158_artifacts.py
```

也可明确指定数据文件：

```bash
python scripts/verify_jsp158_artifacts.py research/jsp158/finite-colorings.json
```

预期退出码为 0：五个区间分别使用 4/5/7/10/14 色，违规为零；循环表为 22 点、3 色，检查 462 个模 AP，违规为零，`crosses_quarter_threshold=false`。退出码 1 表示存在违规，2 表示数据格式或读取错误。

脚本从数组重新计数，不采信已记录的检查结果。它不调用模型、不执行候选程序、不检验证明的新颖性，也不能验证上述渐近界。公开脚本本次只做编译检查；有限核验数字来自此前完成的全量核验，发布时没有重复运行搜索或有限核验。

## 版本和使用

研究稿版本 `0.1.0` 与软件包的 `0.1.0.dev1` 独立。稿件、重算脚本和本项目生成的数据沿用仓库 Apache-2.0 许可；引用已有模板时仍应同时注明其原始论文。

该稿由系统生成，再由 AI 助手整理和检查；没有获得外部同行评审或形式化认证。若发现错误，请在 [Issues](https://github.com/yiwenxx/ai4math-coursework-pathweaver/issues) 标明具体公式或引理。若发现等价文献，请给出原始来源及命题定位。相关修正将更新版本记录。
