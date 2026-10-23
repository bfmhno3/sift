"""csv: export the top terms of the index, read them back."""

import csv
import tempfile
from pathlib import Path

from sift.cli import CORPUS
from sift.storage.store import open_index, update_index

NAMES = ("mixed", "nfkc", "stopwords")
FIELDS = ["term", "df", "tf"]


def top_terms(directory: Path, n: int) -> list[dict[str, str | int]]:
    """Return the n terms with the most documents, with their tf."""
    with open_index(directory) as index:
        segment = index.segment
        by_df = sorted(segment.terms, key=lambda t: (-segment.df(t), t))
        return [
            {
                "term": term,
                "df": segment.df(term),
                "tf": sum(p.tf for p in index[term]),
            }
            for term in by_df[:n]
        ]


def main() -> None:
    """Write top_terms.csv, read it back, show quoting rules."""
    with tempfile.TemporaryDirectory(prefix="sift-csv-") as tmp:
        root = Path(tmp)
        update_index(CORPUS, root / "idx", NAMES)
        rows = top_terms(root / "idx", 10)
        path = root / "top_terms.csv"
        # newline="" lets the csv module control the line endings
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print("raw bytes:", path.read_bytes()[:60])
        with path.open(encoding="utf-8", newline="") as file:
            back = list(csv.DictReader(file))
        print("rows read back:", len(back))
        print("first row     :", back[0])
        print("types are str :", type(back[0]["df"]).__name__)
        print(
            "same terms    :",
            [r["term"] for r in back] == [r["term"] for r in rows],
        )
        print(
            "same numbers  :",
            [int(r["df"]) for r in back] == [r["df"] for r in rows],
        )

        print("--- quoting")
        tricky = [
            ["a,b", 'say "hi"', "line\nbreak", "索引"],
        ]
        quoted = root / "quoted.csv"
        with quoted.open("w", encoding="utf-8", newline="") as file:
            csv.writer(file).writerows(tricky)
        print("written:", quoted.read_bytes())
        with quoted.open(encoding="utf-8", newline="") as file:
            print("read   :", list(csv.reader(file)))
        print("dialects:", sorted(csv.list_dialects()))
        with quoted.open("w", encoding="utf-8", newline="") as file:
            csv.writer(file, delimiter="\t").writerow(["a", "b c"])
        print("tab-delimited:", quoted.read_bytes())


if __name__ == "__main__":
    main()
