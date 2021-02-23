# based on https://github.com/adamtornhill/maat-scripts/blob/master/miner/complexity_calculations.py
import itertools
import os
import re
from typing import Optional

import numpy
import pygount
from pygount import SourceAnalysis, SourceState
from pygount.analysis import has_lexer, guess_lexer, matching_number_line_and_regex, _log, _line_parts, \
    DEFAULT_GENERATED_PATTERNS_TEXT, DuplicatePool

leading_tabs_expr =  re.compile(r'^(\t+)')
leading_spaces_expr = re.compile(r'^( +)')
empty_line_expr = re.compile(r'^\s*$')
tab_pattern = re.compile(r'\t+')
space_pattern = re.compile(r' +')


def n_log_tabs(line):
    wo_spaces = re.sub(space_pattern, '', line)
    m = leading_tabs_expr.search(wo_spaces)
    if m:
        tabs = m.group()
        return len(tabs)
    return 0


def n_log_spaces(line):
    wo_tabs = re.sub(tab_pattern, '', line)
    m = leading_spaces_expr.search(wo_tabs)
    if m:
        spaces = m.group()
        return len(spaces)
    return 0


def complexity_of(line):
    return n_log_tabs(line) + (n_log_spaces(line) / 4) # hardcoded indentation


class CodiceSourceAnalysis(SourceAnalysis):
    def __init__(
        self,
        path: str,
        language: str,
        group: str,
        code: int,
        documentation: int,
        empty: int,
        string: int,
        state: SourceState,
        state_info: Optional[str] = None,
        lc: int = 0,
        lines: int = 0,
    ):
        super().__init__(path, language, group, code, documentation, empty, string, state, state_info)
        self.lc = lc
        self.lines = lines
        SourceAnalysis._check_state_info(state, state_info)
        self._path = path
        self._language = language
        self._group = group
        self._code = code
        self._documentation = documentation
        self._empty = empty
        self._string = string
        self._state = state
        self._state_info = state_info

    @staticmethod
    def codice_from_file(
            source_path: str,
            group: str,
            encoding: str,
            fallback_encoding: str,
    ) -> "CodiceSourceAnalysis":
        """
        BEWARE
        specialized version assumes source_path is not binary
        """
        assert encoding is not None
        assert generated_regexes is not None

        result = None
        lexer = None
        source_code = None
        source_size = os.path.getsize(source_path)
        if source_size == 0:
            result = CodiceSourceAnalysis.from_state(source_path, group, SourceState.empty)
        elif not has_lexer(source_path):
            result = CodiceSourceAnalysis.from_state(source_path, group, SourceState.unknown)

        if result is None:
            try:
                with open(source_path, "r", encoding=encoding) as source_file:
                    source_code = source_file.read()
            except (LookupError, OSError, UnicodeError) as error:
                _log.warning("cannot read %s using encoding %s: %s", source_path, encoding, error)
                result = CodiceSourceAnalysis.from_state(source_path, group, SourceState.error, error)
            if result is None:
                lexer = guess_lexer(source_path, source_code)
                assert lexer is not None
        lc = 0
        ln = 0
        if result is None:
            assert lexer is not None
            assert source_code is not None
            language = lexer.name
            if ("xml" in language.lower()) or (language == "Genshi"):
                dialect = pygount.xmldialect.xml_dialect(source_path, source_code)
                if dialect is not None:
                    language = dialect
            mark_to_count_map = {"c": 0, "d": 0, "e": 0, "s": 0}
            for line_parts in _line_parts(lexer, source_code):
                mark_to_increment = "e"
                for mark_to_check in ("d", "s", "c"):
                    if mark_to_check in line_parts:
                        mark_to_increment = mark_to_check
                mark_to_count_map[mark_to_increment] += 1
            result = CodiceSourceAnalysis(
                path=source_path,
                language=language,
                group=group,
                code=mark_to_count_map["c"],
                documentation=mark_to_count_map["d"],
                empty=mark_to_count_map["e"],
                string=mark_to_count_map["s"],
                state=SourceState.analyzed,
                state_info=None,
                lc=lc,
                lines=ln
            )

        assert result is not None
        return result

    @staticmethod
    def from_state(
            source_path: str, group: str, state: SourceState, state_info: Optional[str] = None
    ) -> "CodiceSourceAnalysis":
        assert source_path is not None
        assert group is not None
        assert state != SourceState.analyzed, "use from() for analyzable sources"
        SourceAnalysis._check_state_info(state, state_info)
        return CodiceSourceAnalysis(
            path=source_path,
            language="__{0}__".format(state.name),
            group=group,
            code=0,
            documentation=0,
            empty=0,
            string=0,
            state=state,
            state_info=state_info,
        )


def source_analysis(source, group, encoding):
    analysis = CodiceSourceAnalysis.codice_from_file(source, group, encoding='utf-8', fallback_encoding=encoding)
    return analysis


