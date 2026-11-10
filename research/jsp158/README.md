# JSP-000158：研究进展与候选证明

**更新于 2026-11-11 · 四项等差数列至少三色 · 对应 Erdős 问题 160**

[Frobenius 障碍完整稿](FROBENIUS-OBSTRUCTIONS.zh-CN.md) · [原定量细化稿](NOTE.zh-CN.md) · [审阅与查新状态](REVIEW.md) · [有限构造数据](finite-colorings.json) · [引用](CITATION.md)

## 2026-11-11：Frobenius 构造族的统一障碍

新增稿研究 π_x(y+N(z)+β(x)Q_x(z)^τ+M(x)Q_x(z))，其中 Q_x=st+w+L(x)t、N 是三次扩域范数，β、M、L任意，π_x是独立置换。准确对象、量词和完整证明见 [正文](FROBENIUS-OBSTRUCTIONS.zh-CN.md)。

| 结论 | 参数和证据状态 |
|---|---|
| 无 ABBA 迫 β、M 为素域坐标二次，β₂各向异性，因此基底维数 d≤2 | p≥5、q=p^e、e≥2、任意非恒等 τ=p^j；文字证明已由AI助手逐步复核 |
| 每非恒定基底 AP、每指定外色都有 ABBA，排除全部 d≥1 | q=S^m、τ=S^h、gcd(h,m)=1、S≥3^(6m)；完整循环下降和点数证明 |
| 单项 Frobenius 的另一项全部正维数障碍 | M=0、e≥2j+1；完整曲线亏格与差分证明 |
| 多项加法测量的维数障碍 ed≤2dimW | 可逆变化空间，或 q≡1(mod3)且每个非零成员秩>e/2；包括若干独立多项系数族 |
| q=121 的40,656组归一化参数值集均报告覆盖 | 候选诊断；无可信独立证书，d=1或2情形尚未据此关闭 |

这些是**受限构造族的障碍**，并非任意染色下界。仍没有 α<1/4 构造、原题完整解或已确认的新颖性。文字审查、候选诊断和可信有限核验的证据等级分别保留；没有外部专家或形式化认证。本次只同步研究文档，不改变软件版本或重跑已有有限核验。

## 2026-11-02：定量细化研究稿 v0.1.0

原 v0.1.0 公开一个有完整文字推导的候选结果：对某个绝对常数 C，

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

定量细化稿的固定版本为 `0.1.0`；Frobenius 障碍稿按 `2026-11-11` 日期引用。它们与软件包的 `0.1.0.dev1` 独立。稿件、重算脚本和本项目生成的数据沿用仓库 Apache-2.0 许可；引用已有模板和工具时仍应同时注明其原始论文。

该稿由系统生成，再由 AI 助手整理和检查；没有获得外部同行评审或形式化认证。若发现错误，请在 [Issues](https://github.com/yiwenxx/ai4math-coursework-pathweaver/issues) 标明具体公式或引理。若发现等价文献，请给出原始来源及命题定位。相关修正将更新版本记录。
