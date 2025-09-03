# backend/parser.py
import re
import python_parser   # your Python handler
import java_parser     # your Java handler
import c_parser        # ✅ new import

def detect_language(code: str) -> str:
    if "public class" in code or "System.out" in code:
        return "java"
    elif "#include" in code or "printf" in code or "scanf" in code:
        return "c"
    else:
        return "python"

def flowchart_from_input(code: str) -> str:
    lang = detect_language(code)

    if lang == "java":
        return java_parser.code_to_flowchart(code)
    elif lang == "c":
        return c_parser.code_to_flowchart(code)
    else:
        return python_parser.code_to_flowchart(code)
