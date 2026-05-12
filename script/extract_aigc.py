#!/usr/bin/env python3
"""Stage 1: Extract suspected AIGC paragraphs, insert markers in main.tex.

Usage: python3 extract_aigc.py [--jobid JOBID]

Reads:
  jobs/{jobid}/report/*.html   — AIGC detection report
  jobs/{jobid}/main.tex        — LaTeX source

Does:
  1. Parse HTML to find purple-marked AIGC fragments
  2. Match fragments to main.tex via text search
  3. Insert % AIGC_BEGIN_{N} / % AIGC_END_{N} markers around each paragraph
  4. Back up main.tex before modifying

Outputs (in jobs/{jobid}/result/stage1/):
  疑似AIGC片段.csv       — marker IDs + fragment text + paragraph plain text
  input_fragments.txt    — AIGC片段 (purple only), one per line, double blank line
  input_paragraphs.txt   — AIGC段落 (full paragraph), one per line, double blank line
"""

import re, csv, os, argparse, shutil, glob

parser = argparse.ArgumentParser()
parser.add_argument("--jobid", default="default")
args = parser.parse_args()

JOBID = args.jobid
from _root import ROOT as BASE
JOB   = os.path.join(BASE, "jobs", JOBID)

# Find HTML report
html_files = glob.glob(os.path.join(JOB, "report", "*.html"))
if not html_files:
    print(f"ERROR: No HTML report found in {JOB}/report/")
    exit(1)
HTML = html_files[0]
TEX  = os.path.join(JOB, "main.tex")
OUT  = os.path.join(JOB, "result", "stage1")

if not os.path.exists(TEX):
    print(f"ERROR: main.tex not found at {TEX}")
    exit(1)

os.makedirs(OUT, exist_ok=True)
CSV   = os.path.join(OUT, "疑似AIGC片段.csv")
INP_F = os.path.join(OUT, "input_fragments.txt")
INP_P = os.path.join(OUT, "input_paragraphs.txt")

# ─── Backup main.tex to result/stage1/ ───
BAK = os.path.join(OUT, "main.tex.bak")
if not os.path.exists(BAK):
    shutil.copy2(TEX, BAK)
    print(f"[0] Backed up main.tex → {BAK}")

# ═══ Step 1: extract purple fragments from HTML ═══
with open(HTML, encoding="utf-8") as f:
    html = f.read()

cl3 = []
for m in re.finditer(
    r"<a class=\"cl3\"><span class='a_span' id=\"a_detail_(\d+)\"></span>(.*?)</a>", html
):
    cl3.append(dict(id=int(m.group(1)), text=m.group(2), start=m.start(), end=m.end()))

groups, cur = [], [cl3[0]]
for i in range(len(cl3) - 1):
    gap = re.sub(r"<[^>]+>", "", html[cl3[i]["end"] : cl3[i+1]["start"]]).strip()
    if gap == "":
        cur.append(cl3[i+1])
    else:
        groups.append(cur); cur = [cl3[i+1]]
groups.append(cur)

aigc_fragments = []
for g in groups:
    t = "".join(f["text"] for f in g)
    t = t.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").replace("&quot;", '"')
    aigc_fragments.append(t)

print(f"[1] {len(aigc_fragments)} purple groups from HTML")

# ═══ Step 2: read main.tex ═══
with open(TEX, encoding="utf-8") as f:
    tex = f.read()
tex_lines = tex.split("\n")

line_offsets = [0]
for l in tex_lines:
    line_offsets.append(line_offsets[-1] + len(l) + 1)

def is_blank(idx):
    if idx < 0 or idx >= len(tex_lines): return True
    return tex_lines[idx].strip() == ""

# ═══ Step 3: LaTeX label → number mapping ═══
def build_ref_map(tex):
    """Simulate LaTeX counters to map each \\label{key} to its displayed number.

    Returns dict: label_key → display_string (e.g. "图3.2", "表4.1", "2.3").
    """
    sec_num = 0           # current section number (unnumbered sections skipped)
    fig_counter = 0       # per-section figure counter
    tab_counter = 0       # per-section table counter

    ref_map = {}

    # Determine label type from key prefix.
    # Note: LaTeX \ref{fig:xxx} produces just the number (e.g. "1.2"),
    # the "图"/"表" prefix is already typed in the source text.
    def label_type(key):
        for pfx in ['fig:', 'tab:', 'eq:', 'alg:']:
            if key.startswith(pfx):
                return key[len(pfx):]
        return key

    # Scan tex line by line, tracking counters
    lines = tex.split('\n')
    in_figure = False
    in_table = False
    pending_labels = []  # labels collected inside current float

    for line in lines:
        stripped = line.strip()

        # Track section counters (skip starred/unnumbered)
        if re.match(r'\\section\*?\{', stripped):
            if not stripped.startswith(r'\section*'):
                sec_num += 1
                fig_counter = 0
                tab_counter = 0

        # Track float environments
        if re.match(r'\\begin\{figure\}', stripped) or re.match(r'\\begin\{figure\*\}', stripped):
            in_figure = True
            pending_labels = []
        if re.match(r'\\begin\{table\}', stripped) or re.match(r'\\begin\{table\*\}', stripped) or re.match(r'\\begin\{longtable\}', stripped):
            in_table = True
            pending_labels = []
        if re.match(r'\\end\{figure\}', stripped) or re.match(r'\\end\{figure\*\}', stripped):
            if in_figure:
                fig_counter += 1
                for lbl in pending_labels:
                    ref_map[lbl] = f"{sec_num}.{fig_counter}"
                pending_labels = []
                in_figure = False
        if re.match(r'\\end\{table\}', stripped) or re.match(r'\\end\{table\*\}', stripped) or re.match(r'\\end\{longtable\}', stripped):
            if in_table:
                tab_counter += 1
                for lbl in pending_labels:
                    ref_map[lbl] = f"{sec_num}.{tab_counter}"
                pending_labels = []
                in_table = False

        # Collect labels outside floats
        for m in re.finditer(r'\\label\{([^}]*)\}', stripped):
            key = m.group(1)
            if in_figure or in_table:
                pending_labels.append(key)
            else:
                # Generic label (section, etc.) — just use section number
                ref_map[key] = f"{sec_num}"

    return ref_map


# ═══ Step 4: clean_to_plain ═══
def clean_to_plain(text, ref_map=None):
    def _label(block):
        m = re.search(r'\\label\{([^}]*)\}', block)
        if m:
            key = m.group(1)
            for pfx in ['tab:', 'fig:', 'eq:', 'alg:']:
                if key.startswith(pfx): return key[len(pfx):]
            return key
        return ""
    def _cap(block):
        m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', block, re.DOTALL)
        return m.group(1).strip() if m else ""
    def _float_repl(m, typ):
        lbl = _label(m.group(0)); cap = _cap(m.group(0))
        if lbl: return f"<{typ}: {lbl}>"
        if cap: return f"<{typ}: {cap}>"
        return f"<{typ}>"

    text = re.sub(r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}', lambda m: _float_repl(m, "图"), text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{table\*?\}.*?\\end\{table\*?\}', lambda m: _float_repl(m, "表"), text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{longtable\}.*?\\end\{longtable\}', lambda m: _float_repl(m, "表"), text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{algorithm\}.*?\\end\{algorithm\}', lambda m: _float_repl(m, "算法"), text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{equation\*?\}.*?\\end\{equation\*?\}', '<公式>', text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}.*?\\end\{align\*?\}', '<公式>', text, flags=re.DOTALL)

    def _list(m):
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', m.group(0), re.DOTALL)
        return "; ".join(clean_to_plain(it.strip(), ref_map) for it in items if it.strip())
    text = re.sub(r'\\begin\{enumerate\}.*?\\end\{enumerate\}', _list, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{itemize\}.*?\\end\{itemize\}', _list, text, flags=re.DOTALL)

    def _resolve_ref(m):
        full_key = m.group(0)[5:-1]  # extract entire key from \ref{...}
        ref_type, ref_key = (m.group(1), m.group(2)) if len(m.groups()) >= 2 else (None, full_key)

        if ref_map and full_key in ref_map:
            return ref_map[full_key]

        # Fallback: use label prefix to guess type
        typ_map = {'fig': '图', 'tab': '表', 'eq': '公式', 'alg': '算法'}
        if ref_type and ref_type in typ_map:
            return f"{typ_map[ref_type]} {ref_key}"
        return ref_key if ref_key else full_key

    text = re.sub(r'\\ref\{([a-z]+):([^}]*)\}', _resolve_ref, text)
    text = re.sub(r'\\ref\{([^}]*)\}', _resolve_ref, text)
    text = re.sub(r'\\cite\{([^}]*)\}', r'[\1]', text)
    text = re.sub(r'\\label\{[^}]*\}', '', text)
    text = re.sub(r'\\includegraphics\*?(\[[^\]]*\])?\{[^}]*\}', '', text)
    text = re.sub(r'\\includesvg\*?(\[[^\]]*\])?\{[^}]*\}', '', text)

    for env in ["center", "minipage", "tabular", "flushleft", "flushright",
                "quote", "quotation", "verbatim", "description"]:
        text = re.sub(r'\\begin\{' + env + r'\*?\}(\[[^\]]*\])?(\{[^}]*\})?', '', text)
        text = re.sub(r'\\end\{' + env + r'\*?\}', '', text)

    text = re.sub(r'\\IfFileExists\{[^}]*\}\{[^}]*\}\{[^}]*\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\\IfFileExists\{[^}]*\}\{', '', text)

    for cmd in ["texttt", "textbf", "textit", "emph", "underline", "textsc",
                "heiti", "songti", "zihao", "timesnewroman",
                "scriptsize", "footnotesize", "small", "normalsize", "large", "Large",
                "LARGE", "huge", "Huge", "bfseries", "centering", "rmfamily", "sffamily",
                "ttfamily", "mdseries", "upshape", "itshape", "slshape", "scshape",
                "raggedright", "raggedleft", "textnormal", "textup", "textsuperscript",
                "textsubscript", "mathrm", "mathit", "mathbf", "mathsf", "mathbb",
                "mathcal", "mathfrak", "mathscr"]:
        text = re.sub(r'\\' + cmd + r'\{((?:[^{}]|\{[^{}]*\})*)\}', r'\1', text)

    text = re.sub(r'\\\(([^)]*)\\\)', r'\1', text)
    text = re.sub(r'\$([^$]*)\$', r'\1', text)
    text = re.sub(r'\\[a-zA-Z@]+\*?(\[[^\]]*\])?(\{[^}]*\})?(\{[^}]*\})?', '', text)
    text = re.sub(r'\\[a-zA-Z@]+\*?', '', text)
    text = re.sub(r'\{((?:[^{}]|\{[^{}]*\})*)\}', r'\1', text)

    text = text.replace("~", " ").replace("``", '"').replace("''", '"')
    text = text.replace("--", "—").replace("---", "—")
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\#", "#").replace("\\_", "_")
    text = text.replace("$", "").replace("\\", "")

    for cmd in ['section', 'subsection', 'subsubsection', 'par', 'noindent', 'item']:
        text = re.sub(r'\\' + cmd + r'\*?\s*', '', text)
    text = re.sub(r'\\qquad\s*', '  ', text); text = re.sub(r'\\quad\s*', ' ', text)
    text = re.sub(r'\\hfill\s*', '', text); text = re.sub(r'\\[hv]space\*?\{[^}]*\}', '', text)

    text = re.sub(r'\n+', '\n', text); text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return text.strip()

# ═══ Step 4: position matching (auto-match, fall back to manual) ═══
# Build stripped tex for matching
def strip_for_match(s):
    s = re.sub(r'(?<!\\)%.*$', '', s, flags=re.MULTILINE)
    for cmd in ["texttt", "textbf", "textit", "emph", "underline", "textsc", "heiti", "songti", "zihao"]:
        s = re.sub(r'\\' + cmd + r'\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\cite\{[^}]*\}', '', s)
    s = re.sub(r'\\ref\{[^}]*\}', '', s)
    s = re.sub(r'\\label\{[^}]*\}', '', s)
    for env in ["figure", "table", "longtable", "algorithm", "equation", "align",
                "enumerate", "itemize", "center", "minipage", "flushleft", "tabular"]:
        for star in ["", "*"]:
            s = re.sub(r'\\begin\{' + env + star + r'\}.*?\\end\{' + env + star + r'\}', '', s, flags=re.DOTALL)
    s = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})*', '', s)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    s = re.sub(r'\{([^}]*)\}', r'\1', s)
    s = s.replace("~", " ").replace("``", '"').replace("''", '"').replace("--", "-").replace("---", "—")
    return re.sub(r'\s+', '', s)

stripped_lines = [strip_for_match(l) for l in tex_lines]
full_stripped = "".join(stripped_lines)

def find_in_tex(text):
    ns = re.sub(r'\s+', '', text)
    idx = full_stripped.find(ns)
    if idx < 0:
        for pl in [40, 30, 20, 15, 10]:
            idx = full_stripped.find(ns[:pl])
            if idx >= 0: break
    return idx

def stripped_pos_to_line_col(pos):
    """Map full_stripped position → (line, visible_col) in tex."""
    accum = 0
    for ln, sl in enumerate(stripped_lines):
        if pos < accum + len(sl):
            return ln + 1, pos - accum + 1  # 1-based
        accum += len(sl)
    return 0, 0

def line_col_to_byte(line_num, vis_col):
    raw_line = tex_lines[line_num - 1]
    base = line_offsets[line_num - 1]
    ci = 0; ri = 0
    while ri < len(raw_line) and ci < vis_col - 1:
        ch = raw_line[ri]
        if ch == '\\':
            ri += 1
            while ri < len(raw_line) and raw_line[ri].isalpha(): ri += 1
            while ri < len(raw_line) and raw_line[ri] in ' \t': ri += 1
            while ri < len(raw_line) and raw_line[ri] in '{[':
                bc = '}' if raw_line[ri] == '{' else ']'
                depth = 1; ri += 1
                while ri < len(raw_line) and depth > 0:
                    if raw_line[ri] in '{[': depth += 1
                    elif raw_line[ri] == bc: depth -= 1
                    ri += 1
                while ri < len(raw_line) and raw_line[ri] in ' \t': ri += 1
            continue
        if ch in '{}~$ \t': ri += 1; continue
        ci += 1; ri += 1
    return base + ri

# ─── Find positions for each fragment ───
# Manual position overrides for fragments that fail auto-matching.
# Add (sl, sc, el, ec) tuples keyed by 1-based fragment index.
MANUAL_POSITIONS = {
    2:  (179, 1, 185, 456),   # English ABSTRACT
    18: (874, 1, 914, 90),
    19: (940, 1, 941, 115),
    20: (965, 42, 969, 90),
    # Add entries when auto-match fails:  fragment_index: (start_line, start_col, end_line, end_col)
    # Example from current document:
    # 18: (874, 1,   914, 90),
    # 19: (940, 1,   941, 115),
    # 20: (965, 42,  969, 90),
}

frag_positions = []
manual_fallbacks = 0

for i, pt in enumerate(aigc_fragments):
    n = i + 1
    if n in MANUAL_POSITIONS:
        sl, sc, el, ec = MANUAL_POSITIONS[n]
        bs = line_col_to_byte(sl, sc)
        be = line_col_to_byte(el, ec)
        frag_positions.append((bs, be, sl, el))
        print(f"  [{n:2d}] L{sl}:{sc} → L{el}:{ec}  bytes=[{bs}, {be})  (manual)")
        continue

    idx = find_in_tex(pt)
    if idx < 0:
        for trim in range(5, 30, 5):
            idx = find_in_tex(pt[trim:])
            if idx >= 0: break
    if idx < 0:
        print(f"  [MISS] fragment {n} — manual intervention needed")
        manual_fallbacks += 1
        frag_positions.append(None)
        continue

    end_idx = idx + len(re.sub(r'\s+', '', pt)) - 1
    sl, sc = stripped_pos_to_line_col(idx)
    el, ec = stripped_pos_to_line_col(end_idx)
    bs = line_col_to_byte(sl, sc)
    be = line_col_to_byte(el, ec)
    frag_positions.append((bs, be, sl, el))

    print(f"  [{n:2d}] L{sl}:{sc} → L{el}:{ec}  bytes=[{bs}, {be})")

if manual_fallbacks > 0:
    print(f"\n⚠ {manual_fallbacks} fragments need manual position lookup.")
    print("  Edit the script's MANUAL_POSITIONS dict with verified (sl, sc, el, ec) values.")

# ═══ Step 5: expand to paragraph boundaries, insert markers ═══
ref_map = build_ref_map(tex)  # simulate LaTeX counters for \ref → readable number
tex_bytes = list(tex)
results = []

# Process in reverse order (end of file first) to preserve positions
process_order = []
for i, pos in enumerate(frag_positions):
    if pos is None:
        process_order.append((i, None))
    else:
        process_order.append((i, pos))
process_order.sort(key=lambda x: x[1][0] if x[1] else 0, reverse=True)

for i, pos in process_order:
    n = i + 1
    pt = aigc_fragments[i]

    if pos is None:
        results.append((n, dict(id=n, fragment=pt, paragraph="")))
        continue

    bs, be, sl, el = pos

    # Expand to paragraph boundaries
    ps_line = sl - 1
    while ps_line > 0 and not is_blank(ps_line - 1): ps_line -= 1
    pe_line = el - 1
    while pe_line < len(tex_lines) - 1 and not is_blank(pe_line + 1): pe_line += 1

    ps = line_offsets[ps_line]
    pe = line_offsets[pe_line + 1] - 1

    # Extract full paragraph
    para_tex = ''.join(tex_bytes[ps:pe]).strip()
    paragraph_plain = clean_to_plain(para_tex, ref_map)

    # Insert markers
    begin = f"% AIGC_BEGIN_{n}"
    end   = f"% AIGC_END_{n}"
    replacement = f"{begin}\n{para_tex}\n{end}"

    del tex_bytes[ps:pe]
    for j, ch in enumerate(replacement):
        tex_bytes.insert(ps + j, ch)

    results.append((n, dict(id=n, fragment=pt, paragraph=paragraph_plain)))
    print(f"  [{n:2d}] marker inserted  para_lines={para_tex.count(chr(10))+1}  "
          f"fragment={len(pt)}B  paragraph={len(paragraph_plain)}B")

# Sort by ID
results.sort(key=lambda x: x[0])
results = [r[1] for r in results]

# Write modified tex
tex_new = ''.join(tex_bytes)
with open(TEX, "w", encoding="utf-8") as f:
    f.write(tex_new)

# Verify markers
markers_found = re.findall(r'% AIGC_(BEGIN|END)_(\d+)', tex_new)
ids_found = set(int(m[1]) for m in markers_found)
expected = set(range(1, len(results) + 1))
missing_ids = expected - ids_found
if missing_ids:
    print(f"\n⚠ Missing marker IDs: {missing_ids}")
else:
    print(f"\n[verify] All {len(expected)} marker IDs present, {len(markers_found)} markers total")

# ═══ Step 6: write CSV and input files ═══
with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["标记ID", "AIGC片段", "AIGC段落"])
    for r in results:
        w.writerow([r["id"], r["fragment"], r["paragraph"]])

for path, field in [(INP_F, "fragment"), (INP_P, "paragraph")]:
    with open(path, "w", encoding="utf-8") as f:
        for i, r in enumerate(results):
            line = r[field].replace("\n", " ").replace("\r", " ")
            line = re.sub(r"\s+", " ", line).strip()
            f.write(line)
            if i < len(results) - 1: f.write("\n\n\n")

print(f"CSV: {CSV} ({len(results)} rows)")
print(f"INP: {INP_F}")
print(f"INP: {INP_P}")
print("Done.")
