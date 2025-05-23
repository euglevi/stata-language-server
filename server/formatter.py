import re

class StataFormatter:
    def __init__(self, max_line_length=72, indent_size=4):
        self.max_line_length = max_line_length
        self.indent_size = indent_size

    def format_code(self, code: str) -> str:
        """Format Stata code according to style rules."""
        lines = code.split("\n")
        lines_reordered, comments_reordered = self._reorder_lines(lines)
        formatted_lines = self._process_lines(lines_reordered, comments_reordered)
        formatted_lines_indented = self._apply_indentation(formatted_lines)
        return "\n".join(formatted_lines_indented)

    def _reorder_lines(self, lines: list[str]) -> tuple[list[str], list[str]]:
        """Reorder lines to handle `///` continuations and comments."""
        lines_reordered = []
        comments_reordered = []

        for line in lines:
            if lines_reordered:
                if "///" in lines_reordered[-1] and not re.match(
                    r"^\*\s", lines_reordered[-1]
                ):
                    comments_reordered[-1] += (
                        lines_reordered[-1].split("///", 1)[1].strip()
                    )
                    lines_reordered[-1] = (
                        lines_reordered[-1].split("///", 1)[0].strip()
                        + " "
                        + line.strip()
                    )
                else:
                    lines_reordered.append(line)
                    comments_reordered.append("")
            else:
                lines_reordered.append(line)
                comments_reordered.append("")

        return lines_reordered, comments_reordered

    def _process_lines(self, lines: list[str], comments: list[str]) -> list[str]:
        """Process and format lines, handling long lines and comments."""
        formatted_lines = []

        for line, comment in zip(lines, comments):
            stripped = line.strip()
            if not stripped:
                formatted_lines.append(comment)
                continue

            formatted = self._format_line(stripped)
            broken_lines = self._break_long_line(formatted, comment)
            formatted_lines.extend(broken_lines)

        return formatted_lines

    def _apply_indentation(self, lines: list[str]) -> list[str]:
        """Apply indentation rules to formatted lines."""
        formatted_lines_indented = []
        open_parenthesis = 0

        for i, line in enumerate(lines):
            if (i > 0) and (
                "{" in formatted_lines_indented[i - 1]
                and "}" not in formatted_lines_indented[i - 1]
            ):
                open_parenthesis += 1
                line = " " * open_parenthesis * self.indent_size + line
            elif (i > 0) and (open_parenthesis > 0) and ("}" not in line):
                line = " " * open_parenthesis * self.indent_size + line
            elif (i > 0) and ("}" in line) and ("{" not in line):
                open_parenthesis -= 1
                line = " " * open_parenthesis * self.indent_size + line

            if (
                (i > 0)
                and ("///" in formatted_lines_indented[i - 1])
                and not re.match(r"^\*\s", line)
            ):
                line = " " * self.indent_size + line

            formatted_lines_indented.append(line)

        return formatted_lines_indented

    def _format_line(self, line: str) -> str:
        """Format a single line of Stata code."""

        # Format commas (space after, not before)
        line = re.sub(r"\s*,\s*", ", ", line)

        # Format operators with spaces around them
        line = re.sub(r"\s*(==|!=|~=|>=|<=|\|\||>|<|=|&|\|)\s*", r" \1 ", line)
        # line = re.sub(r"(?<![=!])\s*([=|&])(?![=!])\s*", r" \1 ", line)

        # Fix double spaces
        line = re.sub(r"\s{2,}", " ", line)

        return line.strip()

    def _break_long_line(self, line: str, comment: str) -> list[str]:
        """Break long lines at logical points, adding /// for continuation."""
        parts = line.split("//", 1)
        remaining = parts[0]
        remaining_comment = (
            " //" + comment + parts[1]
            if len(parts) > 1
            else " // " + comment
            if comment
            else ""
        )

        if len(remaining) <= self.max_line_length or re.search(r"^\*\s", remaining):
            return [remaining + remaining_comment]

        result_lines = []

        while len(remaining) > self.max_line_length + 4:
            # Try breaking at logical points first (brackets, commas, operators)
            break_result = self._try_logical_break(remaining)
            if break_result:
                segment, remaining = break_result
                result_lines.append(segment)
                continue

            # If no logical break works, try breaking at spaces
            break_result = self._try_space_break(remaining)
            if break_result:
                segment, remaining = break_result
                result_lines.append(segment)
                continue

            # If no valid break point is found, add the entire line
            result_lines.append(remaining.strip() + remaining_comment)
            remaining = ""

        if remaining:
            result_lines.append(remaining.strip() + remaining_comment)

        return result_lines

    def _find_break_points(self, text: str, max_length: int) -> list[int]:
        """Find potential break points in text within max_length."""
        break_points = []

        # After closing brackets or parentheses
        for match in re.finditer(r"[)\]][,|\s]", text[:max_length]):
            break_points.append(match.end())

        # After commas
        for match in re.finditer(r",", text[:max_length]):
            break_points.append(match.end())

        # After logical operators
        for match in re.finditer(r"\s(&|\||/|:)\s", text[:max_length]):
            break_points.append(match.end())

        # Sort break points from furthest to nearest
        break_points.sort(reverse=True)
        return break_points

    def _find_space_break_points(self, text: str, max_length: int) -> list[int]:
        """Find space-based break points in text within max_length."""
        space_break_points = []
        for match in re.finditer(r"\s", text[: max_length - 3]):
            space_break_points.append(match.end())

        # Sort break points from furthest to nearest
        space_break_points.sort(reverse=True)
        return space_break_points

    def _is_valid_break_point(self, segment: str) -> bool:
        """Check if a segment can be safely broken at this point."""
        open_curly_count = segment.count("{") - segment.count("}")
        open_quote_count = segment.count('"') % 2
        open_backtick_count = segment.count("`")
        close_quote_count = segment.count("'")

        # Valid break only if all delimiters are properly closed
        return (
            open_curly_count <= 0
            and open_quote_count == 0
            and open_backtick_count <= close_quote_count
        )

    def _try_logical_break(
        self,
        text: str,
    ) -> tuple[str, str] | None:
        """Try to break text at logical break points."""
        break_points = self._find_break_points(text, self.max_line_length)

        for break_pos in break_points:
            segment = text[:break_pos]
            if self._is_valid_break_point(segment):
                # Valid break point found
                return segment.strip() + " ///", text[break_pos:]

        return None

    def _try_space_break(
        self,
        text: str,
    ) -> tuple[str, str] | None:
        """Try to break text at spaces."""
        space_break_points = self._find_space_break_points(text, self.max_line_length)

        for break_pos in space_break_points:
            segment = text[:break_pos]
            if self._is_valid_break_point(segment):
                # Valid break point found
                return segment.strip() + " ///", text[break_pos:]

        return None

def format_stata_code(
    code: str, max_line_length: int = 72, indent_size: int = 4
) -> str:
    """Format Stata code according to style rules."""
    formatter = StataFormatter(max_line_length=max_line_length, indent_size=indent_size)
    return formatter.format_code(code)
