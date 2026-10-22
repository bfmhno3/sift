"""Tests for sift.query: lexer, parser, printer and evaluator."""

import pytest

from sift.errors import QuerySyntaxError
from sift.index import InvertedIndex
from sift.query import (
    And,
    Field,
    Kind,
    Not,
    Or,
    Phrase,
    Prefix,
    Term,
    evaluate,
    iter_tokens,
    parse,
    print_query,
)
from sift.query.evaluate import phrase_postings
from sift.query.parser import MAX_DEPTH, has_positive


def kinds(query: str) -> list[Kind]:
    """Return the token kinds of query, EOF included."""
    return [token.kind for token in iter_tokens(query)]


def test_lexer_kinds_and_positions() -> None:
    tokens = list(iter_tokens('title:foo AND (bar* OR -"a b")'))
    assert [(t.kind.name, t.pos) for t in tokens] == [
        ("FIELD", 0),
        ("WORD", 6),
        ("AND", 10),
        ("LPAREN", 14),
        ("WORD", 15),
        ("STAR", 18),
        ("OR", 20),
        ("MINUS", 23),
        ("PHRASE", 24),
        ("RPAREN", 29),
        ("EOF", 30),
    ]


def test_lexer_operators_need_upper_case() -> None:
    assert kinds("and or not")[:-1] == [Kind.WORD] * 3
    assert kinds("AND OR NOT")[:-1] == [Kind.AND, Kind.OR, Kind.NOT]


def test_lexer_minus_inside_a_word_is_a_letter() -> None:
    tokens = list(iter_tokens("well-known"))
    assert [t.text for t in tokens[:-1]] == ["well-known"]


def test_lexer_colon_after_unknown_field_stays_in_the_word() -> None:
    assert [t.text for t in iter_tokens("a:b")][:-1] == ["a:b"]
    assert kinds("tag:b")[:2] == [Kind.FIELD, Kind.WORD]


def test_lexer_empty_query_is_just_eof() -> None:
    assert kinds("   ") == [Kind.EOF]


def test_lexer_unterminated_phrase() -> None:
    with pytest.raises(QuerySyntaxError, match="unterminated phrase") as e:
        list(iter_tokens('abc "def'))
    assert e.value.position == 4


@pytest.mark.parametrize(
    ("query", "tree"),
    [
        ("a", Term("a")),
        ("a*", Prefix("a")),
        ('"a b"', Phrase(("a", "b"))),
        ('""', Phrase(())),
        ("tag:x", Field("tag", Term("x"))),
        ('title:"x y"', Field("title", Phrase(("x", "y")))),
        ("a b", And(Term("a"), Term("b"))),
        ("a AND b", And(Term("a"), Term("b"))),
        ("a OR b", Or(Term("a"), Term("b"))),
        ("a -b", And(Term("a"), Not(Term("b")))),
        ("a NOT b", And(Term("a"), Not(Term("b")))),
        ("a NOT NOT b", And(Term("a"), Not(Not(Term("b"))))),
        (
            "a b OR c d",
            Or(And(Term("a"), Term("b")), And(Term("c"), Term("d"))),
        ),
        (
            "a OR b OR c",
            Or(Or(Term("a"), Term("b")), Term("c")),
        ),
        (
            "a AND (b OR c)",
            And(Term("a"), Or(Term("b"), Term("c"))),
        ),
        ("((a))", Term("a")),
    ],
)
def test_parse(query: str, tree: object) -> None:
    assert parse(query) == tree


@pytest.mark.parametrize(
    ("query", "message", "position"),
    [
        ("", "expected a term", 0),
        ("a AND", "expected a term", 5),
        ("(a", r"expected '\)'", 2),
        ("a)", r"unexpected '\)'", 1),
        ("*", r"unexpected '\*'", 0),
        ("tag:", "expected a value after tag:", 4),
        ("tag:(a)", "expected a value after tag:", 4),
        ("-a", "at least one positive term", 0),
        ("a OR -b", "at least one positive term", 0),
        ("NOT a", "at least one positive term", 0),
        ('a "b', "unterminated phrase", 2),
    ],
)
def test_parse_errors(query: str, message: str, position: int) -> None:
    with pytest.raises(QuerySyntaxError, match=message) as caught:
        parse(query)
    assert caught.value.position == position
    assert caught.value.query == query


def test_parse_depth_limit() -> None:
    ok = "(" * MAX_DEPTH + "a" + ")" * MAX_DEPTH
    assert parse(ok) == Term("a")
    too_deep = "(" * (MAX_DEPTH + 1) + "a" + ")" * (MAX_DEPTH + 1)
    with pytest.raises(QuerySyntaxError, match="nested too deeply"):
        parse(too_deep)


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        (Term("a"), True),
        (Not(Term("a")), False),
        (And(Term("a"), Not(Term("b"))), True),
        (And(Not(Term("a")), Not(Term("b"))), False),
        (Or(Term("a"), Not(Term("b"))), False),
        (Or(Term("a"), Term("b")), True),
    ],
)
def test_has_positive(node: object, expected: bool) -> None:
    assert has_positive(node) is expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("node", "text"),
    [
        (Term("a"), "a"),
        (Prefix("ab"), "ab*"),
        (Phrase(("x", "y")), '"x y"'),
        (Phrase(()), '""'),
        (Field("tag", Term("x")), "tag:x"),
        (And(Term("a"), And(Term("b"), Term("c"))), "a AND (b AND c)"),
        (And(And(Term("a"), Term("b")), Term("c")), "a AND b AND c"),
        (Or(Term("a"), Or(Term("b"), Term("c"))), "a OR (b OR c)"),
        (And(Or(Term("a"), Term("b")), Term("c")), "(a OR b) AND c"),
        (Or(And(Term("a"), Term("b")), Term("c")), "a AND b OR c"),
        (Not(And(Term("a"), Term("b"))), "NOT (a AND b)"),
        (Not(Not(Term("a"))), "NOT NOT a"),
    ],
)
def test_print_query(node: object, text: str) -> None:
    assert print_query(node) == text  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "query",
    [
        "a b OR c -d",
        'tag:x "p q" (y OR z*) NOT w',
        "a OR b AND c OR d",
        "((a OR b) AND (c OR d)) OR e",
    ],
)
def test_print_query_round_trips_parsed_queries(query: str) -> None:
    tree = parse(query)
    assert parse(print_query(tree)) == tree


def ids(query: str, index: InvertedIndex) -> list[int]:
    """Return the doc_ids that match query."""
    return evaluate(parse(query), index).doc_ids()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("chain", [1]),
        ("CHAIN", [1]),
        ("zebra", []),
        ("tea", [6, 7]),
        ("tea AND green", [6, 7]),
        ("tea green", [6, 7]),
        ("tea OR parsing", [2, 6, 7]),
        ("chain -quick", []),
        ("chain -zebra", [1]),
        ("chain NOT zebra", [1]),
        ("(chain OR parser) AND tool", [1]),
        ('"chain tool"', [1]),
        ('"tool chain"', []),
        ('"chain bridge"', []),
        ("tool chain", [1]),
        ("chai*", [1]),
        ("编译", [3]),
        ("语法树", [3]),
        ("title:chain", [1]),
        ("title:tool", []),
        ('title:"bicycle chain"', [1]),
        ("tag:river", [5]),
        ("tag:RIVER", [5]),
        ("tag:河流", [4]),
        ('tag:"生活"', [6]),
        ("category:notes", [0, 1, 2, 3, 4, 5, 6, 7]),
        ("series:none", []),
        ("flow tag:river", [5]),
        ("river -tag:river", []),
    ],
)
def test_evaluate(query: str, expected: list[int], mini_index) -> None:
    assert ids(query, mini_index) == expected


def test_evaluate_bare_not_uses_the_universe(mini_index) -> None:
    node = Not(Term("chain"))
    assert evaluate(node, mini_index).doc_ids() == [0, 2, 3, 4, 5, 6, 7]


def test_phrase_postings_report_start_positions(mini_index) -> None:
    found = phrase_postings(mini_index, ["chain", "tool"])
    (posting,) = list(found)
    assert posting.doc_id == 1
    assert posting.tf == 2
    chain = mini_index["chain"][0].positions
    assert posting.positions[0] in chain


def test_phrase_postings_edge_cases(mini_index) -> None:
    assert phrase_postings(mini_index, []).doc_ids() == []
    assert phrase_postings(mini_index, ["chain"]) == mini_index["chain"]
    assert phrase_postings(mini_index, ["chain", "zebra"]).doc_ids() == []


def test_evaluate_rejects_a_bad_field(mini_index) -> None:
    with pytest.raises(ValueError, match="unknown field: 'nope'"):
        evaluate(Field("nope", Term("x")), mini_index)


def test_prefix_without_terms_matches_nothing(mini_index) -> None:
    assert evaluate(Prefix("--"), mini_index).doc_ids() == []


@pytest.mark.parametrize("value", [Prefix("x"), Not(Term("x"))])
def test_evaluate_rejects_a_bad_field_value(value, mini_index) -> None:
    with pytest.raises(ValueError, match="bad field value"):
        evaluate(Field("tag", value), mini_index)


def test_evaluate_and_print_refuse_a_non_node(mini_index) -> None:
    with pytest.raises(AssertionError, match="unreachable"):
        evaluate("chain", mini_index)  # type: ignore[arg-type]
    with pytest.raises(AssertionError, match="unreachable"):
        print_query("chain")  # type: ignore[arg-type]
