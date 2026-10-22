"""The query parser: recursive descent, one function per rule.

::

    query  := or EOF
    or     := and ("OR" and)*
    and    := unary (("AND")? unary)*
    unary  := "NOT" unary | "-" atom | atom
    atom   := "(" or ")" | PHRASE | FIELD ":" (WORD | PHRASE)
              | WORD "*"?

NOT binds tighter than AND, and AND tighter than OR. Both binary
operators are left-associative.
"""

from sift.errors import QuerySyntaxError
from sift.query.ast import And, Field, Node, Not, Or, Phrase, Prefix, Term
from sift.query.lexer import Kind, QToken, iter_tokens

MAX_DEPTH = 100
"""Deepest nesting of parentheses that parse accepts.

Each level costs four Python frames, so 100 levels stay far below the
default recursion limit of 1000. Only parentheses are counted: a flat
chain of a thousand terms still hits the limit (a known gap).
"""

_STARTS_UNARY = frozenset(
    {Kind.WORD, Kind.PHRASE, Kind.FIELD, Kind.LPAREN, Kind.NOT, Kind.MINUS}
)


class _Parser:
    """The state of one parse: the tokens and the current index."""

    def __init__(self, query: str) -> None:
        """Lex query completely, then point at the first token."""
        self.query = query
        self.tokens = list(iter_tokens(query))
        self.i = 0
        self.depth = 0

    @property
    def peek(self) -> QToken:
        """Return the current token without consuming it."""
        return self.tokens[self.i]

    def take(self) -> QToken:
        """Consume and return the current token."""
        token = self.tokens[self.i]
        self.i += 1
        return token

    def fail(
        self, message: str, token: QToken | None = None
    ) -> QuerySyntaxError:
        """Return an error at token, by default the current one."""
        token = token or self.peek
        return QuerySyntaxError(message, self.query, token.pos)

    def parse_query(self) -> Node:
        """Parse a whole query and require the end of input."""
        node = self.parse_or()
        if self.peek.kind is not Kind.EOF:
            raise self.fail(f"unexpected {self.peek.text!r}")
        return node

    def parse_or(self) -> Node:
        """Parse ``and ("OR" and)*``."""
        node = self.parse_and()
        while self.peek.kind is Kind.OR:
            self.take()
            node = Or(node, self.parse_and())
        return node

    def parse_and(self) -> Node:
        """Parse ``unary (("AND")? unary)*``."""
        node = self.parse_unary()
        while True:
            if self.peek.kind is Kind.AND:
                self.take()
            elif self.peek.kind not in _STARTS_UNARY:
                return node
            node = And(node, self.parse_unary())

    def parse_unary(self) -> Node:
        """Parse ``"NOT" unary | "-" atom | atom``."""
        match self.peek.kind:
            case Kind.NOT:
                self.take()
                return Not(self.parse_unary())
            case Kind.MINUS:
                self.take()
                return Not(self.parse_atom())
            case _:
                return self.parse_atom()

    def parse_atom(self) -> Node:
        """Parse a parenthesized query, a phrase, a field or a word."""
        token = self.take()
        match token.kind:
            case Kind.LPAREN:
                self.depth += 1
                if self.depth > MAX_DEPTH:
                    raise self.fail("query nested too deeply", token)
                node = self.parse_or()
                self.depth -= 1
                if self.peek.kind is not Kind.RPAREN:
                    raise self.fail("expected ')'")
                self.take()
                return node
            case Kind.PHRASE:
                return Phrase(tuple(token.text.split()))
            case Kind.FIELD:
                return Field(token.text, self.parse_field_value(token))
            case Kind.WORD:
                if self.peek.kind is Kind.STAR:
                    self.take()
                    return Prefix(token.text)
                return Term(token.text)
            case Kind.EOF:
                raise self.fail("expected a term", token)
            case _:
                raise self.fail(f"unexpected {token.text!r}", token)

    def parse_field_value(self, field: QToken) -> Node:
        """Parse the word or phrase after ``field:``."""
        token = self.take()
        match token.kind:
            case Kind.WORD:
                return Term(token.text)
            case Kind.PHRASE:
                return Phrase(tuple(token.text.split()))
            case _:
                raise self.fail(f"expected a value after {field.text}:", token)


def has_positive(node: Node) -> bool:
    """Return True if node can match through a term, not only a NOT.

    A conjunction needs one positive side, a disjunction needs both.
    """
    match node:
        case Not():
            return False
        case And(left, right):
            return has_positive(left) or has_positive(right)
        case Or(left, right):
            return has_positive(left) and has_positive(right)
        case _:
            return True


def parse(query: str) -> Node:
    """Parse query into a syntax tree.

    Raise QuerySyntaxError on a malformed query, and on a query that
    has no positive term (``-latex``).
    """
    parser = _Parser(query)
    node = parser.parse_query()
    if not has_positive(node):
        raise QuerySyntaxError(
            "query needs at least one positive term", query, 0
        )
    return node
