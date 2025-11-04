# shared/functions/calculator.py
import operator

def calculate(expression: str) -> float:
    # Simple, sandboxed eval
    allowed = {"abs": abs, "round": round, **operator.__dict__}
    return eval(expression, {"__builtins__": None}, allowed)
