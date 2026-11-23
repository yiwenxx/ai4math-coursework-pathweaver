# JSP-000158：研究进展与候选证明

**更新于 2026-11-23 · 四项等差数列至少三色 · 对应 Erdős 问题 160**

[耦合置换与非多项式刚性新稿](NONSEPARABLE-AND-NONPOLYNOMIAL-OBSTRUCTIONS.zh-CN.md) · [Frobenius 障碍完整稿](FROBENIUS-OBSTRUCTIONS.zh-CN.md) · [原定量细化稿](NOTE.zh-CN.md) · [审阅与查新状态](REVIEW.md) · [有限构造数据](finite-colorings.json) · [引用](CITATION.md)

## 2026-11-23：Lean 4 内核无条件证明的有限上界与结构阈值

本轮公开同步了一批已完成 **Lean 4 内核认证（零 Mathlib、零 `sorry`，仅依赖标准公理 `propext`/`Classical.choice`/`Quot.sound`）** 的显式有限上界、循环模板提升与区间结构阈值定理（渐近主指数相关草稿暂留私有研究仓待外部审阅，不在公开仓宣称）：

| 成果 | 精确结论 | Lean 4 内核模块与复现入口 |
|---|---|---|
| **$h(10^{18}) \le 132\,158\,016$ 及自由边界延拓** | 取素数 $p=578\,743\,129$，两位按 $x^{50\,343}\bmod p$ 着色（零并入色 $1$，每位 $11\,496$ 色），覆盖任意平移区间 $N \le 3p^2$；独立改色零列后，相同 $132\,158\,016$ 色覆盖长度达 **$3p^2+p+1=1\,004\,830\,828\,672\,875\,053$** | `CriticalSquareCertificate.lean`、`CriticalSquareIntervals.lean`、`CriticalSquareBoundary.lean`、`FreePositionProduct.lean`、`OddPowerCollisionLift.lean` |
| **$h(137) \le 9$ 与模 45 循环模板** | 模 45 的九色循环表满足 $h(45n)\le 9h(n)$；三周期重排并改色 6 处即得 137 项区间见证（全量 3,060 条非平凡 4-AP 均至少三色） | `NineColorCycle.lean`、`NineColorInterval.lean`、`results/jsp158_nine_color_cycle/template.json`、`results/jsp158_nine_color_interval/witness.json` |
| **$h(98) \le 8$ 与公开 $h(77) \le 7$ 复现** | 8 色覆盖 98 项区间（1,552 条非平凡 4-AP 全量核验通过），并内核复现 Canli 的 77 项 7 色公开见证 | `SmallIntervalWitnesses.lean` |
| **必现四色进程的精确阈值 $= 19$** | 任意合法 4-AP 至少三色区间着色中，首次强制出现四色 4-AP 的精确最小长度为 **19**（长度 18 存在全部 45 条进程恰用三色的见证） | `ForcedRainbow.lean`、`results/jsp158_forced_rainbow/certificate.py` |
| **一般递推与奇次幂碰撞提升** | 证明零位可自由改色递推 $h(pn+1)\le r h(n)$、两位循环提升、尾部乘积以及 $q=121$ 奇次幂核引理 | `TwoDigitCyclicLift.lean`、`CyclicTailProduct.lean`、`OddPower121.lean`、`QuadraticDenominator.lean`、`Jsp158Distance.lean`、`QuarterTurn.lean` |

复现命令（无需第三方 Python 依赖；Lean 核验需本地 `lake`）：

```bash
# 显式有限上界着色与预算查询
python scripts/color_jsp158_cyclic_product.py --interval-size 1000000000000000000 --budget
python scripts/color_jsp158_cyclic_product.py --interval-size 137 --budget
python scripts/color_jsp158_cyclic_product.py --interval-size 98 --budget
python results/jsp158_forced_rainbow/certificate.py
pathweaver jsp158 verify-template --three-colors results/jsp158_nine_color_cycle/template.json

# Lean 4 内核构建与核验（零 Mathlib、零 sorry）
cd formal && lake build PathWeaverFormal
```

## 2026-11-22：耦合置换、非多项式刚性与有理/陪集染色的统一分类与障碍

新增稿 [NONSEPARABLE-AND-NONPOLYNOMIAL-OBSTRUCTIONS.zh-CN.md](NONSEPARABLE-AND-NONPOLYNOMIAL-OBSTRUCTIONS.zh-CN.md) 针对前稿留下的外色耦合置换 $\pi_{(x,z)}$、非多项式/分圆高次剩余特征构造、无零点有理分母剪切、向量值四次多项式及循环乘性陪集模板给出六条分类与障碍定理，核心代数恒等式与循环核验规约已由 **Lean 4 内核（`PathWeaverFormal`）无公理认证**：

| 定理 | 精确结论 | 证据与认证状态 |
|---|---|---|
| **定理 A（$z$-耦合仿射置换二分定理）** | 对 $\pi_x(\sigma(x,z)y+F(x,z))$，$D_\sigma = \sigma_0\Delta^3\sigma - (\Delta^2\sigma)(\sigma_3-\sigma_0)$：$\mathbb{F}_p$-仿射 $\sigma$ 严格保持 $\Delta^3 F \neq 0$ 条件不变；$2 \le k \le (p+1)/2$ 次多项式切片给出非零首项 $-2(k-1)k(k+1)c_k^2 t^{2k-3}$，对**任意**函数 $F$ 强制产生 Cramer ABBA 见证 | 解析证明 + **Lean 4 内核认证** (`coupled_affine_det_forces_abba`, `coupled_affine_det_diff_identity`, `coupled_fp_affine_row_proportional`) |
| **定理 B（特征 $5$ 集合论非多项式剪切刚性）** | **不假设 $F$ 为多项式**，任意集合论映射 $F: \mathbb{F}_5^d \to \mathbb{F}_5$ 使 $\pi(y+F(z))$ 无 ABBA **当且仅当** $F$ 是各向异性三次多项式，从而必有 **$d \le 3$**（彻底排除 $\mathbb{F}_5 \times \mathbb{F}_5^4$ 上的非多项式纯剪切） | 解析证明 + **Lean 4 内核认证** (`f5_fourth_diff_sum_identity`, `f5_nonzero_orbit_forces_zero_slope`) |
| **定理 C（射影不变权重与分圆特征径向坍缩）** | $d=1$（$\mathbb{F}_{25}, \mathbb{F}_{49}$）上 $15/19/27$ 次分圆特征剪切 $W(\chi_m(z))z^3$ 全量核验无 ABBA；$d \ge 4$ 时任意 $\mathbb{F}_p^\times$-射影不变权重 $\Omega(z)$ 与非齐次三次式 $A(z)$ 沿径向 $z_i=(1+i)h$ 坍缩为 $\Delta_h^3[\Omega A](h) = 6\Omega(h)A_3(h)$，迫使 $d \le 3$ | 解析证明 + **Lean 4 内核认证** (`projective_weight_radial_cubic_collapse`) + `ff_probe.py` 全量枚举 |
| **定理 D（加法分母有理剪切 $d \le 2$ 尖锐降维）** | $\pi(y+A(z)/(\gamma+T(z)))$ ($T \neq 0, \deg A \le 3$) 无 ABBA **当且仅当** $A(w) \neq 0$ ($\forall w$) 且 $A_3(h) \neq 0$ ($\forall h \neq 0$)，将维数上限从 $d=3$ **严格压降至 $d=2$** 且逐秩可达 | 完整解析证明（有限集碰撞引理 + 齐次化 Chevalley–Warning） |
| **定理 E（循环乘性陪集障碍与 $q=121$ 闭合）** | 含 $-1\pmod m$ 的乘性子群（含 $m=257$ 全部非平凡乘性子群）在 $(-3,-1,1,3)$ 处恒有 ABBA；完成 $(m,3), m\in[23,85]$ 全部 $63$ 个模数 `UNSAT` 闭合（结合 LRAT 反证排除全量 $m\ge 23$, $s(2;3)=22$）及 $(m,4)$ 的 $3,300$ 个陪集商 `UNSAT`；$4,919,376$ 方程零信任证书正式闭合 $q=121$ 混合曲线引理 | **Lean 4 内核认证** (`checkCyclicABBAFree_sound`) + 零信任证书 (`q121_mixed_curve_certificate.json`, `jsp158_quarter_breakthrough_sweep.json`) |
| **定理 F（向量值四次多项式中点偶抵消与 $D \le 4r$ 障碍）** | 任意维数 $r \ge 1$ 的四次多项式向量染色 $P: \mathbb{F}_p^D \to \mathbb{F}_p^r$ 在中点 $(u_0-3v, u_0-v, u_0+v, u_0+3v)$ 上偶次项 $Q_4, Q_{2,u_0}$ 恒等消去，奇次泰勒总次数和为 $4r$，故 $D \ge 4r+1$ 时逐中点迫使 ABBA | 解析证明 + **Lean 4 内核认证** (`quartic_midpoint_even_cancellation`) |

## 2026-11-11：Frobenius 构造族的统一障碍

新增稿研究 π_x(y+N(z)+β(x)Q_x(z)^τ+M(x)Q_x(z))，其中 Q_x=st+w+L(x)t、N 是三次扩域范数，β、M、L任意，π_x是独立置换。准确对象、量词和完整证明见 [正文](FROBENIUS-OBSTRUCTIONS.zh-CN.md)。

| 结论 | 参数和证据状态 |
|---|---|
| 无 ABBA 迫 β、M 为素域坐标二次，β₂各向异性，因此基底维数 d≤2 | p≥5、q=p^e、e≥2、任意非恒等 τ=p^j；文字证明已由AI助手逐步复核 |
| 每非恒定基底 AP、每指定外色都有 ABBA，排除全部 d≥1 | q=S^m、τ=S^h、gcd(h,m)=1、S≥3^(6m)；完整循环下降和点数证明 |
| 单项 Frobenius 的另一项全部正维数障碍 | M=0、e≥2j+1；完整曲线亏格与差分证明 |
| 任意加法测量空间的维数障碍 ed≤2dimW | 任意Fp线性变化空间W；无最小秩或q模3条件，含秩1迹映射空间 |
| 次数≤p^h的多项Frobenius测量排除全部d≥1 | h≥2、e≥2h+1，任意独立系数及固定加法项；逐基底AP、逐外色障碍 |
| q=121 的40,656组归一化参数混合曲线全覆盖 | **2026-11-21 已补齐独立机检证书**（[证书 JSON](../../results/q121_mixed_curve_certificate.json)，4,880 个降次不可约三次式、40,656 组、4,919,376 方程零信任重算通过，约 3.3 秒；SHA256 `6e6ff98dcd4595dad3634a495176e5ba60fa321ef515c4a865413ef6ead3d8fd`） |

这些是**受限构造族的障碍**，并非任意染色下界。仍没有 α<1/4 构造、原题完整解或已确认的新颖性。`q=121` 独立证书认证的是第 10 节的有限混合曲线覆盖引理，外部专家审阅与整篇障碍稿的优先权确认仍待完成。可用标准库一键复验该证书：

```bash
python scripts/certify_q121.py verify results/q121_mixed_curve_certificate.json
```

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
