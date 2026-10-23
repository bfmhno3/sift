"""zipfile: bundle the index directory and read members back."""

import shutil
import tempfile
import zipfile
from pathlib import Path

from sift.cli import CORPUS
from sift.storage.store import update_index

NAMES = ("mixed", "nfkc", "stopwords")


def bundle(source: Path, target: Path, method: int) -> int:
    """Zip every file of source into target; return the zip size."""
    with zipfile.ZipFile(target, "w", compression=method) as archive:
        for path in sorted(source.iterdir()):
            archive.write(path, arcname=path.name)
    return target.stat().st_size


def main() -> None:
    """Zip the index three ways and inspect the archive."""
    with tempfile.TemporaryDirectory(prefix="sift-zip-") as tmp:
        root = Path(tmp)
        update_index(CORPUS, root / "idx", NAMES)
        raw = sum(p.stat().st_size for p in (root / "idx").iterdir())
        print(f"index directory: {raw} bytes")
        methods = {
            "stored": zipfile.ZIP_STORED,
            "deflated": zipfile.ZIP_DEFLATED,
            "zstandard": zipfile.ZIP_ZSTANDARD,
        }
        for name, method in methods.items():
            size = bundle(root / "idx", root / f"{name}.zip", method)
            print(f"{name:<10} {size:>9} bytes  {size / raw:.3f}")

        print("--- members of deflated.zip")
        with zipfile.ZipFile(root / "deflated.zip") as archive:
            for info in archive.infolist():
                print(
                    f"{info.filename:<14} {info.file_size:>9} -> "
                    f"{info.compress_size:>9}  crc {info.CRC:08x}"
                )
            print("testzip():", archive.testzip())
            manifest = archive.read("manifest.json")
            print("manifest.json starts:", manifest[:30])
            with archive.open("segment.sft") as member:
                print("segment magic:", member.read(4))
        print("--- shutil.make_archive")
        made = shutil.make_archive(str(root / "snapshot"), "zip", root / "idx")
        print("made:", Path(made).name, zipfile.is_zipfile(made))


if __name__ == "__main__":
    main()
