# 常数标签进位控制与四项等差数列染色的定量细化

**研究稿 v0.1.0 · 2026-11-02 · PathWeaver contributors**

*Constant-label carry control and a candidate quantitative refinement for four-term arithmetic-progression colorings*

**状态：候选证明，开放审阅。正确性尚未经外部独立确认，创新性未确认；不宣称解决 Erdős 问题 160。** JSP-000158 是本项目任务编号，不是 Erdős 问题 158。

## 摘要 / Abstract

设 h(N) 为给 [N] 染色、使每条非平凡四项等差数列至少含三色所需的最小颜色数。本稿提出一个可逐步审阅的组合构造，目标结论为

$$
h(N)\le C N^{1/4}\sqrt{\log N}\,
\exp\!\left(2\sqrt{\log12\,\log N}\right)\qquad(N\ge3),
$$

其中 C 为绝对常数。具体候选贡献是 12 值数字标签的进位控制，以及只在模 p² 投影上施加辅助染色、用常数标签处理剩余步长的组合。范数核心和 1/4 主指数来自已有工作。完整论证如下；其文献新颖性和严格正确性仍需独立审查。

We give a proof draft for an explicit subexponential factor in the upper bound for colorings in which every nontrivial four-term arithmetic progression receives at least three colors. The construction combines a twelve-valued digit label with a refinement of the known cubic-norm construction. An auxiliary coloring is applied only to a projection modulo p²; the remaining steps are treated with a constant number of labels. The leading exponent remains 1/4. This is an AI-assisted research note, not an independently certified theorem or an established novelty claim.

以下对数均为自然对数，标明 log₂ 时除外。全体有限构造数据与本稿的渐近证明相互独立；有限核验不能证明本命题。

## 记号

令 $h(N)$ 为 $[0,N-1]$ 上每条非平凡整数四项 AP 至少三色所需的最小色数；令 $g(N)$ 只要求排除 ABBA，即不允许同时有
$$
c(a)=c(a+3d),\qquad c(a+d)=c(a+2d).
$$
另令 $G(m)$ 为 $\mathbb Z/m\mathbb Z$ 上排除所有非零步长 ABBA 的最小色数；对奇数 $m\ge3$，令 $H(m)$ 为完整循环条件的最小色数。所有循环条件都包括非单位步长和重复位置。

偶数模数不存在完整循环着色：步长 $m/2$ 只有两个不同位置，任何着色都至多两色。这个障碍不适用于 $G(m)$。

## 1. 常数标签与进位控制

先建立全部辅助构造所需的数字引理。对 $B\ge2$、$0\le y<B$，定义
$$
T_B=\lceil B/2\rceil,\quad D_B=T_B-1,
\quad\delta_B(y)=\min(y+1,B-y),
$$
$$
\rho_B(y)=\left(y\bmod2,\ \mathbf1_{y\ge T_B},\
\lfloor\log_2\delta_B(y)\rfloor\bmod3\right).
$$
它至多十二值。两个半区的整数直径均至多 $D_B$，且 $2D_B<B$。

设 $y_0,y_1,y_2,y_3$ 是模 $B$ AP 的标准代表元。若其 $\rho_B$ 标签满足 AABB，则四个代表元构成整数 AP。这一点对偶数 $B$ 也成立。

模步长为零时结论直接成立。否则取步长代表元 $1\le e<B$，写
$$
y_{t+1}=y_t+e-B\eta_t,\qquad\eta_t\in\{0,1\}.
$$
同半区的一对若不回绕，则 $e\le D_B$；若回绕，则 $B-e\le D_B$。二者不能同时成立，故 $\eta_0=\eta_2$。三个进位相同时已经是整数 AP；剩下的 010、101 可通过反转归为 010。

在 010 情形，
$$
y_1\ge\max(e,B-e)\ge T_B,
\qquad y_2\le\min(e-1,B-1-e)<T_B.
$$
配对同半区使首对都在上半区、末对都在下半区。令 $u=B-y_1$、$v=y_2+1$，则
$$
1\le u,v\le e,\qquad u+v=e+1,
$$
四个边界距离依次为 $u+e,u,v,v+e$。取 $w=\max(u,v)$，有
$$
2\le\frac{w+e}{w}<3.
$$
因此相应一对的二进制对数整数部分相差 1 或 2，不能模 3 相同，矛盾。

当 $B$ 为奇数时，还成立以下三条局部结论。

若标签满足 ABAB，则
$$
E_0=y_0-2y_1+y_2,\qquad E_1=y_1-2y_2+y_3
$$
均被 $B$ 整除，且均为偶数、绝对值小于 $2B$。奇数 $B$ 因而使它们被 $2B$ 整除，只能为零，所以代表元构成整数 AP。

若三个位置 $i<j<k$ 标签相同，令
$$
A=k-j,\qquad C=j-i.
$$
可能的 $(A,C)$ 为 $(1,1),(1,2),(2,1)$。加权误差
$$
E=Ay_i+Cy_k-(A+C)y_j
$$
被 $B$ 整除。同奇偶、同半区又给出
$$
E\in2\mathbb Z,\qquad |E|\le(A+C)D_B<2B.
$$
因此得到严格整数等式
$$
Ay_i+Cy_k=(A+C)y_j. \tag{1}
$$

若标签满足 ABBA，令 $e=y_2-y_1$、$f=y_3-y_0$。则 $e,f$ 都是偶数，绝对值至多 $D_B$，且 $f\equiv3e\pmod B$。由于
$$
|f-3e|\le4D_B<2B,
$$
同样得到 $f=3e$。整数 $y_0+e,y_0+2e$ 位于两个端点之间，并分别与 $y_1,y_2$ 模 $B$ 同余；标准代表元唯一性使它们就是两个内点。因此也得到整数 AP。

这里必须保留奇数模数条件。例如模 4 的 $(0,2,0,2)$ 总满足 ABAB 配对，却不是整数 AP。

另有一个适用于所有底数 $B$ 的全局整数消进位原理：
$$
\sum_{\nu=0}^{s-1}E_\nu B^\nu=0,
\quad E_\nu\in2\mathbb Z,
\quad |E_\nu|<2B
\quad\Longrightarrow\quad E_\nu=0\quad\forall\nu. \tag{2}
$$
证明是先将整个整数等式除以二，再从最低位依次模 $B$。每次所得整数都严格位于 $(-B,B)$，只能为零。这不是偶数模数上的局部除法。

## 2. 辅助着色及明确颜色计数

现在定义区间辅助着色。给定 $Q,B\ge2$，取 $s=\lceil\log_BQ\rceil$，将 $0\le x<Q$ 写为数字向量 $X=(x_0,\ldots,x_{s-1})$，并令
$$
S(X)=\sum_{\nu=0}^{s-1}x_\nu(B-1-x_\nu),
$$
$$
\mathcal A_{Q,B}(x)
=\bigl(\rho_B(x_0),\ldots,\rho_B(x_{s-1}),S(X)\bigr).
$$
色数至多
$$
K_B(Q)=12^s\left(\left\lfloor\frac{s(B-1)^2}{4}\right\rfloor+1\right). \tag{3}
$$

它排除所有非恒定单色配置
$$
Au+Cw=(A+C)v,
\qquad(A,C)\in\{(1,1),(1,2),(2,1)\}. \tag{4}
$$
事实上，若三个颜色相同，每位的加权误差均为偶数，绝对值至多 $(A+C)D_B<2B$。由 (2)，关系逐位成立。严格凹二次式 $S$ 满足
$$
S(X_v)=\frac{AS(X_u)+CS(X_w)}{A+C}
+\frac{AC}{(A+C)^2}\|X_u-X_w\|^2.
$$
三个 $S$ 值相同，迫使三个数字向量相同。

它也排除非平凡整数四项 AP 上的 ABAB 和 AABB。ABAB 时，每位的两个二阶差分都是偶数且绝对值小于 $2B$，由 (2) 得到数字向量 AP。AABB 时，最低位先由局部引理成为整数 AP；其二阶差分为零后，下一位才获得模 $B$ AP 关系。逐位归纳同样得到
$$
X_t=U+tV.
$$
两种配对均使
$$
0=S(U+3V)-S(U+2V)-S(U+V)+S(U)
=-4\|V\|^2,
$$
故 $V=0$，矛盾。三个位置同色则由 (4) 排除。这里并未声称 $\mathcal A_{Q,B}$ 排除 ABBA。

优化色数时，令 $\lambda=\log12$、$L=\log Q$，取
$$
b=\sqrt{\lambda L/2},\qquad B=\lceil e^b\rceil.
$$
将所得着色记为 $\mathcal A_Q$。利用 $s\le L/b+1$、$B-1<e^b$，其色数满足
$$
\begin{aligned}
K(Q)
&\le12^s\left(s(B-1)^2/4+1\right)\\
&\le3e^{\lambda L/b+2b}(s+4e^{-2b})\\
&\le3\left(\sqrt{\frac{2L}{\lambda}}+5\right)
 e^{2\sqrt{2\lambda L}}.
\end{aligned} \tag{5}
$$
特别地，$K(Q)=Q^{o(1)}$。

对奇数 $q\ge3$，定义
$$
\sigma_q(y)=\bigl(\mathcal A_q(y),\rho_q(y)\bigr),\qquad0\le y<q.
$$
它至多 $12K(q)$ 色，在每个非零模步长 AP 上排除三位置同色、ABAB、AABB。两个配对先由局部引理成为整数 AP，再由 $\mathcal A_q$ 排除。三个同色位置先给出 (1)，随后 (4) 迫使三个代表元相同。这意味着 $Cd=Ad=0\pmod q$；由于 $\gcd(A,C)=1$，得到 $d=0$，矛盾。因此合数模数和重复位置都已覆盖。

## 3. 范数核心与局部补充标签

接下来给出完整循环构造。先记录一个更简单的三分区引理：对任意 $m\ge2$，令
$$
b_m(y)=\lfloor3y/m\rfloor\qquad(0\le y<m).
$$
模 $m$ AP 若在此标签下满足 ABBA，则标准代表元构成整数 AP。

若 $y_1=y_2$，模步长为零。否则反转使 $e=y_2-y_1>0$。内点同箱给出 $e<m/3$，所以三步总长小于 $m$，至多回绕一次，中间一步不回绕。若第一步回绕，则 $y_0>2m/3$、$y_1<m/3$；内点同箱又使 $y_2<m/3$，从而 $y_3<2m/3$，违反外点同箱。若最后一步回绕，则 $y_2>2m/3$、$y_3<m/3$，而内点同箱使 $y_1\ge2m/3$、$y_0>m/3$，仍矛盾。因此没有回绕。

取素数 $p>3$。选择一个首一不可约三次多项式 $f_p$，令
$$
E=\mathbb F_p[T]/(f_p),\qquad\theta=T\bmod f_p.
$$
这样的多项式确实存在：对可能的根作容斥，首一无根三次多项式数为
$$
p\binom p2-\binom p3=\frac{p^3-p}{3}>0.
$$
三次多项式无根即不可约。按系数字典序取第一个即可使选择确定。

通过基 $1,\theta,\theta^2$ 将 $E$ 识别为 $\mathbb F_p^3$。令 $\mathcal N(u)$ 为乘法映射 $z\mapsto uz$ 的行列式。它是齐次三次多项式，且
$$
\mathcal N(u)=0\iff u=0, \tag{6}
$$
因为域中非零元素的乘法映射可逆。

将模 $p^4$ 的标准代表元写成
$$
x=x_0+px_1+p^2x_2+p^3x_3,
$$
定义
$$
\Psi_p(x)=\bigl(b_p(x_0),b_p(x_1),b_p(x_2),
 x_3+\mathcal N(x_0,x_1,x_2)\bigr), \tag{7}
$$
最后一个坐标在 $\mathbb F_p$ 中计算。

它排除所有非零模步长 ABBA。若出现 ABBA，从最低位应用三分区引理；每消去一位的两个严格整数二阶差分，下一位才获得模 $p$ AP 关系。最终低三位为向量 AP $U+tV$，最高位在域中为 $W+tZ$。最后一个颜色坐标为
$$
P(t)=W+tZ+\mathcal N(U+tV)
=c_0+c_1t+c_2t^2+c_3t^3.
$$
ABBA 给出
$$
c_1+3c_2+9c_3=0,
\qquad c_1+3c_2+7c_3=0.
$$
所以 $c_3=\mathcal N(V)=0$，由 (6) 得 $V=0$，随后 $Z=0$，原步长为零，矛盾。该核心的已有来源是 [Shi–Dong §4](https://arxiv.org/html/2607.20752v2#S4)。

为补足其他模式，需要一个额外的有限标签。在
$$
\mathbb F_p^\times/\{\pm1\}
$$
上，乘以 $[3]$ 的轨道形成边或环，且没有自环，因为 $3\ne\pm1\pmod p$。每个分量可三色：偶环交替两色；奇环前偶数个顶点交替两色，最后一个顶点用第三色。拉回到 $\mathbb F_p^\times$，再任意给零赋一个已有颜色，得到 $\tau_p$，满足
$$
\tau_p(z)\ne\tau_p(3z),\qquad
\tau_p(z)\ne\tau_p(-3z)\qquad(z\ne0). \tag{8}
$$
每条轨道从最小标准代表元的类开始，即可给出确定规则。

定义至多九值的
$$
\kappa_p(z)=\bigl(b_p(\bar z),\tau_p(z)\bigr),
$$
其中 $\bar z$ 为标准代表元。若三个 $\kappa_p$ 标签相同的元素之和为零，则三者全零。证明只需三分区：同属第 $j$ 箱的三个标准代表元之和在 $[jp,(j+1)p)$ 内。当 $j=1,2$ 时，因 $3\nmid p$，下端严格不能取到，故其中没有 $p$ 的倍数；当 $j=0$ 时唯一可能的倍数为零。

令 $\xi=(x_0,x_1)$，展开
$$
\mathcal N(\xi_0,\xi_1,y)
=\gamma y^3+\beta_\xi y^2+\eta_\xi y+\zeta_\xi,
\qquad\gamma=\mathcal N(0,0,1)\ne0.
$$
取
$$
s_\xi=\frac{\beta_\xi}{3\gamma},\qquad\widehat y=y+s_\xi.
$$
于是存在 $\ell_\xi,k_\xi$，使
$$
\mathcal N(\xi_0,\xi_1,y)
=\gamma\widehat y^3+\ell_\xi\widehat y+k_\xi.
$$
定义至多 108 值的
$$
\Lambda_p(x)=\bigl(\rho_p(x_2),
\kappa_p(x_2+s_{(x_0,x_1)})\bigr).
$$
注意 $\rho_p$ 作用于未移位的标准数字；这一点用于控制进位。

## 4. 完整着色与所有步长分支

最终取
$$
C_p(x)=\bigl(\Psi_p(x),
\sigma_{p^2}(x_0+px_1),\Lambda_p(x)\bigr). \tag{9}
$$
下面检查全部步长和全部坏模式。

假设非零模 $p^4$ 步长 $d$ 的四项 AP 至多两色。若没有三个同色位置，则必属 ABBA、ABAB、AABB 三种配对之一。ABBA 已由 $\Psi_p$ 排除。

若 $p^2\nmid d$，低两位构成非零模 $p^2$ AP，由 $\sigma_{p^2}$ 排除剩余模式。若 $p^3\mid d$，低三位恒定、最高位是非零方向的域上 AP；$p>3$ 使其四个值互异，$\Psi_p$ 已给出四色。

只剩 $p^2\mid d$、$p^3\nmid d$。此时 $\xi$ 恒定。记高两位为 $y_t,w_t$，则 $y_t+pw_t$ 构成模 $p^2$ AP，其方向模 $p$ 为某个 $v\ne0$。因而
$$
\widehat y_t=Y+tv,
\qquad
F_t=w_t+\gamma\widehat y_t^3+
\ell_\xi\widehat y_t+k_\xi \tag{10}
$$
是 $\Psi_p$ 的最后一个颜色坐标。

若三个位置 $i<j<k$ 同色，令 $A=k-j,C=j-i$。未移位的 $\rho_p$ 标签给出整数关系 (1)。从模 $p^2$ AP 的对应关系中减去它、再除以 $p$，得到
$$
Aw_i+Cw_k-(A+C)w_j=0\quad\text{于 }\mathbb F_p.
$$
三个 $F$ 值相同，在 (10) 中消去最高位、常数及线性项后，得到
$$
A\widehat y_i^3+C\widehat y_k^3
-(A+C)\widehat y_j^3=0.
$$
直接展开 $\widehat y_i=\widehat y_j-Cv$、$\widehat y_k=\widehat y_j+Av$，左端等于
$$
AC(A+C)v^2
(\widehat y_i+\widehat y_j+\widehat y_k). \tag{11}
$$
前因子非零，故三个移位数字之和为零。同 $\kappa_p$ 标签迫使三者全零；但它们来自非零方向的三个不同位置，特征 $p>3$ 下互异，矛盾。

若呈 ABAB 或 AABB，$\rho_p$ 先使四个 $y_t$ 成为整数 AP，随后模 $p^2$ 关系使 $w_t$ 成为域上 AP。因此 (10) 是关于 $t$ 的三次多项式，其二次、三次系数分别为
$$
c_2=3\gamma Yv^2,\qquad c_3=\gamma v^3.
$$
两种配对都蕴含
$$
0=P(3)-P(2)-P(1)+P(0)
=4c_2+18c_3
=6\gamma v^2(2Y+3v).
$$
所以 $Y=-3v/2$，四个移位数字依次为
$$
-3v/2,\quad-v/2,\quad v/2,\quad3v/2.
$$
AABB 要求第零、第一位置的 $\tau_p$ 标签相同，却是三倍关系；ABAB 要求第零、第二位置相同，却是负三倍关系。两者均违反 (8)。这完成了完整循环条件的证明。

## 5. 颜色计数与区间上界

令 $r_p=|\operatorname{im}C_p|$。由色数乘积及 (5)，
$$
\begin{aligned}
r_p
&\le27p\cdot12K(p^2)\cdot108\\
&\le104976p
\left(\sqrt{\frac{4\log p}{\lambda}}+5\right)
\exp\!\left(4\sqrt{\lambda\log p}\right),
\qquad\lambda=\log12. \tag{12}
\end{aligned}
$$
这是对实际像集大小的上界，并不要求全部形式标签都出现。

推广到所有 $N$ 使用本文未证明的 Bertrand 素数定理：对充分大的 $N$，选
$$
N^{1/4}<p<2N^{1/4}.
$$
把 $C_p$ 限制到 $[0,N-1]$。区间内的正步长小于 $p^4$，不会变成零模步长，故限制着色合法。由 $\log p=\tfrac14\log N+O(1)$，(12) 给出
$$
\log h(N)\le\frac14\log N
+2\sqrt{\lambda\log N}
+\frac12\log\log N+O(1). \tag{13}
$$
有限个小 $N$ 吸收入常数，即得开头的定量上界。


## 6. 与已有工作的区别和当前证据等级

| 内容 | 归属与状态 |
|---|---|
| 模 p⁴ 的 27p 色 ABBA 自由范数核心 | Shi–Dong §4，已有方法 |
| h(N)≤N^(1/4+o(1)) | Shi–Dong Corollary 1.3，已有主指数 |
| 数字乘积、Behrend 型辅助染色 | Deng–Tidor–Zhao 等工作的已有背景 |
| 12 值边界标签及同时排除非 ABBA 模式 | 本稿具体候选推导；等价先例尚未排除 |
| 只支付 K(p²) 开销的投影与剩余步长分支 | 本稿具体候选组合；独立审阅与查新未完成 |
| 模 22 的三色模板 | Deng–Tidor–Zhao 已公布，不是本项目新发现 |

[Shi–Dong §5，Lemma 5.3](https://arxiv.org/html/2607.20752v2#S5) 使用保留完整边界距离对数的标签，其显示计数含 $(\log M)^s$ 因子。本稿比较的是这一具体构造和计数；不能由此断言所有已知方法都没有同等或更强的余项界。[Deng–Tidor–Zhao](https://arxiv.org/html/2307.06914v2) 已有亚多项式辅助染色和数字提升方法，不能重新认领这些基本思想。

本稿的逐步检查没有发现上界链中未覆盖的步长分支；检查仍由 AI 助手完成，不等于外部专家确认。主要待审环节是边界距离对数模三的回绕排除、整数消进位、移位三次式的加权恒等式及所有少色模式的覆盖。细节与讨论入口见 [审阅说明](REVIEW.md)。

对于 N≥81，由正文的计数可以取以下显式上界候选：

$$
h(N)\le209952N^{1/4}
\left(\sqrt{\frac{\log N+4\log2}{\log12}}+5\right)
\exp\!\left(\sqrt{4\log12\log N+16\log12\log2}\right).
$$

外部存在性输入包括 Bertrand 素数定理；其余使用的有限域性质在正文中说明。这里没有声称常数最优。保留范数核心的细化至少保留其实际 27p 种颜色，因此它本身不会给出少于四分之一的主指数。

## 7. 生成、审查与适用范围

本稿由 PathWeaver 系统中的本地 Codex 模型生成和迭代，随后由 AI 助手整理、直接检查代数步骤并核对原始文献。这里公开的是经筛选的数学论证和有限构造，不以模型多次赞同作为证明。研究稿没有外部同行评审、Lean 形式化或该渐近参数族的全量计算证书。

有限构造及复现说明见 [项目页](README.md)。已有搜索没有得到 m>r⁴ 的有效 ABBA 模板，也没有证明此类模板不存在。对本稿的支持或反驳应给出具体引理、计算或原始文献中的等价命题。

## 参考文献

1. R. Shi and Y. Dong. *An Improved Upper Bound for Colorings Without Symmetrically Colored k-Term Arithmetic Progressions*. [arXiv:2607.20752v2](https://arxiv.org/html/2607.20752v2), 2026. 主要对照 §4–5。
2. M. Deng, J. Tidor and Y. Zhao. *Uniform sets with few progressions via colorings*. [arXiv:2307.06914v2](https://arxiv.org/html/2307.06914v2). 主要对照 §1、Lemma 3.2、Lemma 5.1、Lemma 7.11。

机器可读引用见 [references.bib](references.bib)。本稿应作为“未独立确认的研究稿 v0.1.0”引用，不能省略证据状态。
