import re
from typing import List, Optional

from lsprotocol.types import (
    CompletionList,
    CompletionParams,
    ConfigurationItem,
    ConfigurationParams,
    DefinitionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeConfigurationParams,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DocumentFormattingParams,
    Hover,
    HoverParams,
    Location,
    MessageType,
    Position,
    Range,
    TextEdit,
)
from pygls.server import LanguageServer

import server.constants as constants
import server.utils as utils

from .formatter import format_stata_code

# from server.constants import (MAX_LINE_LENGTH_MESSAGE, OPERATOR_REGEX, STRING, STAR_COMMENTS,
#                              WHITESPACE_AFTER_COMMA_REGEX, BLOCK_COMMENTS_BG,
#                              BLOCK_COMMENTS_END, INLINE_COMM_RE, LOOP_START, LOOP_END, INDENT_REGEX,
#                              OP_WHITESPACE_MESSAGE, COMMA_WHITESPACE_MESSAGE, INAP_INDENT_MESSAGE,
#                              MAX_LINE_LENGTH_SEVERITY, MAX_LINE_LENGTH, INDENT_SPACE,
#                              OP_WHITESPACE_SEVERITY, COMMA_WHITESPACE_SEVERITY, INAP_INDENT_SEVERITY,
#                              ENABLECOMPLETION, ENABLEDOCSTRING, ENABLESTYLECHECKING)


class StataLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = "stata"

    def __init__(self):
        super().__init__("stata-language-server", "v0.1.0")


stata_server = StataLanguageServer()
comlist = utils.getComList()


@stata_server.feature("textDocument/didChange")
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if constants.ENABLESTYLECHECKING:
        refresh_diagnostics(ls, params)


@stata_server.feature("textDocument/didClose")
def did_close(ls: StataLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    ls.show_message_log("Stata File Did Close")
    clear_diagnostics(ls, params)


@stata_server.feature("textDocument/didOpen")
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message_log("Stata File Did Open")
    if constants.ENABLESTYLECHECKING:
        refresh_diagnostics(ls, params)


@stata_server.feature("textDocument/completion")
def completions(
    ls: StataLanguageServer, params: CompletionParams
) -> CompletionList | None:
    """Return completion items."""
    if not constants.ENABLECOMPLETION:
        return None
    return comlist


@stata_server.feature("textDocument/hover")
def hover(ls: StataLanguageServer, params: HoverParams) -> Optional[Hover]:
    """Display Markdown documentation for the element under the cursor."""
    if constants.ENABLEDOCSTRING:
        document = ls.workspace.get_document(params.text_document.uri)
        word = document.word_at_position(
            params.position
        )  # return start and end positions
        docstring = utils.getDocstringFromWord(word)
        return Hover(contents=docstring)
    else:
        return None


@stata_server.feature("textDocument/definition")
def goto_definition(ls, params: DefinitionParams):
    """
    Go to the last definition of a var: g(enerate) varname
    """
    uri = params.text_document.uri
    document = ls.workspace.get_document(uri)
    origin_pos = params.position  # start from 1
    origin_line = origin_pos.line  # start from 0
    origin_varname = document.word_at_position(origin_pos)
    lenOrigin = len(origin_varname)
    genPattern = "\\b(g(enerate|enerat|enera|ener|ene|en|e)?|egen)\\s+((byte|int|long|float|double|str[1-9]?[0-9]?[0-9]?[0-9]?|strL)\\s+)?([^=\\s]+)\\s*((==)|(=))"

    if origin_line > 0:
        searched_area = document.lines
        for i in range(origin_pos.line - 1, -1, -1):
            matchObj = re.match(genPattern, searched_area[i])
            if matchObj and matchObj.group(5) == origin_varname:
                targetLine = i
                targetStChar = searched_area[i].find(origin_varname)
                targetEndChar = targetStChar + lenOrigin
                target_range = Range(
                    start=Position(line=targetLine, character=targetStChar),
                    end=Position(line=targetLine, character=targetEndChar),
                )
                return Location(uri=uri, range=target_range)
    return None


def create_diagnostic(
    line: int,
    stIndex: int,
    enIndex: int,
    msg: str,
    severity: DiagnosticSeverity,
) -> Diagnostic:
    """Create a Diagnostic"""
    range = Range(
        start=Position(line=line, character=stIndex),
        end=Position(line=line, character=enIndex),
    )
    diag = Diagnostic(range=range, message=msg, severity=severity)
    return diag


def inSkipTokens(start: int, end: int, skip_tokens: List[List[int]]) -> bool:
    """
    Check if start and end index(python) is in one of skip tokens
    """
    for token in skip_tokens:
        if start >= token[0] and end <= token[1]:
            return True
    return False


def refresh_diagnostics(ls: StataLanguageServer, params):
    """
    Codestyle checking and publish diagnostics.
    """
    uri = ls.workspace.get_document(params.text_document.uri).uri
    doc = ls.workspace.get_document(uri)
    diagnostics = []

    LINE_STATE = {
        "isInComm": False,
        "loopLevel": 0,
        "prevComm": 0,
    }  # cross line state
    for lineno, line in enumerate(doc.lines):
        # Max line length
        remaining = line.split("//")[0]
        if (
            len(remaining) > constants.MAX_LINE_LENGTH
            and not re.findall(r"^\s*\*\s", remaining)
            and not remaining.startswith("// ")
            and not remaining.startswith("/* ")
            and not remaining.startswith("*/ ")
        ):
            diagnostics.append(
                create_diagnostic(
                    lineno,
                    constants.MAX_LINE_LENGTH,
                    constants.MAX_LINE_LENGTH,
                    constants.MAX_LINE_LENGTH_MESSAGE,
                    constants.MAX_LINE_LENGTH_SEVERITY,
                )
            )
        skip_tokens = []

        # Comment block
        if LINE_STATE["isInComm"] is False:
            match = re.match(constants.BLOCK_COMMENTS_BG, line)
            if match is None:
                pass
            elif match.group(1) == "":
                LINE_STATE["isInComm"] = True
                continue
            else:
                LINE_STATE["isInComm"] = True
                start, end = match.start(1), match.end(1)  # python index
                skip_tokens.append([start, end])
        else:
            match = re.match(constants.BLOCK_COMMENTS_END, line)
            if match is None:
                continue
            elif match.group(1) == "":
                LINE_STATE["isInComm"] = False
                continue
            else:
                LINE_STATE["isInComm"] = False
                start, end = match.start(1), match.end(1)
                skip_tokens.append([start, end])

        # Star Comments
        if re.match(constants.STAR_COMMENTS, line):
            continue

        # Inline Comment
        match = re.match(constants.INLINE_COMM_RE, line)
        if match and match.group(1) != "":
            start, end = match.start(1), match.end(1)
            skip_tokens.append([start, end])

        # STRING
        for match in constants.STRING.finditer(line):
            start, end = match.span()
            if not inSkipTokens(start, end, skip_tokens):
                skip_tokens.append([start, end])

        # Operator Checker
        for match in constants.OPERATOR_REGEX.finditer(line):
            for sindex in range(1, 3):
                start, end = match.start(sindex), match.end(sindex)
                if not inSkipTokens(start, end, skip_tokens):
                    if end - start != 1:
                        diagnostics.append(
                            create_diagnostic(
                                lineno,
                                end,
                                end,
                                constants.OP_WHITESPACE_MESSAGE,
                                constants.OP_WHITESPACE_SEVERITY,
                            )
                        )

        # Comma Checker
        for match in constants.WHITESPACE_AFTER_COMMA_REGEX.finditer(line):
            start, end = match.start(1), match.end(1)
            if not inSkipTokens(start, end, skip_tokens):
                if end - start != 1:
                    diagnostics.append(
                        create_diagnostic(
                            lineno,
                            end,
                            end,
                            constants.COMMA_WHITESPACE_MESSAGE,
                            constants.COMMA_WHITESPACE_SEVERITY,
                        )
                    )

        # Combined Indent Checker for both Comments and Loops
        # First, adjust indentation levels based on closing structures
        if re.match(constants.LOOP_END, line) and LINE_STATE["loopLevel"] > 0:
            LINE_STATE["loopLevel"] -= 1

        # Check indentation against the combined requirements
        match = re.match(constants.INDENT_REGEX, line)
        if match:
            start, end = match.start(1), match.end(1)
            actual_space = end - start
            expected_space = (
                LINE_STATE["loopLevel"] + LINE_STATE["prevComm"]
            ) * constants.INDENT_SPACE

            if actual_space != expected_space:
                diagnostics.append(
                    create_diagnostic(
                        lineno,
                        end,
                        end,
                        f"{constants.INAP_INDENT_MESSAGE} (expected {expected_space} spaces)",
                        constants.INAP_INDENT_SEVERITY,
                    )
                )

        # Adjust indentation levels based on opening structures
        if re.match(constants.LOOP_START, line):
            LINE_STATE["loopLevel"] += 1

        # Handle comment indentation state - check current line before adjusting for next line
        has_long_comment = re.search(constants.INLINE_COMM_LONG, line) is not None

        if LINE_STATE["prevComm"] > 0 and not has_long_comment:
            LINE_STATE["prevComm"] -= 1

        if has_long_comment:
            LINE_STATE["prevComm"] = 1

    ls.publish_diagnostics(uri=uri, diagnostics=diagnostics)


def clear_diagnostics(ls: StataLanguageServer, params):
    """Clear diagnostics."""
    uri = ls.workspace.get_document(params.text_document.uri).uri
    ls.publish_diagnostics(uri=uri, diagnostics=[])


@stata_server.feature("workspace/didChangeConfiguration")
async def refresh_config(ls: StataLanguageServer, params: DidChangeConfigurationParams):
    """Handle configuration changes from the client."""
    try:
        config_item = ConfigurationItem(section="stata")
        config = await ls.get_configuration_async(
            ConfigurationParams(items=[config_item])
        )
        if config:
            settings = config[0]
            global \
                MAX_LINE_LENGTH, \
                INDENT_SPACE, \
                ENABLECOMPLETION, \
                ENABLEDOCSTRING, \
                ENABLESTYLECHECKING
            constants.MAX_LINE_LENGTH = int(settings.get("setMaxLineLength", 80))
            constants.INDENT_SPACE = int(settings.get("setIndentSpace", 4))
            constants.ENABLECOMPLETION = bool(settings.get("enableCompletion", False))
            constants.ENABLEDOCSTRING = bool(settings.get("enableDocstring", True))
            constants.ENABLESTYLECHECKING = bool(
                settings.get("enableStyleChecking", True)
            )
            ls.show_message_log(f"Configuration applied: {settings}")
    except Exception as e:
        ls.show_message_log(f"Error applying configuration: {e}")


@stata_server.feature("textDocument/formatting")
def formatting(
    ls: StataLanguageServer, params: DocumentFormattingParams
) -> List[TextEdit]:
    """Format the entire document."""
    if not constants.ENABLEFORMATTING:
        return []
    else:
        ls.show_message_log("Formatting Stata file")

        # Get the document
        document = ls.workspace.get_document(params.text_document.uri)
        text = document.source

        try:
            # Call your formatter on the document text
            formatted_text = format_stata_code(
                text,
                max_line_length=constants.FORMATTING_MAX_LINE_LENGTH,
                indent_size=constants.INDENT_SPACE,
            )

            # Create a TextEdit that replaces the entire document
            start_pos = Position(line=0, character=0)
            # Get the position at the end of the last line
            lines = document.lines
            end_line = len(lines) - 1
            end_character = len(lines[end_line]) if lines else 0
            end_pos = Position(line=end_line, character=end_character)

            text_range = Range(start=start_pos, end=end_pos)
            edit = TextEdit(range=text_range, new_text=formatted_text)

            return [edit]
        except Exception as e:
            ls.show_message(f"Error formatting document: {str(e)}", MessageType.Error)
            return []
