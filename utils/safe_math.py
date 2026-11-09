import ast
import math
import operator

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

MAX_EXPRESSION_LENGTH = 200
MAX_AST_NODES = 100
MAX_POWER = 100
MAX_ABS_RESULT = 1e100


def _check_number(value):
    if type(value) not in (int, float):
        raise ValueError("Разрешены только действительные числа.")
    if abs(value) > MAX_ABS_RESULT:
        raise ValueError("Число превышает допустимый предел.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Число должно быть конечным.")
    return value


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)

    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _check_number(node.value)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _check_number(_UNARYOPS[type(node.op)](_evaluate(node.operand)))

    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER:
            raise ValueError(f"Степень ограничена значением {MAX_POWER}.")
        return _check_number(_BINOPS[type(node.op)](left, right))

    raise ValueError("Разрешены только числа и арифметические операции.")


def calculate(expression: str) -> int | float:
    expression = expression.strip()
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Пустое или слишком длинное выражение.")

    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise ValueError("Слишком сложное выражение.")
        return _evaluate(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"Не удалось вычислить выражение: {exc}") from exc
