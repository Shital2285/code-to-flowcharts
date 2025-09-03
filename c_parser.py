# backend/c_parser.py
import re
import html

# ---------------- utilities ----------------
def _clean_label(s: str) -> str:
    """Make a safe, compact label for Mermaid nodes (remove internal quotes)."""
    if s is None:
        return ""
    s = str(s)
    s = s.replace('"', '').replace("'", "")
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    # escape < & > to be safe in HTML contexts
    s = html.escape(s, quote=False)
    return s

def _remove_comments_and_preproc(code: str) -> str:
    code = re.sub(r'//.*', '', code)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    # remove preprocessor lines (keep non-empty code lines)
    code = "\n".join(ln for ln in code.splitlines() if not ln.strip().startswith('#'))
    return code

# read until semicolon not inside parentheses
def _read_stmt(s: str, i: int):
    n = len(s)
    depth = 0
    j = i
    while j < n:
        ch = s[j]
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth > 0:
                depth -= 1
        elif ch == ';' and depth == 0:
            return s[i:j+1].strip(), j+1
        j += 1
    return s[i:j].strip(), j

# read a parenthesized or braced block starting at i (s[i] == '(' or '{')
def _read_block(s: str, i: int):
    open_ch = s[i]
    close_ch = ')' if open_ch == '(' else '}'
    assert open_ch in '({'
    depth = 0
    j = i
    n = len(s)
    buf = []
    while j < n:
        ch = s[j]
        if ch == open_ch:
            depth += 1
            if depth == 1:
                j += 1
                continue
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return "".join(buf), j+1
        buf.append(ch)
        j += 1
    return "".join(buf), j

# parse a block of C code (string) into a simple node list
def _parse_block(s: str):
    s = s.strip()
    i = 0
    n = len(s)
    nodes = []
    while True:
        # skip whitespace/newlines
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break

        # if starts with a keyword
        if s.startswith("if", i) and (i+2==n or not s[i+2].isalnum() and s[i+2] != '_'):
            i += 2
            # skip spaces and read condition
            while i < n and s[i].isspace():
                i += 1
            cond = ""
            if i < n and s[i] == '(':
                cond, i = _read_block(s, i)  # returns inside, index after ')'
            cond = cond.strip()
            # skip spaces
            while i < n and s[i].isspace():
                i += 1
            # read then-block (braced or single stmt)
            then_nodes = []
            if i < n and s[i] == '{':
                inner, i = _read_block(s, i)
                then_nodes = _parse_block(inner)
            else:
                stmt, i = _read_stmt(s, i)
                then_nodes = _parse_block(stmt) if stmt.endswith('}') else [('stmt', stmt)]
            # check for else
            while i < n and s[i].isspace():
                i += 1
            else_nodes = None
            if s.startswith("else", i) and (i+4==n or not s[i+4].isalnum() and s[i+4] != '_'):
                i += 4
                while i < n and s[i].isspace():
                    i += 1
                if i < n and s[i] == '{':
                    inner, i = _read_block(s, i)
                    else_nodes = _parse_block(inner)
                else:
                    stmt, i = _read_stmt(s, i)
                    else_nodes = _parse_block(stmt) if stmt.endswith('}') else [('stmt', stmt)]
            nodes.append(('if', cond, then_nodes, else_nodes))
            continue

        if s.startswith("for", i) and (i+3==n or not s[i+3].isalnum() and s[i+3] != '_'):
            i += 3
            while i < n and s[i].isspace():
                i += 1
            header = ""
            if i < n and s[i] == '(':
                header, i = _read_block(s, i)
            while i < n and s[i].isspace():
                i += 1
            body_nodes = []
            if i < n and s[i] == '{':
                inner, i = _read_block(s, i)
                body_nodes = _parse_block(inner)
            else:
                stmt, i = _read_stmt(s, i)
                body_nodes = [('stmt', stmt)]
            nodes.append(('for', header, body_nodes))
            continue

        if s.startswith("while", i) and (i+5==n or not s[i+5].isalnum() and s[i+5] != '_'):
            i += 5
            while i < n and s[i].isspace():
                i += 1
            cond = ""
            if i < n and s[i] == '(':
                cond, i = _read_block(s, i)
            while i < n and s[i].isspace():
                i += 1
            body_nodes = []
            if i < n and s[i] == '{':
                inner, i = _read_block(s, i)
                body_nodes = _parse_block(inner)
            else:
                stmt, i = _read_stmt(s, i)
                body_nodes = [('stmt', stmt)]
            nodes.append(('while', cond, body_nodes))
            continue

        if s.startswith("do", i) and (i+2==n or not s[i+2].isalnum() and s[i+2] != '_'):
            i += 2
            while i < n and s[i].isspace():
                i += 1
            body_nodes = []
            if i < n and s[i] == '{':
                inner, i = _read_block(s, i)
                body_nodes = _parse_block(inner)
            else:
                stmt, i = _read_stmt(s, i)
                body_nodes = [('stmt', stmt)]
            # expect while(cond);
            while i < n and s[i].isspace():
                i += 1
            cond = ""
            if s.startswith("while", i):
                i += 5
                while i < n and s[i].isspace():
                    i += 1
                if i < n and s[i] == '(':
                    cond, i = _read_block(s, i)
                # skip semicolon if present
                if i < n and s[i] == ';':
                    i += 1
            nodes.append(('do', cond, body_nodes))
            continue

        # switch (simple)
        if s.startswith("switch", i) and (i+6==n or not s[i+6].isalnum() and s[i+6] != '_'):
            i += 6
            while i < n and s[i].isspace():
                i += 1
            expr = ""
            if i < n and s[i] == '(':
                expr, i = _read_block(s, i)
            while i < n and s[i].isspace():
                i += 1
            cases = []
            if i < n and s[i] == '{':
                body, i = _read_block(s, i)
                # naive split into case/default blocks
                parts = re.split(r'(?=(?:\bcase\b|\bdefault\b))', body)
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    m = re.match(r'^(case\s+[^:]+|default)\s*:\s*(.*)$', part, flags=re.S)
                    if not m:
                        continue
                    label = m.group(1).strip()
                    cbody = m.group(2).strip()
                    # remove trailing break; and take content up to that (simple)
                    cbody = re.split(r'\bbreak\s*;', cbody, maxsplit=1, flags=re.S)[0]
                    cases.append((label, _parse_block(cbody)))
            nodes.append(('switch', expr, cases))
            continue

        # default: read a statement until semicolon
        stmt, j = _read_stmt(s, i)
        if stmt:
            nodes.append(('stmt', stmt.strip()))
        i = j
    return nodes

# utility: extract variable names from declaration
def _extract_var_names(decl: str):
    decl = decl.strip().rstrip(';')
    m = re.match(r'^(?:unsigned\s+|signed\s+)?\s*(?:short|long|int|char|float|double|size_t)\b(.*)$', decl)
    if not m:
        return []
    rest = m.group(1).strip()
    parts = [p.strip() for p in rest.split(',') if p.strip()]
    names = []
    for p in parts:
        p = p.split('=')[0].strip()
        p = p.replace('*', ' ').strip()
        p = re.sub(r'\[.*\]', '', p).strip()
        if p:
            name = p.split()[-1]
            names.append(name)
    return names

# map raw stmt to a readable label and a kind
def _label_and_kind(node):
    typ = node[0]
    if typ == 'stmt':
        s = node[1].strip()
        if s.startswith('printf'):
            m = re.search(r'printf\s*\(\s*"([^"]*)"', s)
            if m:
                return f'Display {m.group(1)}', 'io'
            return 'Output', 'io'
        if s.startswith('scanf'):
            m = re.search(r'scanf\s*\([^,]+,\s*(.+)\)', s)
            if m:
                var = m.group(1).strip().replace('&','').strip()
                return f'Input {var}', 'io'
            return 'Input', 'io'
        if re.match(r'^(?:unsigned\s+|signed\s+)?\s*(?:short|long|int|char|float|double|size_t)\b', s):
            names = _extract_var_names(s)
            if not names:
                return 'Declare variable', 'proc'
            if len(names) == 1:
                return f'Declare variable {names[0]}', 'proc'
            return f'Declare variables {", ".join(names)}', 'proc'
        if s.startswith('return'):
            return 'Return', 'proc'
        # fallback show assignment / expression but compact
        # e.g., x = x + 1;
        s_clean = s.rstrip(';').strip()
        return s_clean, 'proc'
    # control nodes
    if typ == 'if':
        cond = node[1].strip() if node[1] else 'Condition'
        return cond, 'decision'
    if typ == 'while':
        cond = node[1].strip() if node[1] else 'Condition'
        return cond, 'decision'
    if typ == 'for':
        hdr = node[1].strip() if node[1] else 'For'
        return hdr, 'decision'
    if typ == 'do':
        cond = node[1].strip() if node[1] else 'Condition'
        return cond, 'decision'
    if typ == 'switch':
        expr = node[1].strip() if node[1] else 'Switch'
        return expr, 'decision'
    return str(node), 'proc'

# ---------------- rendering ----------------
def code_to_flowchart(code: str) -> str:
    """
    Convert C code (string) to a Mermaid flowchart (Mermaid graph string).
    Designed to avoid duplicate declaration nodes and avoid No-action nodes.
    """
    code = _remove_comments_and_preproc(code)
    # extract main body if present
    m = re.search(r'\bint\s+main\s*\([^)]*\)\s*\{', code)
    if m:
        start = m.end() - 1
        body, _ = _read_block(code, start)
        content = body
    else:
        content = code

    # parse into nodes
    ast = _parse_block(content)

    # produce mermaid
    lines = ["graph TD"]
    node_counter = 0
    def new_id():
        nonlocal node_counter
        node_counter += 1
        return f"N{node_counter}"

    def add_node(label, kind='proc'):
        nid = new_id()
        safe = _clean_label(label)
        if kind == 'io':
            lines.append(f'{nid}[/"{safe}"/]')
        elif kind == 'decision':
            lines.append(f'{nid}{{"{safe}"}}')
        elif kind == 'proc':
            lines.append(f'{nid}["{safe}"]')
        else:
            lines.append(f'{nid}["{safe}"]')
        return nid

    def connect(a, b, edge_label=None):
        if edge_label:
            lines.append(f"{a} -- {edge_label} --> {b}")
        else:
            lines.append(f"{a} --> {b}")

    # Start node
    lines.append("Start((Start))")
    prev = "Start"
    last_label_added = None  # used to avoid duplicate consecutive labels

    i = 0
    while i < len(ast):
        node = ast[i]
        kind_label, kind_type = _label_and_kind(node)

        # handle if separately because it can consume else and require merging or direct End
        if node[0] == 'if':
            # render decision
            cond_label = kind_label
            d_id = add_node(cond_label, 'decision')
            connect(prev, d_id)

            then_nodes = node[2] or []
            else_nodes = node[3] or []

            # render then branch: connect d -- Yes --> first_then_node
            then_last = None
            if then_nodes:
                # render sequence from decision (edge labeled Yes)
                then_first = then_nodes[0]
                tl_label, tl_type = _label_and_kind(then_first)
                t_first_id = add_node(tl_label, 'io' if tl_type == 'io' else 'proc')
                connect(d_id, t_first_id, "Yes")
                # render remaining then nodes
                cur = t_first_id
                for tnode in then_nodes[1:]:
                    l, t = _label_and_kind(tnode)
                    nid = add_node(l, 'io' if t == 'io' else 'proc')
                    connect(cur, nid)
                    cur = nid
                then_last = cur
            else:
                then_last = None

            # render else branch
            else_last = None
            if else_nodes:
                e_first = else_nodes[0]
                el_label, el_type = _label_and_kind(e_first)
                e_first_id = add_node(el_label, 'io' if el_type == 'io' else 'proc')
                connect(d_id, e_first_id, "No")
                cur = e_first_id
                for enode in else_nodes[1:]:
                    l, t = _label_and_kind(enode)
                    nid = add_node(l, 'io' if t == 'io' else 'proc')
                    connect(cur, nid)
                    cur = nid
                else_last = cur
            else:
                else_last = None

            # determine if this if is the last top-level node (i == len(ast)-1)
            is_last_top = (i == len(ast) - 1)

            if is_last_top:
                # connect existing branch ends to End, missing branch path connects decision directly to End
                if then_last:
                    connect(then_last, "End")
                else:
                    connect(d_id, "End", "Yes")
                if else_last:
                    connect(else_last, "End")
                else:
                    connect(d_id, "End", "No")
                # terminate here
                lines.append("End((End))")
                return "\n".join(lines)
            else:
                # there are further statements after this if -> create a merge node
                merge_id = add_node("Merge", 'proc')
                # if then branch exists connect its end -> merge else connect decision -> merge with Yes label
                if then_last:
                    connect(then_last, merge_id)
                else:
                    connect(d_id, merge_id, "Yes")
                if else_last:
                    connect(else_last, merge_id)
                else:
                    connect(d_id, merge_id, "No")
                # continue from merge
                prev = merge_id
                i += 1
                continue

        # non-if nodes
        label = kind_label
        # skip None labels (like includes or main)
        if not label:
            i += 1
            continue

        # avoid duplicate consecutive declaration nodes with same label
        if label == last_label_added:
            i += 1
            continue

        nid = add_node(label, 'io' if kind_type == 'io' else 'proc')
        connect(prev, nid)
        prev = nid
        last_label_added = label

        # if statement is a return, connect to End and finish
        if label == 'Return':
            connect(nid, "End")
            lines.append("End((End))")
            return "\n".join(lines)

        i += 1

    # finished all nodes, connect to End
    connect(prev, "End")
    lines.append("End((End))")
    return "\n".join(lines)
# ---------------- Explanation Generator ----------------
def code_to_explanation(code: str) -> str:
    """Generate a step-by-step explanation of the C program."""
    code = _remove_comments_and_preproc(code)
    m = re.search(r'\bint\s+main\s*\([^)]*\)\s*\{', code)
    if m:
        body, _ = _read_block(code, m.end()-1)
        content = body
    else:
        content = code
    ast = _parse_block(content)

    explanation = ["Program Explanation:"]

    def walk(block, depth=0):
        indent = "  " * depth
        for node in block:
            if node[0] == "stmt":
                text, _ = _label_and_kind(node)
                explanation.append(f"{indent}- {text}.")
            elif node[0] == "if":
                explanation.append(f"{indent}- If condition **({node[1].strip()})** is true:")
                walk(node[2], depth+1)
                if node[3]:
                    explanation.append(f"{indent}- Otherwise:")
                    walk(node[3], depth+1)
            elif node[0] == "while":
                explanation.append(f"{indent}- While **({node[1].strip()})**, repeat:")
                walk(node[2], depth+1)
            elif node[0] == "do":
                explanation.append(f"{indent}- Do the following at least once:")
                walk(node[2], depth+1)
                explanation.append(f"{indent}- Then repeat while **({node[1].strip()})**.")
            elif node[0] == "for":
                explanation.append(f"{indent}- For loop **({node[1].strip()})**, repeat:")
                walk(node[2], depth+1)
            elif node[0] == "switch":
                explanation.append(f"{indent}- Switch on **({node[1].strip()})**:")
                for label, case_nodes in node[2]:
                    explanation.append(f"{indent}  - Case **{label}**:")
                    walk(case_nodes, depth+2)

    walk(ast)
    return "\n".join(explanation)
