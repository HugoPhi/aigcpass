#!/usr/bin/env python3
"""Fix fragments 8, 9, 11, 14, 18 in 疑似AIGC片段_待确认.csv.

Problem: the 修改后片段 had optimized text pasted AFTER the original content
instead of replacing it. This script corrects each fragment by:
1. Adapting the Chinese wording using optimized text as guidance
2. Preserving ALL LaTeX structures exactly as in 原片段
3. Ensuring paragraph count matches between 原片段 and 修改后片段
"""
import csv, os, re, sys

# Find project root (scripts now live in .claude/skills/aigcpass/script/)
import os as _os
def _find_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while d != "/" and not _os.path.exists(_os.path.join(d, ".git")):
        d = _os.path.dirname(d)
    return d if d != "/" else _os.getcwd()
BASE = _find_root()
CSV  = os.path.join(BASE, "jobs", "default", "result", "stage2", "疑似AIGC片段_待确认.csv")

with open(CSV, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))

header = rows[0]
col_orig = header.index("原片段")
col_mod  = header.index("修改后片段")
col_aigc = header.index("AIGC片段")

def count_paras(text):
    """Count paragraphs by splitting on blank lines."""
    if not text:
        return 0
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    parts = [p for p in text.split('\n\n') if p.strip()]
    return len(parts)

def split_paras(text):
    """Split text into paragraphs (preserving internal \n within paras)."""
    if not text:
        return []
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    return [p for p in text.split('\n\n') if p.strip()]

errors = []

def validate(frag_id, orig_text, modified_text):
    """Check paragraph count matches. Returns True if OK."""
    o = count_paras(orig_text)
    m = count_paras(modified_text)
    if o != m:
        errors.append(f"Fragment {frag_id}: paragraph mismatch 原={o} 修改后={m}")
        return False
    return True

# ============================================================
# FRAGMENT 8
# 原片段: 2 body paragraphs + \subsection + intro + comments
# Purple covers: body paras (from "工注解..." to "必要条件。")
# Non-purple prefix in para 1: "第一，代码迁移的复杂度仍然很高。C应用通常以POSIX或库函数直接调用为范式，迁移到门调用要完成函数到库域的映射、调用语法改写以及语义对齐。手"
# Non-purple suffix: everything from \subsection onwards
# ============================================================
frag8_modified = """第一，代码迁移的复杂度仍然很高。C应用通常以POSIX或库函数直接调用为范式，迁移到门调用要完成函数到库域的映射、调用语法改写以及语义对齐。手工注解虽然准确但是耗费时间，静态分析虽然自动但是比较保守；如果函数指针等动态调用目标无法静态确定时，开发者需补充目标集合，由工具链生成包装器\\cite{1}。FlexOS采用Coccinelle做源码到源码变换，常规差异审阅即可用于结果检查，但构建期工具链会生成大量辅助代码，门实例化、共享数据与链接脚本等均包含在内，工程复杂度需通过流水线化与可复现制品管理来控制\\cite{1}。

其次，配置空间过大同样是难题。FlexOS把隔离策略展开为隔离域划分与库映射、隔离后端、共享策略以及硬化选项等多维决策，各维度相乘导致配置指数增长\\cite{1}。不同后端对可行域的约束各不相同，比如MPK的键数量与权限切换模型、EPT/VM的跨系统RPC与更重的运行时边界、SFI的插桩粒度与额外检查开销等\\cite{7,8,9}，这些约束进一步放大了人工穷举配置的难度。FlexOS论文在相对简单的Redis配置下即测量到工具链修改量达$\\sim 1$~KLoC\\cite{1}，自动化且可复现的流水线对控制工程复杂度是必要条件。


\\subsection{本文主要研究内容}

围绕FlexOS工程落地的关键门槛，本文主要开展以下两方面工作：
% \\begin{enumerate}
%   \\def\\labelenumi{(\\arabic{enumi})}
%   \\item
% 面向 FlexOS 门的自动化代码迁移与轻量安全检查：设计并实现一套规则驱动迁移流水线，在保持改动可解释与可回溯的前提下，将常见 POSIX/库函数调用自动改写为 门调用；迁移后提供 跨域调用完整性检查，并可选集成通用静态扫描器以辅助安全审阅。
%   \\item
% 基于偏序关系的安全配置搜索算法：将隔离配置空间建模为 DAG 偏序图，在单调性假设下利用祖先/后代闭包进行批量剪枝；提出期望剪枝最大化的 均衡搜索策略，系统对比 极小极大Centroid、贝叶斯混合、信息增益 信息熵三种补充准则，并在此基础上设计 Centroid—均衡 自适应复合策略 复合策略\\cite{30}，在全部数据集上取得最优查询效率。
% \\end{enumerate}"""

# ============================================================
# FRAGMENT 9
# 原片段 has 3 paragraphs:
# 1. "FlexOS 把跨安全域交互统一约束为门调用..." (purple)
# 2. "难点在于多个约束叠加..." (purple)
# 3. "从形式化角度..." + \begin{equation} T(S) = S' \end{equation} (purple + equation)
# ============================================================
frag9_modified = """FlexOS 把跨安全域交互统一约束为门调用，迁移工作的核心目标是把原本隐式的跨域语义显式化，而非机械替换函数名。迁移后每个调用点需同时满足三个条件，库域归属正确、参数与返回值通道一致、控制流与错误处理语义不漂移。以本章工具链的口径看，常见调用最终归入 flexos\\_gate(lib, ret, func, ...) 或 flexos\\_gate\\_r(lib, retptr, func, ...) 两类形式。两类形式虽统一了接口外观，原代码中许多被默认假设的细节也被暴露，返回值类型是否匹配、失败路径是否仍被正确传播、宏或条件表达式中的调用是否保持原有求值顺序均是示例。

难点在于多个约束叠加，同名函数可能出现在不同库中，库域解析错误会将调用映射到错误隔离边界；调用形态并不总是独立语句，大量调用嵌在 if、return、类型转换与宏展开中，简单模式匹配极易漏改或误改；很多遗留代码依赖隐式错误处理约定，仅修改表层调用而未补齐返回值接收与检查会引入新的语义缺陷；编译通过无法证明迁移正确，覆盖统计与可定位报告必须配套，风险被收敛到可人工复核的候选点集合。

从形式化角度，设原始文件为 \\(S\\)，候选外部调用点集合为\\(\\mathcal{C}(S)=\\{c_1,\\dots,c_m\\}\\)，迁移器目标可写为重写算子 \\(T\\)：
\\begin{equation}
  T(S) = S'
\\end{equation}"""

# ============================================================
# FRAGMENT 11
# 原片段 has 5 paragraphs:
# 1. "\texttt{InferLibFromPath}的做法..." (purple, with \texttt, $ math)
# 2. "映射确定后，AutoFlex进入Coccinelle批量替换阶段..." (purple)
# 3. "Coccinelle把C源码先解析为可匹配的语法结构..." (purple)
# 4. "工程实践中，Coccinelle在本文场景中有效的主要原因是..." (purple)
# 5. "替换目标为统一的门调用形式。例如，以func属于库libX为例..." + equation (purple + LaTeX)
# ============================================================
frag11_modified = """\\texttt{InferLibFromPath} 的做法是从符号定义路径提取 \\texttt{lib/\\{name\\}/} 或 \\texttt{libs/\\{name\\}/} 并统一归一化为门的库名。某函数定义不唯一（即 $|D_f| > 1$）时，系统采取保守策略，优先使用显式回退映射或交由人工补充，从而避免把调用映射到错误的库域。流水线还实现了关键字过滤、接口别名归一化以及返回值类型辅助推断等优化，尽量减少误报、假阴性以及类型不匹配带来的二次人工修补。

映射确定后，AutoFlex 进入 Coccinelle 批量替换阶段。Coccinelle 基于 SmPL（Semantic Patch Language）做结构化匹配\\cite{10,26}，作用域及语法位置能比纯文本替换被更严格地控制，大规模代码上的可控覆盖由此实现。该阶段优先处理最常见的独立语句调用形态，其一是赋值调用，其二是纯调用，高占比、低风险的改写点先被稳定处理，后续高难场景的处理面便更小、更可控。

Coccinelle 把 C 源码先解析为可匹配的语法结构，SmPL 中的元变量（如表达式列表 \\textit{EL}）被用于建立约束，所有满足约束的位置随后被生成变换，而非做字符串替换。调用表达式、赋值语句以及参数列表等语法层对象被直接精确匹配，注释、字符串字面量、同名标识符等易引发误替换的场景因此被天然避开。SmPL 规则文本可读，每次规则修改都能通过差异审查解释改动原因、位置以及作用域。

工程实践中，Coccinelle 在本文场景中有效的主要原因是其解决了高频、同构、跨文件的第一波改写任务。遗留代码中大量调用具有稳定句型，手工改写全部调用成本高且容易出现一致性错误；这类高重复度改写被 Coccinelle 收敛为少量可复用规则，规则执行结果直接形成差异输出，与后续覆盖检查及人工复核形成闭环，不会有自动改完但不可解释的黑盒风险。

替换目标为统一的 门调用形式。例如，以 func 属于库 libX 为例，迁移后得到：
\\begin{equation}
  \\begin{aligned}
    \\text{原始：}\\quad & \\texttt{ret = func(a, b);}                    \\\\
    \\text{改写：}\\quad & \\texttt{flexos\\_gate(libX, ret, func, a, b);}
  \\end{aligned}
\\end{equation}"""

# ============================================================
# FRAGMENT 14
# 原片段 has 4 paragraphs:
# 1. "自动迁移完成后，运行时是否存在绕过门的跨域调用..." (purple)
# 2. "GCC选项\texttt{-finstrument-functions}开启后..." (purple, with \texttt)
# 3. "隔离语义上，该机制把漏门转化为域内访问异常..." (purple)
# 4. "可将编译器插入逻辑抽象为以下形式：" + equation (purple + LaTeX)
# ============================================================
frag14_modified = """自动迁移完成后，运行时是否存在绕过门的跨域调用才是核心问题，而非代码里的门是否都被替换。门完整性检测以 GCC 函数插桩及运行时校验为主线，目标库启用函数级插桩后，每次函数进入与退出都让库内钩子写入局部守卫变量；某条跨域路径缺少门时，MPK 等域内隔离后端下运行时更容易暴露为异常行为或崩溃，潜在漏改由此从静态可疑点转为可观测的故障信号。

GCC 选项 \\texttt{-finstrument-functions} 开启后，编译器在每个函数入口自动插入对 \\texttt{\\_\\_cyg\\_profile\\_func\\_enter} 的调用，每个函数返回路径自动插入对 \\texttt{\\_\\_cyg\\_profile\\_func\\_exit} 的调用，业务代码无需显式调用这两个函数，运行时所有被插桩函数仍会触发它们。库内易变守卫写操作与钩子配合，每次执行都对应一次真实内存访问，优化器很难将其消除。需要注意的是，钩子自身被插桩会导致递归，工程实践中 \\texttt{no\\_instrument\\_function} 属性应同时使用，或在排除列表中明确排除这两个钩子函数。

隔离语义上，该机制把漏门转化为域内访问异常的可观测事件：调用通过正确门进入目标库时，域切换或权限切换已发生，钩子对库内守卫的读写可达；调用绕过门直接进入目标库函数时，MPK 等机制下通常缺少对应权限上下文，钩子的守卫写入更容易触发保护异常。插桩本身不直接证明正确，但原本可能静默存在的缺门错误由此转化为失效即停信号，暴露概率与定位效率显著提升。

可将编译器插入逻辑抽象为以下形式：
\\begin{equation}
  \\begin{aligned}
    \\texttt{f(\\ldots)\\ \\{\\ } & \\texttt{\\_\\_cyg\\_profile\\_func\\_enter(this\\_fn, call\\_site);}\\\\\\
                                 & \\texttt{/* original body */}\\\\\\
                                 & \\texttt{\\_\\_cyg\\_profile\\_func\\_exit(this\\_fn, call\\_site);\\ \\}}
  \\end{aligned}
\\end{equation}"""

# ============================================================
# FRAGMENT 18
# 原片段 has 3 paragraphs:
# 1. "从最终结果可得到各方法的平均查询比例与首次命中比例...最终结果如表\ref{...}" (purple)
# 2. "\begin{table}...\end{table}" (LaTeX float, preserved as-is)
# 3. "（1）查询次数方面...（2）所选5个阈值覆盖了从低到高的完整范围..." (purple)
# ============================================================
frag18_modified = """从最终结果可得到各方法的平均查询比例与首次命中比例。表中数据为每个数据集在 5 个经筛选的阈值上跨 5 个随机种子的均值，筛选依据为 复合策略相对 均衡策略的查询量增益最大的 5 个阈值。最终结果如表\\ref{tab:search-agg-results}，各方法对比如下：
\\begin{table}[h]
  \\centering
  \\small
  \\setlength{\\tabcolsep}{3pt}
  \\begin{tabular}{llcccc}
    \\toprule
    数据集       & 方法         & 总查询次数        & 总查询比例        & 首中查询次数    & 首中查询比例    \\\\
    \\midrule
    nginx:REQ & 均衡   & 26.40±10.71 & 0.275±0.112 & 22.00±14.51 & 0.229±0.151 \\\\
    nginx:REQ & Centroid   & 25.60±1.50  & 0.267±0.016 & \\underline{12.20±6.36}  & \\underline{0.127±0.066} \\\\
    nginx:REQ & 复合（本文）  & \\textbf{17.40±5.57}  & \\textbf{0.181±0.058} & 13.00±7.35  & 0.135±0.077 \\\\
    nginx:REQ & 混合   & 24.60±9.79  & 0.256±0.102 & 22.60±15.33 & 0.235±0.160 \\\\
    nginx:REQ & 信息熵   & 24.40±9.42  & 0.254±0.098 & 22.60±15.33 & 0.235±0.160 \\\\
    nginx:REQ & 随机   & \\underline{22.60±5.03}  & \\underline{0.235±0.052} & \\textbf{10.48±5.14}   & \\textbf{0.109±0.053} \\\\
    nginx:REQ & 穷举 & 96.00±0.00  & 1.000±0.000 & 43.84±24.03 & 0.457±0.250 \\\\
    \\midrule
    redis:GET & 均衡   & 31.20±11.18 & 0.325±0.116 & 20.00±12.83 & 0.208±0.134 \\\\
    redis:GET & Centroid   & 28.40±2.58  & 0.296±0.027 & 17.40±9.09  & 0.181±0.095 \\\\
    redis:GET & 复合（本文）  & \\textbf{22.40±4.88}  & \\textbf{0.233±0.051} & \\textbf{11.60±6.24}  & \\textbf{0.121±0.065} \\\\
    redis:GET & 混合   & 29.20±9.87  & 0.304±0.103 & 18.20±12.16 & 0.190±0.127 \\\\
    redis:GET & 信息熵   & 29.00±9.47  & 0.302±0.099 & 17.40±11.37 & 0.181±0.118 \\\\
    redis:GET & 随机   & \\underline{28.36±5.68}  & \\underline{0.295±0.059} & \\underline{12.80±6.44}  & \\underline{0.133±0.067} \\\\
    redis:GET & 穷举 & 96.00±0.00  & 1.000±0.000 & 30.08±12.59 & 0.313±0.131 \\\\
    \\midrule
    redis:SET & 均衡   & 34.60±8.38  & 0.360±0.087 & 19.40±7.97  & 0.202±0.083 \\\\
    redis:SET & Centroid   & 29.60±1.02  & 0.308±0.011 & 15.40±7.52  & 0.160±0.078 \\\\
    redis:SET & 复合（本文）  & \\textbf{21.00±5.40}  & \\textbf{0.219±0.056} & \\textbf{7.80±6.16}   & \\textbf{0.081±0.064} \\\\
    redis:SET & 混合   & 35.20±9.31  & 0.367±0.097 & 21.00±9.13  & 0.219±0.095 \\\\
    redis:SET & 信息熵   & 34.20±9.00  & 0.356±0.094 & 20.20±9.24  & 0.210±0.096 \\\\
    redis:SET & 随机   & \\underline{27.88±4.94}  & \\underline{0.290±0.052} & \\underline{9.00±4.97}   & \\underline{0.094±0.052} \\\\
    redis:SET & 穷举 & 96.00±0.00  & 1.000±0.000 & 20.16±7.12  & 0.210±0.074 \\\\
    \\bottomrule
  \\end{tabular}
  \\caption{七种搜索方法在三个数据集上的聚合结果；加粗为最优值，下划线为次优值}
  \\label{tab:search-agg-results}
\\end{table}

（1）查询次数方面，复合策略在 nginx:REQ 上仅需 17.40 次，均衡策略为 26.40 次，降幅 34\\%；在 redis:GET 上需 22.40 次，均衡策略为 31.20 次，降幅 28\\%；在 redis:SET 上需 21.00 次，均衡策略为 34.60 次，降幅 39\\%。复合策略在 redis:SET 上首次命中步数降至 7.80 次，比均衡策略的 19.40 次减少约 60\\%、比 Centroid 策略的 15.40 次减少约 49\\%，交互式使用中用户平均只需等待约 8 次配置构建与测试即可获得第一个满足性能要求的可行配置。

（2）所选 5 个阈值覆盖了从低到高的完整范围，nginx:REQ 覆盖 30000--46000、redis:GET 覆盖 160000--360000、redis:SET 覆盖 120000--220000。低阈值端复合策略继承均衡策略的激进剪枝快速收敛；高阈值端复合策略复用 Centroid 策略的极小极大准则避免 \\(p\\to 0\\) 时的估计滞后。复合策略在不同阈值分布下均保持了对单一策略的显著优势。"""

# ============================================================
# Map fragment ID to corrected text
# ============================================================
fixes = {
    8: frag8_modified,
    9: frag9_modified,
    11: frag11_modified,
    14: frag14_modified,
    18: frag18_modified,
}

# Apply fixes and validate
for i, row in enumerate(rows[1:], start=1):
    mid = int(row[0])
    if mid not in fixes:
        continue
    orig = row[col_orig]
    new_mod = fixes[mid]

    if not validate(mid, orig, new_mod):
        print(f"  Fragment {mid}: PARAGRAPH MISMATCH - please review!")
        o_paras = split_paras(orig)
        m_paras = split_paras(new_mod)
        print(f"    原 has {len(o_paras)} paras, 修改后 has {len(m_paras)} paras")

    row[col_mod] = new_mod
    print(f"  Fragment {mid}: corrected ({len(row[col_mod])} chars, {count_paras(new_mod)} paras)")

if errors:
    print("\n*** ERRORS ***")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

# Write corrected CSV
with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(rows)
print(f"\nWrote corrected CSV: {CSV}")
print("All fragments validated.")
