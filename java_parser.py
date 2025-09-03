# backend/java_parser.py
import re

# ---------------------------
# Utilities
# ---------------------------
def _remove_comments(code: str) -> str:
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    code = re.sub(r'//.*', '', code)
    return code

def _safe_label(s: str) -> str:
    s = s.strip()
    s = re.sub(r'System\.out\.println\s*\((.*)\)', r'print(\1)', s)
    if s.endswith(';'):
        s = s[:-1].rstrip()
    s = s.replace('"', "'")
    return s

def _preprocess_lines(code: str):
    code = _remove_comments(code)
    code = code.replace('{', '\n{\n').replace('}', '\n}\n')
    lines = [ln.strip() for ln in code.splitlines() if ln.strip() != '']
    return lines

# ---------------------------
# Parse block into AST
# ---------------------------
def _parse_block(lines, i=0):
    block = []
    n = len(lines)

    def _extract_paren(text):
        m = re.search(r'\((.*)\)', text)
        return m.group(1).strip() if m else ''

    while i < n:
        line = lines[i]

        if line == '}':
            return block, i + 1

        if re.search(r'\bclass\b', line) or re.search(r'\bmain\s*\(', line):
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            if j < n and lines[j] == '{':
                inner_block, j2 = _parse_block(lines, j + 1)
                block.extend(inner_block)
                i = j2
                continue
            else:
                i += 1
                continue

        # if / else if / else
        if line.startswith('if'):
            cond = _extract_paren(line)
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            then_block, j = ([], j) if j >= n or lines[j] != '{' else _parse_block(lines, j + 1)
            clauses = [(cond, then_block)]
            k = j
            else_block = None
            while k < n and lines[k].startswith('else'):
                if lines[k].startswith('else if'):
                    cond2 = _extract_paren(lines[k])
                    m = k + 1
                    while m < n and lines[m] != '{':
                        m += 1
                    body2, m = ([], m) if m >= n or lines[m] != '{' else _parse_block(lines, m + 1)
                    clauses.append((cond2, body2))
                    k = m
                else:
                    m = k + 1
                    while m < n and lines[m] != '{':
                        m += 1
                    else_block, m = ([], m) if m >= n or lines[m] != '{' else _parse_block(lines, m + 1)
                    k = m
                    break
            block.append({'type': 'if_chain', 'clauses': clauses, 'else': else_block})
            i = k
            continue

        # for loop
        if line.startswith('for'):
            cond = _extract_paren(line)
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            body, j = ([], j) if j >= n or lines[j] != '{' else _parse_block(lines, j + 1)
            block.append({'type': 'for', 'cond': cond, 'body': body})
            i = j
            continue

        # while loop
        if line.startswith('while'):
            cond = _extract_paren(line)
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            body, j = ([], j) if j >= n or lines[j] != '{' else _parse_block(lines, j + 1)
            block.append({'type': 'while', 'cond': cond, 'body': body})
            i = j
            continue

        # do-while loop
        if line.startswith('do'):
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            body, j = ([], j) if j >= n or lines[j] != '{' else _parse_block(lines, j + 1)
            cond = ''
            if j < n and lines[j].startswith('while'):
                cond = _extract_paren(lines[j])
                j += 1
            block.append({'type': 'do_while', 'cond': cond, 'body': body})
            i = j
            continue

        # switch statement
        if line.startswith('switch'):
            cond = _extract_paren(line)
            j = i + 1
            while j < n and lines[j] != '{':
                j += 1
            j += 1  # skip '{'
            cases = []
            current_case = None
            while j < n and lines[j] != '}':
                stmt = lines[j]
                if re.match(r'case .*?:', stmt) or re.match(r'default:', stmt):
                    if current_case:
                        cases.append(current_case)
                    current_case = {'type': 'case', 'label': stmt.rstrip(':'), 'body': []}
                elif current_case:
                    current_case['body'].append(stmt)
                j += 1
            if current_case:
                cases.append(current_case)
            block.append({'type': 'switch', 'cond': cond, 'cases': cases})
            i = j + 1
            continue

        # normal statement
        block.append({'type': 'stmt', 'code': line})
        i += 1

    return block, i

# ---------------------------
# Render AST to Mermaid
# ---------------------------
def parse_java_code(code: str) -> str:
    lines = _preprocess_lines(code)
    ast_root, _ = _parse_block(lines, 0)

    nodes = []
    edges = []
    id_counter = 0

    def new_id():
        nonlocal id_counter
        id_counter += 1
        return f"N{id_counter}"

    def add_node_rect(label):
        if not label.strip():
            label = " "
        nid = new_id()
        nodes.append(f'{nid}["{label}"]')
        return nid

    def add_node_diamond(label):
        nid = new_id()
        nodes.append(f'{nid}{{"{label}"}}')
        return nid

    def add_node_circle(label):
        nid = new_id()
        nodes.append(f'{nid}(({label}))')
        return nid

    def render_block(block):
        if not block:
            return (None, None)

        first = None
        last = None

        for stmt in block:
            if stmt['type'] == 'stmt':
                lbl = _safe_label(stmt['code'])
                if re.search(r'\bclass\b', lbl) or 'static void main' in lbl:
                    continue
                nid = add_node_rect(lbl)
                if first is None:
                    first = nid
                if last is not None:
                    edges.append((last, nid, None))
                last = nid

            elif stmt['type'] == 'if_chain':
                cond_first, cond_last = render_if_chain(stmt)
                if first is None:
                    first = cond_first
                if last is not None:
                    edges.append((last, cond_first, None))
                last = cond_last

            elif stmt['type'] in ['for', 'while']:
                cond_label = _safe_label(stmt['cond'])
                loop_type = stmt['type']
                cond_n = add_node_diamond(f"{loop_type} ({cond_label})")
                if first is None:
                    first = cond_n
                if last is not None:
                    edges.append((last, cond_n, None))
                if stmt['body']:
                    body_text = "\n".join([_safe_label(s['code']) if s['type']=='stmt' else '...' for s in stmt['body']])
                    body_n = add_node_rect(body_text)
                    edges.append((cond_n, body_n, "True"))
                    edges.append((body_n, cond_n, None))
                last = cond_n

            elif stmt['type'] == 'do_while':
                body_first, body_last = render_block(stmt['body'])
                cond_label = _safe_label(stmt['cond'])
                cond_n = add_node_diamond(f"do-while ({cond_label})")
                if first is None:
                    first = body_first
                if last is not None:
                    edges.append((last, body_first, None))
                edges.append((body_last, cond_n, None))
                edges.append((cond_n, body_first, "True"))
                last = cond_n

            elif stmt['type'] == 'switch':
                switch_label = _safe_label(stmt['cond'])
                switch_n = add_node_diamond(f'switch ({switch_label})')
                if first is None:
                    first = switch_n
                if last is not None:
                    edges.append((last, switch_n, None))
                merge_n = new_id()
                nodes.append(f'{merge_n}(( ))')
                for case_stmt in stmt['cases']:
                    case_body = "\n".join([_safe_label(s) for s in case_stmt['body']])
                    case_label = f"{case_stmt['label']}:\n{case_body}" if case_body else f"{case_stmt['label']}"
                    case_n = add_node_rect(case_label)
                    edges.append((switch_n, case_n, "case"))
                    edges.append((case_n, merge_n, None))
                last = merge_n

        return (first, last)

    def render_if_chain(if_node):
        clauses = if_node['clauses']
        else_block = if_node.get('else')
        merge_id = new_id()
        nodes.append(f'{merge_id}(( ))')

        prev_cond_id = None
        first_cond_id = None

        for cond, then_block in clauses:
            cond_label = _safe_label(cond)
            cond_id = add_node_diamond(cond_label)
            if first_cond_id is None:
                first_cond_id = cond_id
            if prev_cond_id is not None:
                edges.append((prev_cond_id, cond_id, "False"))
            then_first, then_last = render_block(then_block)
            if then_first:
                edges.append((cond_id, then_first, "True"))
                edges.append((then_last, merge_id, None))
            else:
                edges.append((cond_id, merge_id, "True"))
            prev_cond_id = cond_id

        if else_block is not None:
            else_first, else_last = render_block(else_block)
            if else_first:
                edges.append((prev_cond_id, else_first, "False"))
                edges.append((else_last, merge_id, None))
            else:
                edges.append((prev_cond_id, merge_id, "False"))
        else:
            edges.append((prev_cond_id, merge_id, "False"))

        return (first_cond_id, merge_id)

    start_id = add_node_circle("Start")
    end_id = add_node_circle("End")
    first_id, last_id = render_block(ast_root)

    if first_id:
        edges.insert(0, (start_id, first_id, None))
    else:
        edges.insert(0, (start_id, end_id, None))

    if last_id:
        edges.append((last_id, end_id, None))
    else:
        edges.append((start_id, end_id, None))

    mermaid_lines = ['flowchart TD']
    mermaid_lines.extend(nodes)

    for e in edges:
        if len(e) == 3 and e[2]:
            mermaid_lines.append(f'{e[0]} -->|{e[2]}| {e[1]}')
        else:
            mermaid_lines.append(f'{e[0]} --> {e[1]}')

    return '\n'.join(mermaid_lines)

# ---------------------------
# Test example
# ---------------------------
if __name__ == '__main__':
    sample = """
    public class Hello {
      public static void main(String[] args) {
        int x = 5;
        if (x > 0) {
            System.out.println("Positive");
        } else if (x == 0) {
            System.out.println("Zero");
        } else {
            System.out.println("Negative");
        }
        for (int i = 0; i < 3; i++) {
            System.out.println(i);
        }
        int j = 0;
        do {
            System.out.println(j);
            j++;
        } while (j < 3);
        switch(x) {
            case 1: System.out.println("One"); break;
            case 2: System.out.println("Two"); break;
            default: System.out.println("Other"); break;
        }
      }
    }
    """
    print(parse_java_code(sample))
