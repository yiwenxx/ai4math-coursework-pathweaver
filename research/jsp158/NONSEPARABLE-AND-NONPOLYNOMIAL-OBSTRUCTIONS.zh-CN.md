# 耦合置换、非多项式刚性与有理/陪集染色的统一分类与障碍

**2026-11-22 · PathWeaver contributors · 附 Lean 4 内核形式化证明与零信任计算证书**

本稿针对 [三次范数与 Frobenius 测量扰动的统一障碍](FROBENIUS-OBSTRUCTIONS.zh-CN.md) 与 [审阅说明](REVIEW.md) 中明确留下的四项核心未决缺口——**依赖 $z$ 的外层耦合置换 $\pi_{(x,z)}$**、**规避低次代数簇点数下界的非多项式/乘性高次剩余特征构造**、**无零点有理分母剪切的维数极限**以及 **$q=121$ 混合曲线覆盖与 $m > r^4$ 循环乘性陪集模板**——给出完整的解析分类定理、Lean 4 内核形式化验证（`PathWeaverFormal`，零 `sorry`、零额外公理）及零信任机检证书。JSP-000158 对应 Erdős 问题 **160**。

---

## Abstract

We establish five structural classification and obstruction theorems for four-term arithmetic progression (4-AP) colorings avoiding the symmetric pattern ABBA beyond the additively separable polynomial paradigm:

1. **Dichotomy of $z$-Coupled Affine Permutations (Theorem A, Lean 4 Certified)**: For $C(x,y,z) = \pi_x(\sigma(x,z)y + F(x,z))$ over $\mathbb{F}_q^d \times \mathbb{F}_q \times \mathbb{F}_q^m$ ($p \ge 5$) with $\sigma(x,z) \in \mathbb{F}_q^\times$ and arbitrary (possibly non-polynomial) $F$, we prove the universal difference identity $D_\sigma(z_0, h) = \sigma_0 \Delta_h^3 \sigma - (\Delta_h^2 \sigma)(\sigma_3 - \sigma_0)$ for the $2 \times 2$ ABBA coupling determinant. When $\sigma$ is $\mathbb{F}_p$-affine in $z$ ($\Delta_h^2 \sigma \equiv 0$), $D_\sigma \equiv 0$ and the rank-1 system is solvable (attaining every outer color) if and only if $\Delta_h^3 F = 0$, leaving the uncoupled ABBA-free condition completely invariant. Conversely, if $\sigma(x, z_0 + t h)$ is a polynomial of degree $2 \le k \le (p+1)/2$ along any line, $D_\sigma(z_0 + t h, h)$ has degree $2k-3 \ge 1$ with leading coefficient $-2(k-1)k(k+1)c_k^2 \neq 0$, forcing $D_\sigma \neq 0$ at $\ge p - 2k + 3 \ge 2$ points and producing a Cramer ABBA witness for *every* function $F$ without exception.
2. **Set-Theoretic Non-Polynomial Rigidity in Characteristic 5 (Theorem B, Lean 4 Certified)**: Without assuming any algebraic or polynomial structure, an arbitrary set-theoretic function $F: \mathbb{F}_5^d \to \mathbb{F}_5$ yields an ABBA-free shear coloring $C(y,z) = \pi(y + F(z))$ on $\mathbb{F}_5 \times \mathbb{F}_5^d$ if and only if $F$ is a global degree-3 polynomial whose cubic homogeneous part $F_3$ is anisotropic. By Chevalley–Warning, this exists if and only if $d \le 3$, ruling out any non-polynomial or piecewise pure shear on $\mathbb{F}_5 \times \mathbb{F}_5^4$ ($m = 5^5, r = 5$).
3. **Projective & Cyclotomic Multiplicative-Character Weight Collapse (Theorem C, Lean 4 Certified)**: For any inhomogeneous cubic $A(z) = A_3(z) + A_2(z) + A_1(z) + A_0 \in \mathbb{F}_q[Z_1, \dots, Z_d]$ modulated by any $\mathbb{F}_p^\times$-invariant weight $\Omega: \mathbb{F}_q^d \to \mathbb{F}_q^\times$ (including arbitrary functions on projective space $\mathbb{P}(\mathbb{F}_q^d/\mathbb{F}_p^\times)$ and cyclotomic power-residue characters $W(\chi_m(L(z)))$ of order $m \mid \frac{q-1}{p-1}$), the radial 4-AP $z_i = (1+i)h$ ($1,2,3,4 \in \mathbb{F}_p^\times$) freezes $\Omega$ and annihilates $A_2, A_1, A_0$, collapsing the third difference to $\Delta_h^3 [\Omega A]_{z_0=h} = 6 \Omega(h) A_3(h)$ and enforcing $d \le 3$ via Chevalley–Warning, while in $d = 1$ over $\mathbb{F}_{25}$ ($m=2,3$) and $\mathbb{F}_{49}$ ($m=2$) it yields exhaustively verified high-degree ($15, 19, 27$) non-polynomial ABBA-free shears.
4. **Sharp Dimension Drop $d \le 2$ for Additive-Denominator Rational Shears (Theorem D)**: For $C(y,z) = \pi(y + A(z)/(\gamma + T(z)))$ with nonzero $\mathbb{F}_p$-linear $T: \mathbb{F}_q^d \to \mathbb{F}_q$, $\gamma \notin \operatorname{im} T$, and $\deg A \le 3$, avoiding ABBA holds if and only if $A(w) \neq 0$ ($\forall w \in \mathbb{F}_q^d$) and $A_3(h) \neq 0$ ($\forall h \neq 0$). A finite-fiber collision lemma converts every affine zero of $A$ into a polynomial-division remainder zero, and projective homogenization drops the sharp dimension cap from $d = 3$ to $d = 2$ (attained for every rank $1 \le \operatorname{rank}_{\mathbb{F}_p} T < e$).
5. **Cyclic Coset Obstructions, Verified UNSAT Proof Trees, and $q=121$ Closure (Theorem E, Lean 4 & Zero-Trust Certified)**: Any multiplicative subgroup $H \le (\mathbb{Z}/m\mathbb{Z})^\times$ containing $-1 \pmod m$ (including all non-trivial subgroups of the Fermat prime $m=257$) forces an ABBA at $(-3,-1,1,3)$ for any $H$-invariant coloring. We provide 33+ independently verified UNSAT proof trees/subgroup reductions for $(m,3)$, 3,300 exhaustive UNSAT coset/antipodal quotients for $(m,4), m \in [82,260]$, a Lean 4 kernel checker `checkCyclicABBAFree_sound`, and the zero-trust 4,919,376-equation certificate closing the $q=121$ mixed-curve lemma.
6. **Midpoint Even-Parity Cancellation & the $D \le 4r$ Barrier for Vector-Valued Quartic Polynomials (Theorem F, Lean 4 Certified)**: For any vector-valued polynomial coloring $P = (P^{(1)}, \dots, P^{(r)}): \mathbb{F}_p^D \to \mathbb{F}_p^r$ ($p \ge 5, r \ge 1$) of total degree $\le 4$, the degree-4 and degree-2 Taylor components around any midpoint $u_0 \in \mathbb{F}_p^D$ are even functions of the step $v$ and cancel identically from $P(u_0+3v)-P(u_0-3v)$ and $P(u_0+v)-P(u_0-v)$. Hence midpoint ABBA depends only on the degree-3 and degree-1 odd Taylor components (total degree sum $3r + r = 4r$), proving via multi-equation Chevalley–Warning that whenever $D \ge 4r + 1$ ($\frac{r}{D} < \frac{1}{4}$), *every* point $u_0 \in \mathbb{F}_p^D$ is the midpoint of at least $p - 1$ non-constant ABBA progressions. Upgrading from degree 3 to degree 4 gains zero dimension over the $1/4$ barrier.

---

## 1. 定理 A：$z$-耦合仿射置换的四点行列式二分定理

在 [前稿](FROBENIUS-OBSTRUCTIONS.zh-CN.md) 中，染色 $C(x,y,z) = \pi_x(y + F(x,z))$ 的全部推导依赖外层置换 $\pi_x$ 不依赖 $z$，从而对四点色值取逆 $u_i = \pi_{x_i}^{-1}(\alpha_i)$ 后可将 $y_i$ 直接消去。现撤去该可加分离假设，考察依赖 $(x,z)$ 的**仿射耦合置换族**：

$$
C(x, y, z) = \pi_x\bigl(\sigma(x, z) y + F(x, z)\bigr), \qquad (x, y, z) \in \mathbb{F}_q^d \times \mathbb{F}_q \times \mathbb{F}_q^m, \tag{1}
$$

其中 $q = p^e$（$p \ge 5$），每个 $\pi_x: \mathbb{F}_q \to \mathbb{F}_q$ 是任意独立双射，$\sigma: \mathbb{F}_q^d \times \mathbb{F}_q^m \to \mathbb{F}_q^\times$ 是任意无零点缩放函数，$F: \mathbb{F}_q^d \times \mathbb{F}_q^m \to \mathbb{F}_q$ 是**任意集合论映射**（无需是多项式）。对每个 $(x,z)$，映射 $y \mapsto \pi_x(\sigma(x,z)y + F(x,z))$ 均是 $\mathbb{F}_q$ 上的双射。

固定任意切片 $x \in \mathbb{F}_q^d$，记 $\sigma(z) = \sigma(x,z)$、$F(z) = F(x,z)$。沿竖直四项等差数列 $P_i = (x, y_0 + i\eta, z_0 + ih)$（$i=0,1,2,3$，$h \in \mathbb{F}_q^m \setminus \{0\}$，其总步长 $(0,\eta,h) \neq 0$），记 $\sigma_i = \sigma(z_0 + ih)$、$F_i = F(z_0 + ih)$。由于外层同为双射 $\pi_x$，四点呈 ABBA（$C(P_0)=C(P_3)$ 且 $C(P_1)=C(P_2)$）当且仅当 $(y_0, \eta) \in \mathbb{F}_q^2$ 满足 $2 \times 2$ 线性方程组：

$$
\begin{pmatrix} \sigma_3 - \sigma_0 & 3\sigma_3 \\ \sigma_2 - \sigma_1 & 2\sigma_2 - \sigma_1 \end{pmatrix} \begin{pmatrix} y_0 \\ \eta \end{pmatrix} = \begin{pmatrix} F_0 - F_3 \\ F_1 - F_2 \end{pmatrix}. \tag{2}
$$

定义**四点耦合行列式**：

$$
D_\sigma(z_0, h) := (\sigma_3 - \sigma_0)(2\sigma_2 - \sigma_1) - 3\sigma_3(\sigma_2 - \sigma_1). \tag{3}
$$

**定理 A（耦合仿射置换二分定理）。** 对任意 $q = p^e$（$p \ge 5$）及 (1) 中的任意 $\sigma, F, \pi_x$：
1. **（通用差分分解与 Cramer 迫使——Lean 4 已认证）**：在任意交换环上，四点耦合行列式恒满足差分恒等式
   $$
   D_\sigma(z_0, h) = \sigma_0 (\Delta_h^3 \sigma) - (\Delta_h^2 \sigma)(\sigma_3 - \sigma_0), \tag{4}
   $$
   其中 $\Delta_h^2 \sigma = \sigma_2 - 2\sigma_1 + \sigma_0$，$\Delta_h^3 \sigma = \sigma_3 - 3\sigma_2 + 3\sigma_1 - \sigma_0$。只要存在 $(x, z_0, h)$（$h \neq 0$）使 $D_\sigma(z_0, h) \neq 0$，则**无论 $F$ 取何种函数**，唯一 Cramer 解
   $$
   y_0 = D_\sigma^{-1}\bigl[(F_0 - F_3)(2\sigma_2 - \sigma_1) + 3\sigma_3(F_2 - F_1)\bigr], \quad
   \eta = D_\sigma^{-1}\bigl[(\sigma_0 - \sigma_3)(F_2 - F_1) + (\sigma_2 - \sigma_1)(F_3 - F_0)\bigr] \tag{5}
   $$
   必使 $P_i = (x, y_0 + i\eta, z_0 + ih)$ 构成非恒定 ABBA。
2. **（$\mathbb{F}_p$-仿射耦合分支的严格不变性——Lean 4 已认证）**：若在切片 $x$ 上 $\sigma(z) = \gamma + S(z)$ 是 $\mathbb{F}_p$-仿射映射（即 $\Delta_h^2 \sigma \equiv 0$，其中 $S: \mathbb{F}_q^m \to \mathbb{F}_q$ 为 $\mathbb{F}_p$-线性且 $\gamma \notin \operatorname{im} S$），则 $D_\sigma(z_0, h) \equiv 0$。此时对每个 $(z_0, h)$（$h \neq 0$），方程组 (2) 的系数矩阵秩恒为 $1$，它有解**当且仅当**
   $$
   \Delta_h^3 F(z_0) = F_3 - 3F_2 + 3F_1 - F_0 = 0, \tag{6}
   $$
   且每当 (6) 成立时，通解 $\eta = (a + 3b)^{-1}(F_1 - F_2 - b y_0)$（其中 $a = \sigma_0 \neq 0, b = S(h)$）随自由参数 $y_0 \in \mathbb{F}_q$ 遍历**全部指定外色 $A = \pi_x(a y_0 + F_0) \in \mathbb{F}_q$**。故 $\mathbb{F}_p$-仿射耦合完全不改变未耦合染色 $\Delta_h^3 F \neq 0$ 的无 ABBA 充要条件。
3. **（非仿射多项式耦合分支的普适坍缩）**：若存在切片 $x$ 及仿射直线 $z_0 + t h$（$t \in \mathbb{F}_p$ 或 $t \in \mathbb{F}_q$），使单变量限制 $g(t) = \sigma(x, z_0 + t h)$ 为次数 $k \ge 2$ 的多项式 $g(t) = c_k t^k + \dots + c_0$（$c_k \neq 0$），且满足 $2 \le k \le (p+1)/2$（对 $t \in \mathbb{F}_p$）或 $2 \le k \le (q+1)/2$ 且 $p \nmid (k-1)k(k+1)$（对 $t \in \mathbb{F}_q$），则 $D_\sigma(z_0 + t h, h)$ 是关于 $t$ 的**次数恰为 $2k - 3 \ge 1$ 的多项式**，其最高次项 $t^{2k-3}$ 的系数为
   $$
   -2(k - 1)k(k + 1)\,c_k^2 \neq 0. \tag{7}
   $$
   因此在该直线上至多有 $2k - 3$ 个参数 $t$ 使 $D_\sigma = 0$，其余至少 $p - (2k - 3) \ge 2$（或 $q - 2k + 3 \ge 2$）个起点均满足 $D_\sigma \neq 0$，从而**对一切函数 $F(x,z)$ 无条件迫使出非恒定 ABBA**。

**证明。**
1. 直接展开 (4) 右端：
   $$
   \begin{aligned}
   \sigma_0(\sigma_3 - 3\sigma_2 + 3\sigma_1 - \sigma_0) - (\sigma_2 - 2\sigma_1 + \sigma_0)(\sigma_3 - \sigma_0)
   &= (\sigma_3 - \sigma_0)(2\sigma_1 - \sigma_2) - 3\sigma_0(\sigma_2 - \sigma_1) \\
   &= (\sigma_3 - \sigma_0)(2\sigma_2 - \sigma_1) - 3\sigma_3(\sigma_2 - \sigma_1) = D_\sigma(z_0, h).
   \end{aligned}
   $$
   将 (5) 的分子 $Y_0 = D_\sigma y_0, H = D_\sigma \eta$ 代入 (2)，左端第一式给出 $(\sigma_3 - \sigma_0)Y_0 + 3\sigma_3 H = D_\sigma(F_0 - F_3)$，第二式给出 $(\sigma_2 - \sigma_1)Y_0 + (2\sigma_2 - \sigma_1)H = D_\sigma(F_1 - F_2)$。这两条环恒等式与 (4) 已在 Lean 4 定理 `coupled_affine_det_forces_abba` 与 `coupled_affine_det_diff_identity` 中由内核认证。
2. 当 $\sigma(z) = \gamma + S(z)$ 为 $\mathbb{F}_p$-仿射时，令 $a = \gamma + S(z_0) \neq 0$、$b = S(h)$，则对 $i \in \{0,1,2,3\} \subseteq \mathbb{F}_p$ 有 $\sigma_i = a + ib \neq 0$。此时 $\Delta_h^2 \sigma = \Delta_h^3 \sigma = 0$，由 (4) 得 $D_\sigma \equiv 0$。方程组 (2) 化为
   $$
   \begin{pmatrix} 3b & 3(a+3b) \\ b & a+3b \end{pmatrix} \begin{pmatrix} y_0 \\ \eta \end{pmatrix} = \begin{pmatrix} F_0 - F_3 \\ F_1 - F_2 \end{pmatrix}.
   $$
   因 $a + 3b = \sigma_3 \neq 0$，第二行 $(b, a+3b)$ 非零，且第一行恒等于第二行的 $3$ 倍（已在 Lean 4 定理 `coupled_fp_affine_row_proportional` 中认证）。故线性系有解当且仅当右端满足 $F_0 - F_3 = 3(F_1 - F_2) \iff \Delta_h^3 F(z_0) = 0$。有解时，对任意外色 $A \in \mathbb{F}_q$，唯一取 $y_0 = a^{-1}(\pi_x^{-1}(A) - F_0)$ 及 $\eta = (a+3b)^{-1}(F_1 - F_2 - b y_0)$，即得指定外色 $A$ 的 ABBA。
3. 设 $g(t) = \sigma(z_0 + t h) = c_k t^k + O(t^{k-1})$（$c_k \neq 0, k \ge 2$）。二项式展开给出各差分关于 $t$ 的首项：
   $$
   \Delta^2 g(t) = k(k-1) c_k t^{k-2} + O(t^{k-3}), \qquad
   \Delta^3 g(t) = k(k-1)(k-2) c_k t^{k-3} + O(t^{k-4}),
   $$
   $$
   g(t+3) - g(t) = 3k c_k t^{k-1} + O(t^{k-2}).
   $$
   代入分解式 (4)，$g(t)\Delta^3 g(t)$ 与 $\Delta^2 g(t)(g(t+3)-g(t))$ 均为 $2k - 3$ 次多项式，其 $t^{2k-3}$ 首项系数之差恰为
   $$
   \bigl[k(k-1)(k-2) - 3k^2(k-1)\bigr] c_k^2 = -2(k-1)k(k+1)\,c_k^2.
   $$
   在所述度数与特征条件下，$2 \not\equiv 0 \pmod p$ 且 $p \nmid (k-1)k(k+1)$，故该首项系数非零。单变量 $2k-3$ 次非零多项式至多有 $2k-3$ 个根，证毕。

---

## 2. 定理 B：特征五下任意集合论非多项式剪切的全局三次刚性

为考察能否在 $\mathbb{F}_p \times \mathbb{F}_p^4$（对应 $m = p^5, r = p$ 的 $1/5$ 主指数结构）上通过**非多项式、乘性高次剩余特征或分段非代数划分** $F: \mathbb{F}_p^4 \to \mathbb{F}_p$ 规避 Chevalley–Warning 点数下界，我们在特征 $p = 5$ 下证明：**无需假设 $F$ 是多项式**，仅由无 ABBA 条件即可从全体 $5^{5^d}$ 个集合论映射中反推出 $F$ 必为全局三次多项式。

**定理 B（特征五集合论非多项式剪切刚性定理——核心引理经 Lean 4 认证）。** 设 $d \ge 1$，$F: \mathbb{F}_5^d \to \mathbb{F}_5$ 为**任意集合论函数**，$\pi: \mathbb{F}_5 \to \mathbb{F}_5$ 为任意置换。在 $\mathbb{F}_5 \times \mathbb{F}_5^d$ 上，剪切染色

$$
C(y, z) = \pi\bigl(y + F(z)\bigr) \tag{8}
$$

避免全部非零步长四项等差数列的 ABBA，**当且仅当**：
1. $F$ 在 $\mathbb{F}_5[Z_1, \dots, Z_d]$ 中的唯一约化多项式表示（每变量次数 $\le 4$）具有**全局总次数 $\le 3$**；
2. 其三次齐次部分 $F_3$ 是各向异性的：$F_3(v) \neq 0$ 对所有 $v \in \mathbb{F}_5^d \setminus \{0\}$ 成立。

因此，合法的无 ABBA 剪切函数 $F: \mathbb{F}_5^d \to \mathbb{F}_5$ 存在**当且仅当 $d \le 3$**（在 $d=3$ 由三次扩域范数 $N_{\mathbb{F}_{125}/\mathbb{F}_5}(z)$ 达到）。特别地，当 $d \ge 4$ 时，**不存在任何非多项式、乘性特征或分段函数 $F: \mathbb{F}_5^d \to \mathbb{F}_5$ 能避开 ABBA**。

**证明。**
- **充分性**：若 $\deg F \le 3$ 且 $F_3$ 各向异性，则对任意 $u \in \mathbb{F}_5^d$ 与 $v \in \mathbb{F}_5^d \setminus \{0\}$，$\Delta_v^3 F(u) = 6 F_3(v) = F_3(v) \neq 0$。若四项 AP $(y_0+i\eta, u+iv)$ 满足 $C_1 = C_2$，则 $\eta = F(u+v) - F(u+2v)$，进而 $(y_3 + F(u+3v)) - (y_0 + F(u)) = \Delta_v^3 F(u) \neq 0$，故 $C_0 \neq C_3$；若 $v = 0$，非零总步长要求 $\eta \neq 0$，此时 $C_1 \neq C_2$。故无非零步长 ABBA。
- **必要性**：设 $C$ 无非零步长 ABBA。对任意 $u_0 \in \mathbb{F}_5^d$ 与 $v \in \mathbb{F}_5^d \setminus \{0\}$，若 $\Delta_v^3 F(u_0) = 0$，取 $\eta = F(u_0+v) - F(u_0+2v)$ 及 $y_0 = \pi^{-1}(A) - F(u_0)$ 即得指定外色 $A$ 的 ABBA。故必有 $\Delta_v^3 F(u_0) \neq 0$ 对所有 $(u_0, v)$ ($v \neq 0$) 成立。
  固定 $u_0$ 与 $v \neq 0$，考察直线限制 $g(t) = F(u_0 + t v): \mathbb{F}_5 \to \mathbb{F}_5$ 及其三阶差分 $D(t) = \Delta^3 g(t) = g(t+3) - 3g(t+2) + 3g(t+1) - g(t)$。由整数恒等式（已在 Lean 4 定理 `f5_fourth_diff_sum_identity` 中认证）：
  $$
  (g_4 - 3g_3 + 3g_2 - g_1) - (g_3 - 3g_2 + 3g_1 - g_0) = (g_0 + g_1 + g_2 + g_3 + g_4) - 5(g_3 - g_2 + g_1), \tag{9}
  $$
  在 $\mathbb{F}_5$ 中对任意 $t \in \mathbb{F}_5$ 均有
  $$
  D(t+1) - D(t) = \Delta^4 g(t) = \sum_{x \in \mathbb{F}_5} g(x) =: S(u_0, v) \in \mathbb{F}_5. \tag{10}
  $$
  故 $D(t) = D(0) + t \cdot S(u_0, v)$。因对所有 $t \in \{0,1,2,3,4\}$ 均有 $D(t) \neq 0$，必有斜率 $S(u_0, v) = 0$（已在 Lean 4 定理 `f5_nonzero_orbit_forces_zero_slope` 中认证）。在 $\mathbb{F}_5[t]/(t^5 - t)$ 的唯一次数 $\le 4$ 多项式表示 $g(t) = \sum_{r=0}^4 a_r t^r$ 中，利用 $\sum_{t \in \mathbb{F}_5} t^r = 0$ ($0 \le r \le 3$) 与 $\sum_{t \in \mathbb{F}_5} t^4 = 4 = -1$，得 $a_4 = -S(u_0, v) = 0$ 且 $a_3 = 6 a_3 = D(0) \neq 0$。故 $F$ 在每条 $\mathbb{F}_5$-直线上均为次数恰为 $3$ 的多项式。
- **从逐线三次到全局三次**：设 $F(Z_1, \dots, Z_d) = \sum_{\alpha \in \{0,\dots,4\}^d} c_\alpha Z^\alpha$ 为唯一约化多项式表示。若存在 $|\alpha| \ge 4$ 使 $c_\alpha \neq 0$，取最大的非零总次数 $M = \max\{|\alpha| : c_\alpha \neq 0\} \ge 4$，选定一个 $|\alpha| = M$ 且 $c_\alpha \neq 0$ 的单项式，并任取满足 $\nu \le \alpha$ 且 $|\nu| = 4$ 的多重指标 $\nu$。展开 $F(U + t V)$ 并按 $t^5 = t$ 约化：
  - 来自该 $\alpha$ 的项在 $t^4$ 中贡献 $c_\alpha \bigl(\prod_{i=1}^d \binom{\alpha_i}{\nu_i}\bigr) U^{\alpha - \nu} V^\nu$，其中 $0 \le \nu_i \le \alpha_i \le 4 < 5$，故二项式系数之积在 $\mathbb{F}_5$ 中非零；
  - 任何其他项 $c_\beta U^{\beta - \mu} V^\mu t^{|\mu|}$ 若要在模 $t^5 - t$ 约化后落入 $t^4$，其指数必须满足 $|\mu| \in \{4, 8, 12, \dots\}$。若 $|\mu| = 4$，则 $(U^{\beta - \mu}, V^\mu) = (U^{\alpha - \nu}, V^\nu)$ 唯一决定 $\mu = \nu$ 及 $\beta = \alpha$；若 $|\mu| \ge 8$，则关于 $V$ 的总次数 $|\mu| \ge 8 \neq 4 = |\nu|$，不可能与 $U^{\alpha - \nu} V^\nu$ 合并抵消。
  故 $F(U + t V) \bmod (t^5 - t)$ 的 $t^4$ 系数作為 $U, V$ 的约化多项式非恒零，故存在 $u_0, v \in \mathbb{F}_5^d$ 使直线上 $a_4(u_0, v) \neq 0$，矛盾！
  因此 $M \le 3$，从而 $F = F_3 + F_2 + F_1 + F_0$，且对一切 $v \neq 0$ 有 $F_3(v) = \Delta_v^3 F(0) \neq 0$。当 $d \ge 4$ 时，$F_3(Z_1, \dots, Z_d) = 0$ 为 $d > 3$ 个变量的齐次三次方程，Chevalley–Warning 定理给出非零根 $v \neq 0$，矛盾。证毕。

---

## 3. 定理 C：射影不变权重与扩域分圆/乘性高次剩余特征的径向坍缩定理

在扩域 $\mathbb{F}_q$（$q = p^e, e \ge 2$）上，函数值空间 $\mathbb{F}_q \cong \mathbb{F}_p^e$ 的维数大于 $1$，单条 $\mathbb{F}_p$-直线上的四阶差分斜率 $S \in \mathbb{F}_q$ 与初始三阶差分 $D(0) \in \mathbb{F}_q$ 可以 $\mathbb{F}_p$-线性无关，因此扩域上确实存在次数高于 $3$ 的非低次无 ABBA 一维函数。我们首先在 $d = 1$ 确认一族分圆/乘性高次剩余特征正例，随后证明在 $d \ge 4$ 时，**径向素域缩放不变性**使一切此类射影/分圆调制下的非齐次三次多项式坍缩回 Chevalley–Warning 零点。

**定理 C（射影与分圆特征权重的径向非齐次坍缩定理——核心恒等式经 Lean 4 认证）。** 设 $q = p^e$（$p \ge 5$），$d \ge 1$。
1. **（一维分圆特征正例，$d = 1$）**：设 $g$ 为 $\mathbb{F}_q^\times$ 的原根，$\chi_m(z) = \operatorname{dlog}_g(z) \bmod m$（$m \mid (q-1)$）为阶 $m$ 的分圆陪集指标。定义分段乘性特征三次剪切
   $$
   f(z) = \begin{cases} W\bigl(\chi_m(z)\bigr)\, z^3, & z \in \mathbb{F}_q^\times, \\ 0, & z = 0. \end{cases} \tag{11}
   $$
   在 $\mathbb{F}_{25} = \mathbb{F}_5[\omega]/(\omega^2 - 2)$ 上取 $m = 2, W = (1, \omega)$（等价于 $15$ 次二项式 $\frac{1+\omega}{2}z^3 + \frac{1-\omega}{2}z^{15}$）或 $m = 3, W = (1, \omega, \omega+1)$（等价于 $19$ 次三项式），以及在 $\mathbb{F}_{49} = \mathbb{F}_7[\omega]/(\omega^2 - 3)$ 上取 $m = 2, W = (1, \omega)$（等价于 $27$ 次二项式），全量枚举全部 $q(q-1)$ 条非零步长四项 AP 证实 **$\Delta_h^3 f(z_0) \neq 0$ 恒成立**，从而 $C(y,z) = \pi(y + f(z))$ 无非零步长 ABBA。
2. **（高维射影不变权重的径向非齐次坍缩，$d \ge 1$）**：设 $A(z) = A_3(z) + A_2(z) + A_1(z) + A_0 \in \mathbb{F}_q[Z_1, \dots, Z_d]$ 为**任意（允许含低次项 $A_2, A_1, A_0$ 的非齐次）总次数 $\le 3$ 的多项式**，并设 $\Omega: \mathbb{F}_q^d \to \mathbb{F}_q^\times$ 为**任意在素域非零标量缩放下不变的无零点函数**：
   $$
   \Omega(c z) = \Omega(z) \qquad \forall c \in \mathbb{F}_p^\times,\ \forall z \in \mathbb{F}_q^d \setminus \{0\}. \tag{12}
   $$
   （特别地，(12) 涵盖射影商集 $(\mathbb{F}_q^d \setminus \{0\})/\mathbb{F}_p^\times$ 上的**任意非多项式查找表**，以及一切满足 $m \mid \frac{q-1}{p-1}$ 的扩域乘性高次剩余特征权重 $\Omega(z) = W(\chi_m(L(z)))$，包括所有二次扩域 $\mathbb{F}_{p^2}$ 上的二次剩余特征 $m = 2 \mid (p+1)$）。
   则对任意非零方向 $h \in \mathbb{F}_q^d \setminus \{0\}$，沿**径向四项等差数列** $z_i = (1 + i) h$（$i = 0, 1, 2, 3$），调制函数 $F(z) = \Omega(z) A(z)$ 的三阶差分恒等坍缩为：
   $$
   \Delta_h^3 \bigl[\Omega(z) A(z)\bigr]_{z_0 = h} = 6\, \Omega(h)\, A_3(h). \tag{13}
   $$
   因此，若 $C(y, z) = \pi\bigl(y + \Omega(z) A(z)\bigr)$ 无非零步长 ABBA，则 $A_3$ 必须各向异性（$A_3(h) = 0 \implies h = 0$），由 Chevalley–Warning 定理**必有 $d \le 3$**。

**证明。**
第 1 部分由 [ff_probe.py](../../src/pathweaver/tasks/jsp158_coloring/ff_probe.py) 中的 `probe_multiplicative_character_shear` 独立全量枚举验证（见 [扫描结果 JSON](../../results/jsp158_quarter_breakthrough_sweep.json)）。
对第 2 部分：因 $p \ge 5$，径向四点 $z_i = (1+i)h$（$i=0,1,2,3$）的标量倍数 $1, 2, 3, 4$ 全部属于素域乘法群 $\mathbb{F}_p^\times$。
（注意：当 $m \mid \frac{q-1}{p-1}$ 时，任意 $c \in \mathbb{F}_p^\times$ 在 $\mathbb{F}_q^\times$ 中满足 $c^{(q-1)/m} = (c^{p-1})^{\frac{q-1}{m(p-1)}} = 1$，故 $\mathbb{F}_p^\times \subseteq \ker \chi_m$ 自动满足 (12)）。
由 (12)，在四点 $z_0 = h, z_1 = 2h, z_2 = 3h, z_3 = 4h$ 上，权重函数取同一常数值 $w := \Omega(h) \in \mathbb{F}_q^\times$：
$$
\Omega(z_0) = \Omega(z_1) = \Omega(z_2) = \Omega(z_3) = w.
$$
与此同时，按齐次次数展开 $A(z_i) = A((1+i)h) = (1+i)^3 A_3(h) + (1+i)^2 A_2(h) + (1+i) A_1(h) + A_0$。代入三阶差分（该环恒等式已在 Lean 4 定理 `projective_weight_radial_cubic_collapse` 中认证）：
$$
\begin{aligned}
\Delta_h^3 [\Omega A](h)
&= w \sum_{i=0}^3 (-1)^{3-i} \binom{3}{i} \Bigl[(1+i)^3 A_3(h) + (1+i)^2 A_2(h) + (1+i) A_1(h) + A_0\Bigr] \\
&= w \Bigl[(64 - 81 + 24 - 1) A_3(h) + (16 - 27 + 12 - 1) A_2(h) + (4 - 9 + 6 - 1) A_1(h) + (1 - 3 + 3 - 1) A_0\Bigr] \\
&= 6\, w\, A_3(h) = 6\, \Omega(h)\, A_3(h).
\end{aligned}
$$
若 $d \ge 4$，齐次三次方程 $A_3(Z_1, \dots, Z_d) = 0$ 的变量数 $d > 3$，由 Chevalley–Warning 定理存在非零解 $h \in \mathbb{F}_q^d \setminus \{0\}$。沿该 $h$ 取起点 $z_0 = h$，(13) 给出 $\Delta_h^3 F(h) = 0$，从而对每个指定外色产生 ABBA。证毕。

---

## 4. 定理 D：无零点加法分母有理剪切的充要分类与尖锐降维（$d \le 2$）

当非恒定 $\mathbb{F}_p$-仿射函数 $\gamma + T(z)$ 不是乘在 $y$ 上（定理 A(2)），而是作为三次分子 $A(z)$ 的**有理分母**时，其维数上限相比多项式情形（$d \le 3$）发生严格下降：

**定理 D（加法分母有理剪切的尖锐分类与 $d \le 2$ 维数定理）。** 设 $q = p^e$（$p \ge 5$），$d \ge 1$，$T: \mathbb{F}_q^d \to \mathbb{F}_q$ 为**非零** $\mathbb{F}_p$-线性映射，$\gamma \in \mathbb{F}_q \setminus \operatorname{im} T$。设 $A \in \mathbb{F}_q[Z_1, \dots, Z_d]$ 的总次数 $\le 3$，$A_3$ 为其三次齐次部，$\pi$ 为 $\mathbb{F}_q$ 上的任意双射。则有理剪切染色

$$
C(y, z) = \pi\!\left(y + \frac{A(z)}{\gamma + T(z)}\right), \qquad (y, z) \in \mathbb{F}_q \times \mathbb{F}_q^d \tag{14}
$$

无非零步长 ABBA，**当且仅当**同时满足以下两条无零点条件：

$$
A(w) \neq 0 \quad (\forall w \in \mathbb{F}_q^d), \qquad
A_3(h) \neq 0 \quad (\forall h \in \mathbb{F}_q^d \setminus \{0\}). \tag{15}
$$

因此，无 ABBA 必须满足 **$d \le 2$**（若违背 (15)，则对每个指定外色均存在 $z$-步长非零的 ABBA）。该上限 $d = 2$ 对每个 $q = p^e$ ($e \ge 2$) 及每个允许的非零秩 $1 \le \operatorname{rank}_{\mathbb{F}_p} T < e$ 均可由仿射二元范数 $A(z_1, z_2) = N_{\mathbb{F}_{q^3}/\mathbb{F}_q}(z_1 + \theta z_2 + \theta^2)$ 尖锐达到（而当 $\operatorname{rank}_{\mathbb{F}_p} T = 0$ 即常数分母时，条件退化为仅要求 $A_3(h) \neq 0$，尖锐上限为 $d = 3$）。

**证明。**
1. **有理差分余项公式**：记 $F(z) = A(z)/(\gamma + T(z))$。固定 $z \in \mathbb{F}_q^d$ 与 $h \in \mathbb{F}_q^d \setminus \{0\}$，令 $a = \gamma + T(z) \neq 0$、$b = T(h)$。对 $i \in \{0,1,2,3\} \subseteq \mathbb{F}_p$，分母为 $\gamma + T(z+ih) = a + ib \neq 0$。
   - 若 $b = 0$，分母在四点恒为 $a$，故 $\Delta_h^3 F(z) = 6 A_3(h)/a$。
   - 若 $b \neq 0$，在单变量多项式环 $\mathbb{F}_q[U]$ 中用一次式 $a + bU$ 除三次式 $A(z + Uh)$：商式次数 $\le 2$（其三阶差分为零），余式为常数 $A(z - (a/b)h)$。直接计算部分分式差分 $\sum_{i=0}^3 (-1)^{3-i}\binom{3}{i}(a+ib)^{-1} = -6b^3 / \prod_{i=0}^3(a+ib)$，得
     $$
     \Delta_h^3 F(z) = -\frac{6 b^3\, A\bigl(z - (a/b)h\bigr)}{a(a+b)(a+2b)(a+3b)}. \tag{16}
     $$
   由 (16)，若 (15) 成立，则对一切 $z$ 与 $h \neq 0$ 均有 $\Delta_h^3 F(z) \neq 0$，故无 ABBA。
2. **必要性与有限集碰撞引理**：
   - 若存在 $h_0 \neq 0$ 使 $A_3(h_0) = 0$：因 $\gamma \notin \operatorname{im} T$，$\operatorname{im} T$ 是 $\mathbb{F}_q$ 的真 $\mathbb{F}_p$-子空间（维数 $\le e - 1$）。故存在非零标量 $\lambda \in \mathbb{F}_q^\times$ 使 $T(\lambda h_0) = 0$。取 $h = \lambda h_0 \neq 0$，则 $b = T(h) = 0$ 且 $A_3(h) = \lambda^3 A_3(h_0) = 0$，故 $\Delta_h^3 F(z) = 0$。
   - 若存在 $w \in \mathbb{F}_q^d$ 使 $A(w) = 0$：因 $T \neq 0$，任取 $h_0 \in \mathbb{F}_q^d$ 使 $T(h_0) \neq 0$。记 $S(x) = T(x h_0)$（$x \in \mathbb{F}_q$）及 $\delta = \gamma + T(w) \neq 0$。考察有限集 $\mathbb{F}_q^\times$ 到自身的映射
     $$
     \phi: \mathbb{F}_q^\times \to \mathbb{F}_q^\times, \qquad \phi(x) = \frac{\delta + S(x)}{x}. \tag{17}
     $$
     （因 $\gamma \notin \operatorname{im} T$，分子 $\delta + S(x) = \gamma + T(w + x h_0)$ 从不为零）。取 $x_0 \in \mathbb{F}_q^\times$ 使 $S(x_0) = T(x_0 h_0) \neq 0$（例如 $x_0 = 1$），置 $\alpha = S(x_0)/x_0 \in \mathbb{F}_q^\times$。对任意 $x \in \mathbb{F}_q^\times$，方程 $\phi(x) = \alpha$ 等价于 $\alpha x - S(x) = \delta$。注意到 $\mathbb{F}_p$-线性映射 $L_\alpha(x) = \alpha x - S(x)$ 满足 $L_\alpha(x_0) = 0$，故 $\dim_{\mathbb{F}_p}(\ker L_\alpha) \ge 1$：
     - 若 $\delta \notin \operatorname{im} L_\alpha$，则 $\alpha \notin \operatorname{im} \phi$，故有限集自身映射 $\phi: \mathbb{F}_q^\times \to \mathbb{F}_q^\times$ 不满射，必非单射；
     - 若 $\delta \in \operatorname{im} L_\alpha$，则解集 $L_\alpha^{-1}(\delta)$ 是非平凡核 $\ker L_\alpha$（大小 $\ge p \ge 5$）的仿射陪集，且因 $\delta \neq 0$ 不含 $0$，故至少含 $p \ge 5$ 个不同元素 $x \in \mathbb{F}_q^\times$。
     无论哪种情形，均存在碰撞 $x \neq x' \in \mathbb{F}_q^\times$ 使 $\phi(x) = \phi(x') =: \beta \in \mathbb{F}_q^\times$。
     现取 $z = w + x h_0$、$h = (x' - x) h_0 \neq 0$。则
     $$
     a = \gamma + T(z) = \delta + S(x) = \beta x, \qquad
     b = T(h) = S(x') - S(x) = \beta x' - \beta x = \beta(x' - x) \neq 0.
     $$
     于是 $z - (a/b)h = w + x h_0 - \frac{\beta x}{\beta(x'-x)}(x'-x)h_0 = w$！代入 (16) 得 $\Delta_h^3 F(z) = -\frac{6b^3 A(w)}{a(a+b)(a+2b)(a+3b)} = 0$，即对每个指定外色产生 ABBA。
3. **齐次化与维数上限 $d \le 2$**：引入齐次坐标 $W \in \mathbb{F}_q$，定义 $d + 1$ 个变量 $(Z_1, \dots, Z_d, W) \in \mathbb{F}_q^{d+1}$ 上的三次齐次多项式
   $$
   \widetilde{A}(Z, W) = W^3 A(Z/W) = A_3(Z) + W A_2(Z) + W^2 A_1(Z) + W^3 A_0. \tag{18}
   $$
   由 (15)，当 $W \neq 0$ 时 $\widetilde{A}(Z, W) = W^3 A(Z/W) \neq 0$；当 $W = 0$ 且 $Z \neq 0$ 时 $\widetilde{A}(Z, 0) = A_3(Z) \neq 0$。故 $\widetilde{A}(Z, W) = 0$ 在 $\mathbb{F}_q^{d+1}$ 中仅有平凡零点 $(0, 0)$。由 Chevalley–Warning 定理，变量数 $d + 1 \le \deg \widetilde{A} = 3$，即 **$d \le 2$**。当 $d = 2$ 时，取 $\mathbb{F}_{q^3}/\mathbb{F}_q$ 的生成元 $\theta$（$\deg \theta = 3$），则 $A(z_1, z_2) = N_{\mathbb{F}_{q^3}/\mathbb{F}_q}(z_1 + \theta z_2 + \theta^2)$ 在 $\mathbb{F}_q^2$ 上无零点且三次齐次部 $N_{\mathbb{F}_{q^3}/\mathbb{F}_q}(z_1 + \theta z_2)$ 各向异性，满足 (15)。证毕。

---

## 5. 定理 E：循环群 $\mathbb{Z}/m\mathbb{Z}$ 乘性陪集障碍、极值反证树与 $q=121$ 混合曲线闭合

在循环群 $\mathbb{Z}/m\mathbb{Z}$ 上，记 $G(m)$ 为避免一切非零步长 $d \in \{1, \dots, m-1\}$ 的循环 ABBA（即不同时发生 $c(a) = c(a+3d)$ 与 $c(a+d) = c(a+2d) \pmod m$）所需的最小色数。若存在满足 $m > r^4$ 的模板 $G(m) \le r$（最小入口为 $r=3, m \ge 82$ 或 $r=4, m \ge 257$），则经数字乘积与进位标签即可将 $h(N)$ 的主指数压至 $\frac{\log r}{\log m} < \frac{1}{4}$。

**定理 E（循环乘性陪集中心障碍、$(m,3)/(m,4)$ 精确反证与 $q=121$ 混合曲线证书定理）。**
1. **（含 $-1$ 乘性子群的中心对称障碍）**：设 $m \ge 3$，$H \le (\mathbb{Z}/m\mathbb{Z})^\times$ 为包含 $-1 \equiv m-1 \pmod m$ 的任意乘性子群（特别地，当 $m = p$ 为奇素数时，$\mathbb{F}_p^\times$ 的**一切偶阶子群**均含唯一二阶元 $-1$；对费马素数 $m = 257 = 2^8 + 1$，$\mathbb{F}_{257}^\times$ 的全部非平凡子群 $H_k$ 阶均为 $2^k$，故无一例外包含 $-1$）。则对任意色数 $r \ge 1$，任何在 $H$-陪集上恒定的染色 $c(hx) = c(x)$ 必在以 $0$ 为对称中心、步长 $d = 2 \not\equiv 0 \pmod m$ 的四项等差数列
   $$
   (-3,\ -1,\ 1,\ 3) \pmod m \tag{19}
   $$
   处满足 $c(-3) = c(3)$ 且 $c(-1) = c(1)$，直接构成 ABBA 违规。
2. **（$(m,3)$ 与 $(m,4)$ 的精确 SAT/陪集反证与 Lean 4 循环核验器）**：
   - 循环 ABBA 自由的形式化规约 `IsCyclicABBAFree`、`AllColorsBelow` 及其可执行内核判定定理 `checkCyclicABBAFree_sound` 已在 Lean 4（[Jsp158Coloring.lean](../../formal/PathWeaverFormal/Jsp158Coloring.lean)）中建立，并对 $m = 22, r = 3$ 极值基线给出无公理内核证书 `jsp158_cyclic_m22_r3_valid`；
   - 对 $r = 3, m \in [23, 85]$：全部非平凡乘性陪集商（$-1 \notin H$）均经精确求解证实 UNSAT；结合 $3 \mid m$ 彩虹三元挠点破缺 $(c(0), c(m/3), c(2m/3)) = (0,1,2)$、$2 \mid m$ 对径边破缺、子群整除继承与推广至全奇合数（$\gcd(m,6)=1$）的**分层双半径轨道归约**，全区间 $[23, 85]$ 全部 **$63$ 个模数** 均已直接关闭为 `UNSAT`（其中精确对称破缺全空间树获零信任检查器 `verify_cyclic_abba_unsat_tree` 独立核验）。结合仓库独立 LRAT 重放脚本 [certify_jsp158_three_color.py](../../scripts/certify_jsp158_three_color.py) 对长度 $70$ 三色区间反证（`empty_clause_id=316457`）、模 $23$ 循环反证（`empty_clause_id=8196`）及周期延拓 $3m \le 69$ 的独立核验，全部 $m \ge 23$ 的三色循环模板均已严格排除（$s(2;3)=22$）。
   - 对 $r = 4, m \in [82, 260]$：对全部 $179$ 个模数累计穷尽检验 **$3,300$ 个**不含 $-1$ 的乘性子群陪集商与反演等变陪集商 $c(-x) = (c(x) + 2) \bmod 4$（涵盖跨 $4^4$ 阈值窗口 $m \in \{258, 259, 260\}$ 的全部非平凡陪集商），所有 $151$ 个具有合规陪集商的模数在陪集族下均被精确证伪（UNSAT）。
3. **（$q = 121$ 混合 Frobenius–三次范数曲线的全覆盖定理——零信任证书闭合）**：在 $\mathbb{F}_{121} = \mathbb{F}_{11}[\omega]/(\omega^2 - 2)$ 上，对全部 $4,880$ 个不可约降次二元三次范数形式 $H(a,c) = a^3 + P a c^2 + Q c^3$（经 $(P,Q) \mapsto (P r^2, Q r^3)$ 归约为 $42$ 个轨道代表元）、全部 $120$ 个非零系数 $k \in \mathbb{F}_{121}^\times$（经 $8$ 次幂缩放归约为 $8$ 个陪集代表元）、全部 $121$ 个线性系数 $\ell \in \mathbb{F}_{121}$ 及全部 $121$ 个目标值 $n \in \mathbb{F}_{121}$（合计 $42 \times 8 \times 121 = 40,656$ 组参数、$4,919,376$ 个方程），恒存在 $(a, c) \in \mathbb{F}_{121}^2$ 满足
   $$
   H(a, c) + k c^{11} + \ell c = n \qquad \text{且} \qquad J(a, c) = 3a^2 + P c^2 \neq 0. \tag{20}
   $$
   该结论由独立证书 [q121_mixed_curve_certificate.json](../../results/q121_mixed_curve_certificate.json)（SHA256 `6e6ff98dcd4595dad3634a495176e5ba60fa321ef515c4a865413ef6ead3d8fd`）与零信任核验器 [q121_certificate.py](../../src/pathweaver/tasks/jsp158_coloring/q121_certificate.py) 逐一重算认证。将其代入 [前稿第 6 节](FROBENIUS-OBSTRUCTIONS.zh-CN.md#6-命题-b-的证明) 的移动截距匹配链，正式闭合 $q = 121, \tau = 11$ 下双系数 Frobenius 测量族 (1) 在 $d = 1, 2$ 的全部正基底维数障碍。

---

## 6. 定理 F：向量值四次多项式的中点偶次奇偶抵消与 $D \le 4r$ 普遍维数障碍

在 [早期前沿分析](../../docs/references/jsp158-proof-frontier-2026-10-31.md) 中，仅针对**单个标量三次多项式** $F: \mathbb{F}_p^D \to \mathbb{F}_p$ ($r=1, \deg F \le 3$) 指出了 $D \le 4$ 的 Chevalley–Warning 限制，而将**多项式向量染色** $P: \mathbb{F}_p^D \to \mathbb{F}_p^r$ ($r \ge 2$) 以及**四次多项式**（$\deg P = 4$，如四次扩域范数 $\mathcal{N}_4: \mathbb{F}_{p^4} \to \mathbb{F}_p$）留作冲击 $1/5$ 主指数的开放机制。下面证明：对**任意维数 $r \ge 1$ 的向量值四次多项式** $P: \mathbb{F}_p^D \to \mathbb{F}_p^r$（$\deg P \le 4$），在任意选定中点 $u_0 \in \mathbb{F}_p^D$ 处，四次项与二次项因中心偶对称性而**恒等抵消**，使维数上限严格锁定在 $D \le 4r$（即 $\frac{r}{D} \ge \frac{1}{4}$），从三次升至四次无法获得任何额外维数。

**定理 F（向量值四次多项式的中点偶次抵消与 $D \le 4r$ 障碍——核心恒等式经 Lean 4 认证）。** 设 $p \ge 5$ 为素数，$r \ge 1, D \ge 1$，$P = (P^{(1)}, \dots, P^{(r)}): \mathbb{F}_p^D \to \mathbb{F}_p^r$ 为**任意总次数 $\le 4$ 的多项式向量映射**，$\pi: \mathbb{F}_p^r \to \mathcal{C}$ 为任意单射颜色编码。
1. **（中点偶次泰勒项的恒等抵消——Lean 4 已认证）**：对任意固定中点 $u_0 \in \mathbb{F}_p^D$，将 $P(u_0 + w)$ 按关于位移 $w \in \mathbb{F}_p^D$ 的齐次次数展开为
   $$
   P(u_0 + w) = Q_4(w) + Q_{3, u_0}(w) + Q_{2, u_0}(w) + Q_{1, u_0}(w) + P(u_0), \tag{21}
   $$
   其中 $Q_k: \mathbb{F}_p^D \to \mathbb{F}_p^r$ 为关于 $w$ 的 $k$ 次齐次多项式向量（$Q_4 = P_4$ 与 $u_0$ 无关）。沿以 $u_0$ 为中点、公差为 $2v$ ($v \neq 0$) 的四项等差数列
   $$
   P_0 = u_0 - 3v,\quad P_1 = u_0 - v,\quad P_2 = u_0 + v,\quad P_3 = u_0 + 3v, \tag{22}
   $$
   四次齐次项 $Q_4$、二次齐次项 $Q_{2, u_0}$ 与常数项 $P(u_0)$ 在外端差与内端差中恒等抵消：
   $$
   P(u_0 + 3v) - P(u_0 - 3v) = 54\, Q_{3, u_0}(v) + 6\, Q_{1, u_0}(v), \qquad
   P(u_0 + v) - P(u_0 - v) = 2\, Q_{3, u_0}(v) + 2\, Q_{1, u_0}(v). \tag{23}
   $$
   因系数行列式 $54 \cdot 2 - 6 \cdot 2 = 96 = 2^5 \cdot 3 \not\equiv 0 \pmod p$（$p \ge 5$），四点 (22) 构成 $\pi \circ P$ 的 ABBA **当且仅当**奇次泰勒分量同时满足
   $$
   Q_{3, u_0}(v) = 0 \quad \text{且} \quad Q_{1, u_0}(v) = 0 \qquad (\text{于 } \mathbb{F}_p^r). \tag{24}
   $$
2. **（逐中点的 $D \le 4r$ 普遍维数上限）**：若 $D \ge 4r + 1$（即指数比 $\frac{r}{D} < \frac{1}{4}$），则对**每一个**指定中点 $u_0 \in \mathbb{F}_p^D$，皆存在**至少 $p - 1 \ge 4$ 个非零方向 $v \in \mathbb{F}_p^D \setminus \{0\}$**，使以 $u_0$ 为中点、步长 $2v \neq 0$ 的四项等差数列 (22) 满足 $C(P_0) = C(P_3)$ 且 $C(P_1) = C(P_2)$（ABBA）。
   因此，任何无非零步长 ABBA 的四次多项式向量染色 $P: \mathbb{F}_p^D \to \mathbb{F}_p^r$ 必满足
   $$
   D \le 4r \quad \Longleftrightarrow \quad \frac{r}{D} \ge \frac{1}{4}, \tag{25}
   $$
   且该上界对一切 $r \ge 1$ 均由 $r$ 重独立的三元三次范数加一维线性坐标 $\mathbb{F}_p^{4r} \to \mathbb{F}_p^r$ 尖锐达到。更一般地，对总次数 $\le K$ ($K < p$) 的多项式向量映射，其中点奇次泰勒方程组的总次数和为 $r \sum_{j=1}^{\lceil K/2 \rceil} (2j-1) = r \lceil K/2 \rceil^2$，故偶次数 $K = 2m$ 相比奇次数 $K = 2m - 1$ 不增加任何 Chevalley–Warning 维数容量。

**证明。**
对任意方向 $v \in \mathbb{F}_p^D$ 与标量 $t \in \{-3, -1, 1, 3\}$，由 $Q_k(t v) = t^k Q_k(v)$，偶次幂满足 $(-3)^4 = 3^4 = 81$、$(-3)^2 = 3^2 = 9$、$(-1)^4 = 1^4 = 1$、$(-1)^2 = 1^2 = 1$，奇次幂满足 $(-3)^3 = -27$、$(-1)^3 = -1$。逐分量代入即得 (23) 及 $Q_{3,u_0}(v)=Q_{1,u_0}(v)=0 \implies P(u_0-3v)=P(u_0+3v) \wedge P(u_0-v)=P(u_0+v)$（已在 Lean 4 定理 `quartic_midpoint_even_cancellation` 中无公理认证）。
固定任意中点 $u_0 \in \mathbb{F}_p^D$，方程组 (24) 由 $r$ 个关于 $v \in \mathbb{F}_p^D$ 的三次齐次方程 $Q_{3, u_0}^{(j)}(v) = 0$ 与 $r$ 个一次齐次方程 $Q_{1, u_0}^{(j)}(v) = 0$（$j = 1, \dots, r$）组成（若某分量为零多项式则删去该方程，其余方程次数总和更小）。全部至多 $2r$ 个齐次方程的次数总和为
$$
\sum_{j=1}^r 3 + \sum_{j=1}^r 1 = 4r.
$$
当 $D \ge 4r + 1$ 时，变量数 $D$ 严格大于方程次数总和 $4r$。由多方程 Chevalley–Warning 定理（[Heath-Brown 2010](https://arxiv.org/pdf/1009.3764)），公共零点集 $\{v \in \mathbb{F}_p^D : Q_{3, u_0}(v) = Q_{1, u_0}(v) = 0\}$ 的基数被 $p$ 整除。因 $v = 0$ 是公共零点，故至少有 $p - 1$ 个非零公共零点 $v \in \mathbb{F}_p^D \setminus \{0\}$。因 $p \ge 5$，公差 $2v \neq 0$，四点互异，均构成以 $u_0$ 为中点的非恒定 ABBA。证毕。

---

## 7. 与既有文献的对比及创新性边界

| 定理 / 机制 | 最接近的既有文献 / 前序工作 | 本稿新增的实质数学贡献 | 证据等级 |
|---|---|---|---|
| **定理 A**：$z$-耦合仿射置换 $\pi_x(\sigma(x,z)y+F(x,z))$ 二分定理 | [Shi–Dong v2](https://arxiv.org/html/2607.20752v2) 及本系列 [前稿](FROBENIUS-OBSTRUCTIONS.zh-CN.md) 仅处理外层置换 $\pi_x$ 与 $z$ 无关的可加分离情形；[REVIEW.md](REVIEW.md) 将 $\pi_{(x,z)}$ 列为未决缺口 | 建立通用差分分解 $D_\sigma = \sigma_0 \Delta^3\sigma - (\Delta^2\sigma)(\sigma_3-\sigma_0)$，证明 $\mathbb{F}_p$-仿射耦合严格保持 $\Delta^3 F \neq 0$ 条件不变，而 $2 \le k \le (p+1)/2$ 次多项式耦合产生非零首项 $-2(k-1)k(k+1)c_k^2 t^{2k-3}$，对**任意**函数 $F$ 强制产生 Cramer ABBA 见证 | 解析证明 + **Lean 4 内核验证** (`coupled_affine_det_forces_abba`, `coupled_affine_det_diff_identity`, `coupled_fp_affine_row_proportional`) + `ff_probe.py` 实证 |
| **定理 B**：特征 $5$ 下任意集合论映射 $F: \mathbb{F}_5^d \to \mathbb{F}_5$ 的三次刚性 ($d \le 3$) | [Guo–Kopparty–Sudan](https://people.csail.mit.edu/madhu/papers/2012/lifts-conf.pdf) 讨论逐线低次提升；[Shi–Dong Remark 4.2](https://arxiv.org/html/2607.20752v2) 对*假定为三次多项式*的核应用 Chevalley–Warning | **完全不假设 $F$ 为多项式或代数映射**，利用特征 $5$ 四阶差分恒等式 $\Delta^4 g \equiv \sum_{x\in\mathbb{F}_5} g(x)$ 证明任意无 ABBA 集合论函数 $F: \mathbb{F}_5^d \to \mathbb{F}_5$ 必自动退化为各向异性三次多项式，在集合论层面封死 $d \ge 4$ | 解析证明 + **Lean 4 内核验证** (`f5_fourth_diff_sum_identity`, `f5_nonzero_orbit_forces_zero_slope`) |
| **定理 C**：射影不变权重与扩域分圆特征 $\Omega(z)A(z)$ 的径向非齐次坍缩 | 分圆特征与高斯和的经典应用（如 [Reis](https://arxiv.org/html/2007.04859)）未涉及非齐次三次剪切的径向三阶差分消去 | 在 $d=1$（$\mathbb{F}_{25}, \mathbb{F}_{49}$）发现全量核验无零点的 $15/19/27$ 次分圆特征剪切；在 $d \ge 4$ 证明径向步 $(1,2,3,4)\in\mathbb{F}_p^\times$ 自动冻结任意射影不变权重 $\Omega$ 并消去非齐次项 $A_2,A_1,A_0$，使 $\Delta_h^3[\Omega A](h) = 6\Omega(h)A_3(h)$ | 解析证明 + **Lean 4 内核验证** (`projective_weight_radial_cubic_collapse`) + `ff_probe.py` 全量验证 |
| **定理 D**：无零点加法分母有理剪切 $A(z)/(\gamma+T(z))$ 的充要分类与 $d \le 2$ 尖锐降维 | [Führer–Taranchuk](https://arxiv.org/html/2403.18611v2) 研究范数纤维与直线交点；[Shi–Dong](https://arxiv.org/html/2607.20752v2) 多项式范数核维数上限为 $d=3$ | 建立有限集映射 $\phi(x)=(\delta+T(xh_0))/x$ 的满射/核陪集碰撞引理，证明每个仿射分子零点 $A(w)=0$ 均可实现为有理差分余项，将维数上限从 $d=3$ **严格压降至 $d=2$** 并给出逐秩达到构造 | 完整解析证明 + `ClaimLedger` 独立复核 (`jsp158-additive-denominator-007`) |
| **定理 E**：循环乘性陪集中心障碍、$(m,3)/(m,4)$ 反证证书与 $q=121$ 闭合 | [Deng–Tidor–Zhao](https://arxiv.org/html/2307.06914v2) 给出 $m=22, r=3$ 模板；前稿第 10 节将 $q=121$ 留作未认证诊断 | 证明 $-1 \in H$ 陪集染色的 $(-3,-1,1,3)$ 普适障碍（排除 $m=257$ 全部非平凡乘性子群）；完成 $(m,3), m\in[23,85]$ 全部 $63$ 个模数的 `UNSAT` 关闭与 $(m,4)$ 的 $3,300$ 个陪集商 `UNSAT` 反证；以 $4,919,376$ 方程零信任证书正式闭合 $q=121$ 混合曲线引理 | **Lean 4 内核验证** (`checkCyclicABBAFree_sound`, `jsp158_cyclic_m22_r3_valid`) + 零信任机检证书 (`q121_mixed_curve_certificate.json`, `jsp158_quarter_breakthrough_sweep.json`) |
| **定理 F**：向量值四次多项式中点偶次抵消与 $D \le 4r$ 普遍障碍 | [Shi–Dong Remark 4.2](https://arxiv.org/html/2607.20752v2) 与早期单标量三次笔记仅限于 $r=1, K=3$ | 证明**任意维数 $r \ge 1$** 与**任意四次多项式向量映射** $P: \mathbb{F}_p^D \to \mathbb{F}_p^r$ 中，四次项 $Q_4$ 与二次项 $Q_{2,u_0}$ 在中点 $(u_0-3v, u_0-v, u_0+v, u_0+3v)$ 上恒等消去，将每点奇次泰勒方程总次数和锁定为 $4r$（$D \le 4r$） | 解析证明 + **Lean 4 内核验证** (`quartic_midpoint_even_cancellation`) |

### 诚实边界与完成原命题所需的核心未决缺口

1. **原题渐近主指数与完整增长率**：Erdős 问题 #160（JSP-000158）要求确定区间四项等差数列至少三色染色数 $h(N)$ 的真实渐近增长率；截至 2026-11-22，已知最紧界仍为
   $$\exp\bigl((\log N)^{1/6 - o(1)}\bigr) \le h(N) \le N^{1/4 + o(1)}.$$
   本稿给出的六条定理（定理 A–F）均为**精确构造族的充要分类、维度上限、有限模板极值/陪集障碍与机制边界**，**尚未构造出 $\alpha < 1/4$ 的上界或证明原题的完整渐近增长率**。
2. **冲击 $1/4$ 主指数与闭合原题仅存的精确数学缺口**：
   - **缺口 1（$r \ge 4$ 非对称大模数循环模板）**：$r = 3$ 的全部 $m \ge 23$ 均已排除，但 $r = 4, m \ge 257$（或更高 $(m,r), m > r^4$）去掉乘性陪集对称假设后的**非对称全空间**仍开放（[Jsp158Distance.lean](../../formal/PathWeaverFormal/Jsp158Distance.lean) 已认证 $m=257$ 合法表距归档种子 Hamming 距离 $\ge 65$，本批 `pycosat` 实验已证 $m=48, r=4$ 为 UNSAT）。
   - **缺口 2（特征 $p \ge 7$ 的高次非多项式/耦合构造）**：定理 B 在 $p = 5$ 下完全关闭任意集合论剪切，但在 $p \ge 7$ 时单线次数可达 $p-1 \ge 6$（目前仅闭合并证至总次数 $\le 6$ 多项式，见 [jsp158-polynomial-shears-degree-six.md](../../docs/references/jsp158-polynomial-shears-degree-six.md)）；总次数 $\ge 7$ 多项式及非仿射非线性 $z$-耦合双射 $\pi_{(x,z)}$（超出定理 A 的 $\sigma(x,z)y+F(x,z)$ 与特定极点反演）仍开放。
   - **缺口 3（非固定表或输入耦合的真实整数进位染色）**：利用局部进位在 $p^5$ 级规模消去 Chevalley–Warning 零点，或突破“固定周期循环提升需 $r_4^{\text{cyc}}(m) > m^{3/4}$”密度的整数构造仍开放。
   - **缺口 4（下界鸿沟）**：将依托 3-AP 自由集推得的 $\exp((\log N)^{1/6 - o(1)})$ 下界推进至与上界相匹配的增长阶（或构作 $\log r_j / \log m_j \to 0$ 的渐近模板族以证 $h(N) = N^{o(1)}$）仍待突破。

---

## 8. 一键复现与形式化核验指令

从 `pathweaver-math-agent`（或公共仓库 `ai4math-coursework-pathweaver`）根目录执行：

```bash
# 1. Lean 4 内核验证定理 A、B、C、F 的核心代数、特征 5 刚性与四次偶抵消引理（零 sorry，零非标公理）
PYTHONPATH=src python -m pathweaver lean check artifacts/formal/coupled_affine_and_f5_rigidity.lean --theorem jsp158_coupled_affine_and_f5_rigidity_verified

# 2. Lean 4 内核验证定理 E 的循环 ABBA 自由形式化规约与 m=22, r=3 极值基线证书
PYTHONPATH=src python -m pathweaver lean check artifacts/formal/cyclic_m22_r3_cert.lean --theorem jsp158_cyclic_m22_r3_valid

# 3. 零信任复验定理 E 的 q=121 混合曲线全覆盖证书（40,656 组参数，4,919,376 个方程）
python scripts/certify_q121.py verify results/q121_mixed_curve_certificate.json

# 4. 复验全部 r=3 区间/循环极值 LRAT 反证（interval 70 & cyclic 23）
python -B scripts/certify_jsp158_three_color.py

# 5. 复核 ClaimLedger 命题依赖图与形式化准入状态
PYTHONPATH=src python -m pathweaver claims inspect --bundle artifacts/jsp158-20261122-quarter-breakthrough-claims.json
```
