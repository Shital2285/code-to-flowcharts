
import ast
import html

def safe_label(text):
    # Only escape essential HTML characters, but don't re-escape already escaped quotes
    # The original html.escape handles most, but we want to ensure quotes from ast.unparse are fine.
    escaped_text = html.escape(text, quote=False) # Keep original quotes from unparse if they are there
    return escaped_text.replace('\n', ' ').replace('&quot;', '"').replace('&#x27;', "'") # Unescape specific quote entities

def code_to_flowchart(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f'graph TD\nStart((Start))\nerror["Error: {html.escape(str(e))}"] --> End((End))\n'

    lines = ["graph TD", "Start((Start))"]
    node_counter = 0

    def get_id():
        nonlocal node_counter
        node_counter += 1
        return f"n{node_counter}"

    last = "Start"

    def handle_expr(node):
        label_text = ""
        shape_type = ""

        try:
            # Case 1: Print statement (highest priority for custom formatting)
            if isinstance(node, ast.Expr) and \
               isinstance(node.value, ast.Call) and \
               isinstance(node.value.func, ast.Name) and \
               node.value.func.id == 'print' and \
               len(node.value.args) == 1 and \
               isinstance(node.value.args[0], ast.Constant) and \
               isinstance(node.value.args[0].value, str):
                
                content = node.value.args[0].value
                label_text = f"Output: {content}"
                shape_type = '[/"{}"/]' # Parallelogram for Output
            
            # Case 2: Assignment involving input() (e.g., x = input(...) or x = float(input(...)))
            elif isinstance(node, ast.Assign):
                input_prompt = None
                conversion_func = None # To store 'int', 'float', etc.
                
                # Check the right-hand side of the assignment
                rhs_call = node.value

                # If RHS is a direct input() call
                if isinstance(rhs_call, ast.Call) and \
                   isinstance(rhs_call.func, ast.Name) and \
                   rhs_call.func.id == "input" and \
                   len(rhs_call.args) == 1 and \
                   isinstance(rhs_call.args[0], ast.Constant) and \
                   isinstance(rhs_call.args[0].value, str):
                    input_prompt = rhs_call.args[0].value
                        
                # If RHS is a call wrapping an input() call (e.g., float(input(...)))
                elif isinstance(rhs_call, ast.Call) and \
                     isinstance(rhs_call.func, ast.Name) and \
                     len(rhs_call.args) == 1 and \
                     isinstance(rhs_call.args[0], ast.Call) and \
                     isinstance(rhs_call.args[0].func, ast.Name) and \
                     rhs_call.args[0].func.id == "input" and \
                     len(rhs_call.args[0].args) == 1 and \
                     isinstance(rhs_call.args[0].args[0], ast.Constant) and \
                     isinstance(rhs_call.args[0].args[0].value, str):
                    
                    input_prompt = rhs_call.args[0].args[0].value
                    conversion_func = rhs_call.func.id # e.g., 'float', 'int'

                if input_prompt is not None:
                    # Prepend the variable name for clarity
                    target_name = ast.unparse(node.targets[0]).strip() if node.targets else "value"
                    if conversion_func:
                        label_text = f"Input {target_name}: {input_prompt} (as {conversion_func})"
                    else:
                        label_text = f"Input {target_name}: {input_prompt}"
                    shape_type = '[/"{}"/]' # Parallelogram for Input
                else:
                    # It's an assignment, but not an input-related one (or not parsed as such)
                    # Fallback to general assignment handling
                    label_text = ast.unparse(node).strip().splitlines()[0]
                    if len(label_text) > 50:
                        label_text = label_text[:47] + "..."
                    shape_type = '["{}"]' # Default to Rectangle for other assignments
            
            # Case 3: Other expressions that are calls (not assignments, not prints, e.g., func())
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                label_text = ast.unparse(node).strip().splitlines()[0]
                if len(label_text) > 50:
                    label_text = label_text[:47] + "..."
                shape_type = '[/"{}"/]' # Parallelogram for generic function calls
                
            # Case 4: Any other general statement
            else:
                label_text = ast.unparse(node).strip().splitlines()[0]
                if len(label_text) > 50:
                    label_text = label_text[:47] + "..."
                shape_type = '["{}"]' # Rectangle for generic process

        except Exception: # Fallback for any parsing error
            label_text = str(type(node).__name__)
            shape_type = '["{}"]' # Fallback to rectangle

        return shape_type.format(safe_label(label_text))

    # This function will handle if/elif/else chains recursively
    def handle_if_elif_else(if_node, current_last_node, is_top_level_if_last_statement):
        nonlocal last # Needed to update the global 'last' node when merging
        
        cond_id = get_id()
        cond_lbl = safe_label(ast.unparse(if_node.test).strip())
        lines.append(f'{cond_id}{{"{cond_lbl}"}}')  # Decision: Diamond
        lines.append(f"{current_last_node} --> {cond_id}")

        branch_ends = [] # To collect the last nodes of all executed branches

        # Yes branch (if condition is true)
        yes_last = cond_id
        if if_node.body:
            for stmt in if_node.body:
                sid = get_id()
                lines.append(f"{yes_last} -- Yes --> {sid}{handle_expr(stmt)}")
                yes_last = sid
        else:
            # If 'yes' branch is empty, create a 'No action' node
            yes_id = get_id()
            lines.append(f"{cond_id} -- Yes --> {yes_id}[[No action]]")
            yes_last = yes_id
        branch_ends.append(yes_last)

        # No branch (else or elif)
        if if_node.orelse:
            # If orelse contains exactly one 'if' statement, it's an elif
            if len(if_node.orelse) == 1 and isinstance(if_node.orelse[0], ast.If):
                # Recursively handle the elif as a new if statement
                elif_last_node = handle_if_elif_else(if_node.orelse[0], cond_id, is_top_level_if_last_statement)
                branch_ends.append(elif_last_node)
            else:
                # This is a true 'else' block, process its statements
                no_last = cond_id
                for stmt in if_node.orelse:
                    sid = get_id()
                    lines.append(f"{no_last} -- No --> {sid}{handle_expr(stmt)}")
                    no_last = sid
                branch_ends.append(no_last)
        else:
            # If there's no else/elif block, create a 'No action' node for the 'No' path
            no_id = get_id()
            lines.append(f"{cond_id} -- No --> {no_id}[[No action]]")
            branch_ends.append(no_id)
        
        # Merge Logic for this IF block:
        # If this is the last statement in the program, all branches go to End
        if is_top_level_if_last_statement:
            for branch_end in branch_ends:
                lines.append(f"{branch_end} --> End")
            return "End" # The entire if chain terminates here
        else:
            # Otherwise, create a merge node for this IF block and return it
            merge_id = get_id()
            for branch_end in branch_ends:
                lines.append(f"{branch_end} --> {merge_id}")
            return merge_id

    # --- Function to handle loops (For and While) ---
    def handle_loop(loop_node, current_last_node, is_top_level_loop_last_statement):
        nonlocal last

        loop_condition_id = get_id()
        
        # Label for the loop condition (diamond)
        loop_cond_label = ""
        if isinstance(loop_node, ast.For):
            # For a 'for' loop, the condition is implicit in the iterable
            # We can represent it as "For [target] in [iter]"
            target_str = ast.unparse(loop_node.target).strip()
            iter_str = ast.unparse(loop_node.iter).strip()
            loop_cond_label = f"For {target_str} in {iter_str}"
        elif isinstance(loop_node, ast.While):
            loop_cond_label = ast.unparse(loop_node.test).strip()

        lines.append(f'{loop_condition_id}{{"{safe_label(loop_cond_label)}"}}')
        lines.append(f"{current_last_node} --> {loop_condition_id}")

        # Process loop body
        loop_body_last = loop_condition_id
        if loop_node.body:
            # Connect from loop condition to the first statement of the body
            # This is the "Yes" path of the loop condition
            first_stmt_in_body = loop_node.body[0]
            first_body_node_id = get_id()
            lines.append(f"{loop_condition_id} -- Yes --> {first_body_node_id}{handle_expr(first_stmt_in_body)}")
            loop_body_last = first_body_node_id

            for stmt in loop_node.body[1:]:
                sid = get_id()
                lines.append(f"{loop_body_last} --> {sid}{handle_expr(stmt)}")
                loop_body_last = sid
        else:
            # Empty loop body
            empty_body_id = get_id()
            lines.append(f"{loop_condition_id} -- Yes --> {empty_body_id}[[Empty Loop Body]]")
            loop_body_last = empty_body_id

        # Add the back-edge from the end of the loop body to the loop condition
        lines.append(f"{loop_body_last} --> {loop_condition_id}")

        # Handle the 'No' path (exit from loop)
        loop_exit_node_id = get_id()
        lines.append(f"{loop_condition_id} -- No --> {loop_exit_node_id}")

        # If the loop is the last statement, connect its exit directly to End
        if is_top_level_loop_last_statement:
            lines.append(f"{loop_exit_node_id} --> End")
            return "End"
        else:
            # Otherwise, the loop's exit becomes the 'last' node for subsequent statements
            return loop_exit_node_id


    for i, node in enumerate(tree.body):
        is_last_statement = (i == len(tree.body) - 1)

        if isinstance(node, ast.Assign) or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            nid = get_id()
            lines.append(f"{nid}{handle_expr(node)}")
            lines.append(f"{last} --> {nid}")
            last = nid

        elif isinstance(node, ast.If):
            last = handle_if_elif_else(node, last, is_last_statement)
            
        elif isinstance(node, ast.Match):
            match_id = get_id()
            match_expr_lbl = safe_label(ast.unparse(node.subject).strip())
            lines.append(f'{match_id}{{"Match {match_expr_lbl}"}}')
            lines.append(f"{last} --> {match_id}")

            branch_ends = []

            for case_num, case in enumerate(node.cases):
                case_branch_last = match_id

                if case.pattern:
                    case_lbl = safe_label(f"case {ast.unparse(case.pattern).strip()}")
                else:
                    case_lbl = "case (default)"

                if case.body:
                    first_stmt = case.body[0]
                    first_case_id = get_id()
                    lines.append(f"{match_id} -- {case_lbl} --> {first_case_id}{handle_expr(first_stmt)}")
                    case_branch_last = first_case_id
                    for stmt in case.body[1:]:
                        sid = get_id()
                        lines.append(f"{case_branch_last} --> {sid}{handle_expr(stmt)}")
                        case_branch_last = sid
                else:
                    empty_case_id = get_id()
                    lines.append(f"{match_id} -- {case_lbl} --> {empty_case_id}[[No action]]")
                    case_branch_last = empty_case_id
                
                branch_ends.append(case_branch_last)

            if is_last_statement:
                for branch_end in branch_ends:
                    lines.append(f"{branch_end} --> End")
                last = "End"
            else:
                match_merge_id = get_id()
                for branch_end in branch_ends:
                    lines.append(f"{branch_end} --> {match_merge_id}")
                last = match_merge_id

        # --- Handle ast.For and ast.While loops ---
        elif isinstance(node, (ast.For, ast.While)):
            last = handle_loop(node, last, is_last_statement)

        else:
            nid = get_id()
            lines.append(f"{nid}{handle_expr(node)}")
            lines.append(f"{last} --> {nid}")
            last = nid
    
    if last != "End":
        lines.append(f"{last} --> End((End))")
    
    lines.append("End((End))")

    return "\n".join(lines)









