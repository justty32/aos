# Tool math

Compute one arithmetic expression exactly, instead of in your head. Changes nothing.

Allowed: numbers (integers and decimals), `+ - * /`, `//` (floor division), `%` (remainder), `**` (power; exponent at most 1000), parentheses, signs. Not allowed: functions (`sqrt`, `abs`), letters or variables, `x` for times, units.

```json
{"expr": "17*23"}
```
-> `391`

- `{"expr": "(2+3)**2 // 4"}` -> `6`
- `{"expr": "7/2"}` -> `3.5` (`/` gives a decimal; `7//2` -> `3`)
- `{"expr": "2 ** 0.5"}` -> `1.4142135623730951` (a square root)
- `{"expr": "0.1+0.2"}` -> `0.30000000000000004` (decimals are floating point; round in your answer)

Errors: `aos/tools/math.md#/math: errors`.

# math: errors

- `ExprBad`: it cannot compute the expression. The reason says why: `division by zero`; `unsupported syntax: Call` (a function like `sqrt(2)`); `unsupported syntax: Name` (a letter or variable); `cannot parse expression: invalid syntax` (like `17 x 23`); `exponent too large (limit 1000)`; `unsupported syntax: Constant` (a string, `True` or other non-number); `cannot evaluate: ...` (a result too big). Rewrite it with only numbers and the allowed operators, then call once more. Do not retry the same expression.
- `ArgumentsBad`: `expr` is missing or not a string, or you gave another key. Call `{"expr": "17*23"}`.
