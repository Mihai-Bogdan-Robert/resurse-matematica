#!/usr/bin/env python3
"""Build every topic of the collection in Romanian, English and German.

    python3 build.py              # everything (individual PDFs + one book per language)
    python3 build.py matrice      # only topics whose id contains "matrice"
    python3 build.py --lang en    # only one language

Requires XeLaTeX (TeX Live / MacTeX) and `pdfunite` (poppler) for the books.
The LaTeX sources live in src/, the results are written to pdf/<lang>/.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
LANGS = ["ro", "en", "de"]

# chapter folder (= folder in src/) -> {lang: output folder}
CHAPTERS = {
    "01_Algebra":      {"ro": "01_Algebra",      "en": "01_Algebra",      "de": "01_Algebra"},
    "02_Functii":      {"ro": "02_Functii",      "en": "02_Functions",    "de": "02_Funktionen"},
    "03_Analiza":      {"ro": "03_Analiza",      "en": "03_Calculus",     "de": "03_Analysis"},
    "04_Geometrie":    {"ro": "04_Geometrie",    "en": "04_Geometry",     "de": "04_Geometrie"},
    "05_Combinatorica": {"ro": "05_Combinatorica", "en": "05_Combinatorics", "de": "05_Kombinatorik"},
}

# (chapter, source id, {lang: PDF file name without extension})
TOPICS = [
    ("01_Algebra", "matrice", {"ro": "Matrice", "en": "Matrices", "de": "Matrizen"}),
    ("01_Algebra", "modulul", {"ro": "Modulul", "en": "Absolute_value", "de": "Betrag"}),
    ("01_Algebra", "numere_complexe", {"ro": "Numere_complexe", "en": "Complex_numbers", "de": "Komplexe_Zahlen"}),
    ("01_Algebra", "progresii", {"ro": "Progresii", "en": "Progressions", "de": "Folgen_und_Reihen"}),
    ("01_Algebra", "sisteme_ecuatii_in_zn", {"ro": "Sisteme_ecuatii_in_Zn", "en": "Systems_of_equations_in_Zn", "de": "Gleichungssysteme_in_Zn"}),
    ("02_Functii", "compunerea_functiilor", {"ro": "Compunerea_functiilor", "en": "Function_composition", "de": "Verkettung_von_Funktionen"}),
    ("02_Functii", "functia_de_gradul_doi", {"ro": "Functia_de_gradul_doi", "en": "Quadratic_function", "de": "Quadratische_Funktion"}),
    ("02_Functii", "functii_surjective_injective", {"ro": "Functii_surjective_injective", "en": "Injective_and_surjective_functions", "de": "Injektive_und_surjektive_Funktionen"}),
    ("02_Functii", "legi_de_compozitie", {"ro": "Legi_de_compozitie", "en": "Binary_operations", "de": "Verknuepfungen"}),
    ("03_Analiza", "asimptote", {"ro": "Asimptote", "en": "Asymptotes", "de": "Asymptoten"}),
    ("03_Analiza", "derivare", {"ro": "Derivare", "en": "Derivatives", "de": "Ableitungen"}),
    ("03_Analiza", "ecuatii_exponentiale", {"ro": "Ecuatii_exponentiale", "en": "Exponential_equations", "de": "Exponentialgleichungen"}),
    ("03_Analiza", "ecuatii_irationale", {"ro": "Ecuatii_irationale", "en": "Irrational_equations", "de": "Wurzelgleichungen"}),
    ("03_Analiza", "ecuatii_logaritmice", {"ro": "Ecuatii_logaritmice", "en": "Logarithmic_equations", "de": "Logarithmusgleichungen"}),
    ("03_Analiza", "ecuatii_trigonometrice", {"ro": "Ecuatii_trigonometrice", "en": "Trigonometric_equations", "de": "Trigonometrische_Gleichungen"}),
    ("03_Analiza", "integrare", {"ro": "Integrare", "en": "Integration", "de": "Integration"}),
    ("03_Analiza", "limite", {"ro": "Limite", "en": "Limits", "de": "Grenzwerte"}),
    ("04_Geometrie", "drepte_in_plan", {"ro": "Drepte_in_plan", "en": "Lines_in_the_plane", "de": "Geraden_in_der_Ebene"}),
    ("04_Geometrie", "parte_intreaga", {"ro": "Parte_intreaga", "en": "Floor_and_fractional_part", "de": "Gaussklammer"}),
    ("04_Geometrie", "vectori_in_plan", {"ro": "Vectori_in_plan", "en": "Vectors_in_the_plane", "de": "Vektoren_in_der_Ebene"}),
    ("05_Combinatorica", "combinatorica", {"ro": "Combinatorica", "en": "Combinatorics", "de": "Kombinatorik"}),
    ("05_Combinatorica", "inductie", {"ro": "Inductie", "en": "Mathematical_induction", "de": "Vollstaendige_Induktion"}),
]

BOOK_NAME = {"ro": "Resurse_Matematica", "en": "Math_Resources", "de": "Mathe_Formelsammlung"}
BOOK_TITLE = {
    "ro": "Resurse de matematică",
    "en": "Mathematics resources",
    "de": "Mathematik-Formelsammlung",
}
BOOK_SUB = {
    "ro": "Formule și metode pentru liceu (programa din România)",
    "en": "Formulas and methods for Romanian high-school mathematics",
    "de": "Formeln und Methoden für die rumänische Oberstufe",
}
CHAPTER_TITLE = {
    "01_Algebra": {"ro": "Algebră", "en": "Algebra", "de": "Algebra"},
    "02_Functii": {"ro": "Funcții", "en": "Functions", "de": "Funktionen"},
    "03_Analiza": {"ro": "Analiză matematică", "en": "Calculus and analysis", "de": "Analysis"},
    "04_Geometrie": {"ro": "Geometrie", "en": "Geometry", "de": "Geometrie"},
    "05_Combinatorica": {"ro": "Combinatorică", "en": "Combinatorics", "de": "Kombinatorik"},
}


def run_xelatex(tex_source: str, jobname: str, workdir: pathlib.Path) -> pathlib.Path:
    """Compile `tex_source` (a full .tex string) twice; return the PDF path."""
    workdir.mkdir(parents=True, exist_ok=True)
    tex = workdir / f"{jobname}.tex"
    tex.write_text(tex_source, encoding="utf-8")
    env_tex = f"{ROOT}:"  # so that \input{common/...} resolves
    for _ in range(2):
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
             f"-output-directory={workdir}", str(tex)],
            cwd=ROOT, capture_output=True, text=True,
            env={**__import__("os").environ, "TEXINPUTS": env_tex},
        )
        if proc.returncode != 0:
            log = workdir / f"{jobname}.log"
            tail = log.read_text(errors="replace")[-2500:] if log.exists() else proc.stdout[-2500:]
            raise RuntimeError(f"xelatex failed for {jobname}:\n{tail}")
    log = (workdir / f"{jobname}.log").read_text(errors="replace")
    for line in log.splitlines():
        if line.startswith("Missing character") or "Undefined control sequence" in line:
            print(f"[warn] {jobname}: {line.strip()}")
    return workdir / f"{jobname}.pdf"


def topic_source(lang: str, chapter: str, tid: str) -> str:
    return (
        "\\documentclass[10.5pt,a4paper]{article}\n"
        f"\\def\\lang{{{lang}}}\n"
        "\\input{common/preamble}\n"
        "\\begin{document}\n"
        f"\\input{{src/{chapter}/{tid}}}\n"
        "\\end{document}\n"
    )


def build_topics(langs, pattern):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            for chapter, tid, names in TOPICS:
                if pattern and pattern not in tid:
                    continue
                if not (ROOT / "src" / chapter / f"{tid}.tex").exists():
                    print(f"[skip] {lang}/{tid}: no source yet")
                    continue
                pdf = run_xelatex(topic_source(lang, chapter, tid), f"{lang}_{tid}", pathlib.Path(tmp) / lang)
                dest_dir = ROOT / "pdf" / lang / CHAPTERS[chapter][lang]
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"{names[lang]}.pdf"
                shutil.copyfile(pdf, dest)
                print(f"[ok]   {dest.relative_to(ROOT)}")
                out.append(dest)
    return out


def book_source(lang: str) -> str:
    parts = [
        "\\documentclass[10.5pt,a4paper]{article}\n",
        f"\\def\\lang{{{lang}}}\n",
        "\\input{common/preamble}\n",
        # In the book every topic becomes one entry of the table of contents; the headings
        # inside a topic move one level down and are not listed.
        "\\let\\origsection\\section\n",
        "\\setcounter{tocdepth}{2}\n",
        "\\begin{document}\n",
        "\\begin{titlepage}\\centering\\vspace*{5cm}\n",
        f"{{\\Huge\\bfseries\\color{{accent}} {BOOK_TITLE[lang]}}}\\par\\vspace{{1cm}}\n",
        f"{{\\Large {BOOK_SUB[lang]}}}\\par\\vspace{{2cm}}\n",
        "\\includegraphics[width=4cm]{Image.png}\\par\\vfill\n",
        "{\\small \\textcopyright{} 2025 Bogdan Mihai Robert\\\\\n",
        "\\href{https://creativecommons.org/licenses/by-nc-nd/4.0/}{CC BY-NC-ND 4.0}}\n",
        "\\end{titlepage}\n",
        "\\tableofcontents\n",
        "\\renewcommand{\\topictitle}[1]{\\clearpage\\origsection*{#1}\\addcontentsline{toc}{subsection}{#1}}\n",
        "\\renewcommand{\\section}[1]{\\subsection*{#1}}\n",
        "\\renewcommand{\\subsection}[1]{\\subsubsection*{#1}}\n",
        "\\renewcommand{\\subsubsection}[1]{\\par\\medskip\\noindent\\textbf{\\itshape #1}\\par\\nobreak}\n",
    ]
    last = None
    for chapter, tid, _ in TOPICS:
        if not (ROOT / "src" / chapter / f"{tid}.tex").exists():
            continue
        if chapter != last:
            title = CHAPTER_TITLE[chapter][lang]
            parts.append(
                f"\\clearpage\\thispagestyle{{empty}}\\addcontentsline{{toc}}{{section}}{{{title}}}"
                f"\\vspace*{{\\fill}}\\begin{{center}}{{\\Huge\\bfseries\\color{{accent}} {title}}}\\end{{center}}"
                f"\\vspace*{{\\fill}}\\clearpage\n"
            )
            last = chapter
        parts.append(f"\\input{{src/{chapter}/{tid}}}\n")
    parts.append("\\end{document}\n")
    return "".join(parts)


def build_books(langs):
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            pdf = run_xelatex(book_source(lang), f"book_{lang}", pathlib.Path(tmp) / lang)
            dest = ROOT / "pdf" / lang / f"{BOOK_NAME[lang]}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, dest)
            print(f"[ok]   {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", nargs="?", help="build only topics whose id contains this text")
    ap.add_argument("--lang", choices=LANGS, action="append", help="language(s); default: all")
    ap.add_argument("--no-book", action="store_true", help="skip the combined book")
    args = ap.parse_args()
    langs = args.lang or LANGS
    if shutil.which("xelatex") is None:
        sys.exit("xelatex not found - install TeX Live / MacTeX")
    build_topics(langs, args.pattern)
    if not args.pattern and not args.no_book:
        build_books(langs)
