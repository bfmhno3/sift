---
title: Parsing with recursive descent
published: "2026-01-07 08:00:00 +08:00"
tags:
  - compiler
  - parser
category: Notes
---

# Parsing with recursive descent

A recursive descent parser has one function per grammar rule.

## Precedence

Lower precedence rules call higher precedence rules, so `1 + 2 * 3` groups as expected.

| Rule | Calls |
| --- | --- |
| expr | term |
| term | factor |
| factor | number |

```python
def expr(tokens: list[str]) -> int:
    return int(tokens[0])
```

Read more in [Crafting Interpreters](https://example.com/crafting).

Each function consumes tokens and returns a node.
Errors are reported with the position of the offending token.
It is the simplest parsing technique that scales.
