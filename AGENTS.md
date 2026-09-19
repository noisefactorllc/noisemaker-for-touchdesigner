# Noisemaker for TouchDesigner

TouchDesigner integration and compiler for the Noisemaker shader platform.

## Strict Rules

HARD, PERMANENT, INVIOLABLE BAN: BANNED FROM SYMLINKS. Never create, introduce, or use symbolic links anywhere in checkouts, repositories, configuration, scripts, or documentation. All files must be regular files. Zero exceptions.

HARD, PERMANENT, INVIOLABLE BAN: Research documents must be written and presented strictly in the established technical whitepaper style. Banned from slop headlines, promotional/slogan headers, parenthetical subtitles in titles, stat cards, metric cards, decorative callouts, marketing-speak, and invented report layouts. Zero exceptions.

## Testing & Build

- **Unit tests**: `./parity/.venv/bin/python3 -m unittest discover -s parity -p "test_*.py"`
- **Compiler Parity Gates**: `for f in check_lex.py check_parse.py check_validate.py check_graph.py; do NM_REFERENCE_ROOT=/path/to/noisemaker ./parity/.venv/bin/python3 "parity/compiler/$f"; done`
- **Definitions conversion**: `NM_REFERENCE_ROOT=/path/to/noisemaker node tools/convert-definitions.mjs`
