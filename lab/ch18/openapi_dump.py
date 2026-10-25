"""Write the OpenAPI document of the Sift app to out/ch18/openapi.json.

``app.openapi()`` builds the document from the routes, the parameter
types and the pydantic models; no server and no index are needed,
because the Searcher is only opened by the lifespan handler. The
script prints the paths with their parameters and responses, and the
JSON schema of one model.
"""

import json
from contextlib import AbstractContextManager
from pathlib import Path

from sift.config import Config
from sift.search import Searcher
from sift.server.app import create_app

OUT = Path("out/ch18/openapi.json")


def no_index() -> AbstractContextManager[Searcher]:
    """Stand in for the opener: the lifespan handler never runs here."""
    raise RuntimeError("no index is opened to build the document")


def main() -> None:
    """Dump the document and print what is in it."""
    spec = create_app(no_index, Config()).openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print("openapi:", spec["openapi"], "- title:", spec["info"]["title"])
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            params = [
                f"{p['name']} ({p['in']}"
                + ("" if p["required"] else ", optional")
                + ")"
                for p in operation.get("parameters", [])
            ]
            codes = ", ".join(operation["responses"])
            print(f"{method.upper()} {path}: {', '.join(params) or '-'}")
            print(f"    responses: {codes}")
    print("schemas:", ", ".join(spec["components"]["schemas"]))
    limit = spec["paths"]["/search"]["get"]["parameters"][1]
    print("limit parameter:", json.dumps(limit["schema"]))
    print(
        "ErrorResponse:",
        json.dumps(spec["components"]["schemas"]["ErrorResponse"]),
    )


if __name__ == "__main__":
    main()
