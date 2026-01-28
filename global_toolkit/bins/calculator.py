#!/usr/bin/env python3
"""
Calculator Skill - 安全的数学计算器

支持基本的数学运算，使用安全的 eval 方式
Usage: python calculator.py <expression>
"""

import sys
import ast
import operator


class SafeCalculator:
    """安全的计算器，只允许基本数学运算"""

    # 允许的运算符
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def evaluate(self, expression: str) -> float:
        """安全地计算数学表达式

        Args:
            expression: 数学表达式字符串

        Returns:
            计算结果
        """
        try:
            tree = ast.parse(expression, mode='eval')
            return self._eval_node(tree.body)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def _eval_node(self, node):
        """递归计算 AST 节点"""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported node type: {type(node).__name__}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python calculator.py <expression>")
        print("\nExamples:")
        print("  python calculator.py '2 + 3'")
        print("  python calculator.py '10 * (5 + 3)'")
        print("  python calculator.py '2 ** 8'")
        print("  python calculator.py '100 / 3'")
        sys.exit(1)

    expression = ' '.join(sys.argv[1:])

    try:
        calc = SafeCalculator()
        result = calc.evaluate(expression)
        print(f"{expression} = {result}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
