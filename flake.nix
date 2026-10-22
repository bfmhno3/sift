{
  description = "sift: companion code for the series 用 Sift 重学 Python";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      devShellsBySystem = nixpkgs.lib.genAttrs systems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python314.withPackages (
            p: with p; [
              pytest
              hypothesis
              pytest-cov
              pytest-benchmark
              pytest-asyncio
              pytest-qt
              mypy
              httpx
              fastapi
              uvicorn
              pydantic
              sqlalchemy
              numpy
              pandas
              matplotlib
              typer
              rich
              pyside6
              tkinter
              sv-ttk
              darkdetect
              qtawesome
              cffi
              cython
              setuptools
              hatchling
              build
              pip
              pyinstrument
              memray
            ]
          );
        in
        pkgs.mkShell {
          packages =
            [ python ]
            ++ (with pkgs; [
              python314FreeThreading
              ruff
              uv
              pyright
              py-spy
              maturin
              rustc
              cargo
              clippy
              rustfmt
              gcc
              gnumake
              perl
              sqlite
              hyperfine
              imagemagick
              xvfb-run
              git
              jq
              curl
            ]);
          shellHook = ''
            export FONTCONFIG_FILE=${
              pkgs.makeFontsConf {
                fontDirectories = [
                  pkgs.inter
                  pkgs.noto-fonts-cjk-sans
                  pkgs.jetbrains-mono
                ];
              }
            }
            export SIFT_CJK_FONT="${pkgs.noto-fonts-cjk-sans}/share/fonts/opentype/noto-cjk/NotoSansCJK-VF.otf.ttc"
            unset PYTHONPATH _PYTHON_SYSCONFIGDATA_NAME _PYTHON_HOST_PLATFORM
            if [ ! -d .venv ]; then python3 -m venv --system-site-packages .venv; fi; source .venv/bin/activate; pip install -q --no-deps --no-build-isolation -e .
            export UV_PYTHON_DOWNLOADS=never UV_PYTHON=python3.14 PYTHONHASHSEED=0
            echo "sift dev shell: $(python3 --version), $(python3.14t --version) (free-threaded), $(ruff --version), $(rustc --version)"
          '';
        }
      );
    in
    {
      devShells = nixpkgs.lib.mapAttrs (_: devShell: { default = devShell; }) devShellsBySystem;
      checks = nixpkgs.lib.mapAttrs (_: devShell: { dev-shell = devShell; }) devShellsBySystem;
    };
}
