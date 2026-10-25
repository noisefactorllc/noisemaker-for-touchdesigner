# Noisemaker for TouchDesigner

TouchDesigner integration and compiler for the Noisemaker shader platform.

## Rules

Never create, introduce or use symbolic links anywhere in checkouts, repositories, configuration, scripts or documentation. Every file is a regular file.

Write and present research documents in the established technical whitepaper style. Never use slop headlines, promotional or slogan headers, parenthetical subtitles in titles, stat cards, metric cards, decorative callouts, marketing-speak or invented report layouts.

## Testing & Build

- **Unit tests**: `./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"`
- **Compiler Parity Gates**: `for f in check_lex.py check_parse.py check_validate.py check_graph.py; do NM_REFERENCE_ROOT=/path/to/noisemaker ./parity/.venv/bin/python3 "parity/compiler/$f"; done`
- **Definitions conversion**: `NM_REFERENCE_ROOT=/path/to/noisemaker node tools/convert-definitions.mjs`
