# Quantum Computing as an Emerging Electricity Load in Finland: Scenarios to 2050

- `paper/` – LaTeX source (arXiv-ready: `main.tex`, `main.bbl`, `references.bib`, `figures/`). Build: `latexmk -pdf main.tex`
- `data/inputs/` – original 2030/2035 parameter and results files from Merilehto (2026), Zenodo 10.5281/zenodo.21966116 (unchanged)
- `model/model.py` – reads the original inputs, asserts it reproduces the original 2030/2035 results exactly, then constructs 2035–2050 paths and robustness outputs into `data/*.csv`
- `model/figures.py` – regenerates the figures into `paper/figures/`

Run (conda/PowerShell): `python model\model.py; python model\figures.py`
