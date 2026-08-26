"""Tables the model miscounted, caught before the engine sees them.

A tabular declares its columns once and every row has to agree. A model writing
one from a prompt loses count, and TeX answers with "! Extra alignment tab has
been changed to \\cr" -- which names a line and nothing a person who did not
write LaTeX can act on. A tester on Windows hit exactly that.

These are REPORTED, never repaired: padding a short row puts empty cells into a
table the author believes is finished, and truncating a long one deletes their
data.
"""

from __future__ import annotations

import pytest

from domain.paper_writer.compiler import _cells_in_row, _check_tables, _count_columns


class TestCountingColumns:
    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("lcr", 3),
            ("|l|c|r|", 3),                     # rules are not columns
            ("l@{ }c", 2),                      # @{} is material between them
            ("l!{\\vrule}c", 2),
            ("p{3cm}l", 2),                     # a width argument is not columns
            ("m{2cm}b{2cm}", 2),
            ("*{4}{c}", 4),                     # repeated
            ("*{2}{lc}", 4),
            (">{\\bfseries}lc", 2),             # >{} is a per-column prefix
            ("lS[table-format=2.1]", 2),        # siunitx carries an option
            ("X", 1),                           # tabularx
        ],
    )
    def test_a_specification_is_counted_as_tex_would(self, spec, expected):
        assert _count_columns(spec) == expected


class TestCountingCells:
    @pytest.mark.parametrize(
        "row,expected",
        [
            ("a & b & c", 3),
            ("only", 1),
            (r"R\&D & sales", 2),               # an escaped & is text, not a break
            (r"\multicolumn{3}{c}{wide} & last", 4),
            (r"\multicolumn{2}{c}{a} & \multicolumn{2}{c}{b}", 4),
            ("a & b % & c", 2),                 # a comment cannot hold a cell
        ],
    )
    def test_only_separators_count(self, row, expected):
        assert _cells_in_row(row) == expected


class TestTheCheck:
    def test_the_failure_a_tester_actually_hit(self):
        src = (
            "\\begin{tabular}{lcc}\n\\toprule\n"
            "Model & Novelty & Pass \\\\\n\\midrule\n"
            "GA & -12.080 & 0.864 & & & & \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        problems = _check_tables(src)
        assert len(problems) == 1
        assert "7 cells" in problems[0] and "3 column" in problems[0]

    def test_it_names_the_line_the_reader_will_look_at(self):
        src = (
            "line one\nline two\n"
            "\\begin{tabular}{lc}\n\\toprule\n"
            "A & B \\\\\n\\midrule\n"
            "x & y & z \\\\\n\\end{tabular}\n"
        )
        problems = _check_tables(src)
        line = int(problems[0].split("line ")[1].split()[0])
        assert src.splitlines()[line - 1].startswith("x & y & z")

    def test_a_correct_table_says_nothing(self):
        src = (
            "\\begin{tabular}{lcc}\n\\toprule\nA & B & C \\\\\n"
            "\\midrule\n1 & 2 & 3 \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        assert _check_tables(src) == []

    def test_a_short_row_is_allowed(self):
        """TeX fills missing cells silently; only an EXTRA one is an error."""
        src = "\\begin{tabular}{lcc}\nA & B \\\\\n\\end{tabular}\n"
        assert _check_tables(src) == []

    def test_rules_are_not_rows(self):
        src = (
            "\\begin{tabular}{lc}\n\\toprule\nA & B \\\\\n"
            "\\cmidrule(lr){1-2}\n1 & 2 \\\\\n\\bottomrule\n\\end{tabular}\n"
        )
        assert _check_tables(src) == []

    def test_longtable_and_array_are_checked_too(self):
        for env in ("longtable", "array"):
            src = f"\\begin{{{env}}}{{lc}}\na & b & c \\\\\n\\end{{{env}}}\n"
            assert _check_tables(src), f"{env} was not checked"

    def test_several_tables_are_each_checked(self):
        src = (
            "\\begin{tabular}{lc}\na & b & c \\\\\n\\end{tabular}\n"
            "text\n"
            "\\begin{tabular}{lcc}\n1 & 2 & 3 \\\\\n\\end{tabular}\n"
            "\\begin{tabular}{l}\nx & y \\\\\n\\end{tabular}\n"
        )
        assert len(_check_tables(src)) == 2      # the middle one is fine

    def test_a_document_with_no_tables_is_not_a_problem(self):
        assert _check_tables("\\documentclass{article}\nhello\n") == []
