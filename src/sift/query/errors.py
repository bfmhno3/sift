"""Query errors: plain classes for now (ch09 moves them)."""


class QuerySyntaxError(Exception):
    """A query that does not follow the grammar.

    str(error) is the message alone. query is the text that failed
    and position an offset into it.
    """

    def __init__(self, message: str, query: str, position: int) -> None:
        """Keep the message, the query and the offset."""
        super().__init__(message)
        self.message = message
        self.query = query
        self.position = position

    def render(self) -> str:
        """Return the message, the query line and a caret line."""
        caret = " " * self.position + "^"
        return f"{self.message}\n  {self.query}\n  {caret}"
