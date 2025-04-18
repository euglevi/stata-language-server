import server.utils as utils
from pygls.server import LanguageServer
from lsprotocol.types import (CompletionList, CompletionParams, Location, DefinitionParams,
                             Hover, HoverParams, Position, Range, Diagnostic,
                             DiagnosticSeverity, ConfigurationItem, ConfigurationParams, 
                             DidChangeTextDocumentParams, DidCloseTextDocumentParams, 
                             DidOpenTextDocumentParams, DidChangeConfigurationParams,
                             MessageType, TextDocumentSyncKind, NotebookDocumentSyncOptions)
from typing import Optional, List, Any, Dict
import re
from server.constants import (MAX_LINE_LENGTH_MESSAGE, OPERATOR_REGEX, STRING, STAR_COMMENTS,
                             WHITESPACE_AFTER_COMMA_REGEX, BLOCK_COMMENTS_BG,
                             BLOCK_COMMENTS_END, INLINE_COMM_RE, LOOP_START, LOOP_END, INDENT_REGEX,
                             OP_WHITESPACE_MESSAGE, COMMA_WHITESPACE_MESSAGE, INAP_INDENT_MESSAGE,
                             MAX_LINE_LENGTH_SEVERITY, MAX_LINE_LENGTH, INDENT_SPACE,
                             OP_WHITESPACE_SEVERITY, COMMA_WHITESPACE_SEVERITY, INAP_INDENT_SEVERITY,
                             ENABLECOMPLETION, ENABLEDOCSTRING, ENABLESTYLECHECKING)


class StataLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'stataServer'
    
    def __init__(self):
        super().__init__("stata-language-server", "v0.1.0")


stata_server = StataLanguageServer()
COMLIST = utils.getComList()


@stata_server.feature("textDocument/didChange")
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if ENABLESTYLECHECKING:
        refresh_diagnostics(ls, params)


@stata_server.feature("textDocument/didClose")
def did_close(ls: StataLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    ls.show_message_log('Stata File Did Close')
    clear_diagnostics(ls, params)


@stata_server.feature("textDocument/didOpen")
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message_log('Stata File Did Open')
    if ENABLESTYLECHECKING:
        refresh_diagnostics(ls, params)


@stata_server.feature("textDocument/completion")
def completions(ls: StataLanguageServer, params: Optional[CompletionParams] = None) -> Optional[CompletionList]:
    """Return completion items."""
    if ENABLECOMPLETION:
        return COMLIST
    else:
        return None


@stata_server.feature("textDocument/hover")
def hover(ls: StataLanguageServer, params: HoverParams) -> Optional[Hover]:
    """Display Markdown documentation for the element under the cursor."""
    if ENABLEDOCSTRING:
        document = ls.workspace.get_document(params.text_document.uri)
        word = document.word_at_position(params.position)  # return start and end positions
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
    genPattern = '\\b(g(enerate|enerat|enera|ener|ene|en|e)?|egen)\\s+((byte|int|long|float|double|str[1-9]?[0-9]?[0-9]?[0-9]?|strL)\\s+)?([^=\\s]+)\\s*((==)|(=))'

    if origin_line > 0:
        searched_area = document.lines
        for i in range(origin_pos.line - 1, -1, -1):
            matchObj = re.match(genPattern, searched_area[i])
            if matchObj and matchObj.group(5) == origin_varname:
                targetLine = i
                targetStChar = searched_area[i].find(origin_varname)
                targetEndChar = targetStChar + lenOrigin
                target_range = Range(start=Position(line=targetLine,
                                                    character=targetStChar),
                                     end=Position(line=targetLine, character=targetEndChar))
                return Location(uri=uri, range=target_range)
    return None


def create_diagnostic(line: int, stIndex: int, enIndex: int,
                      msg: str, severity: DiagnosticSeverity) -> Diagnostic:
    """Create a Diagnostic"""
    range = Range(
        start=Position(line=line, character=stIndex),
        end=Position(line=line, character=enIndex)
    )
    diag = Diagnostic(
        range=range,
        message=msg,
        severity=severity
    )
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

    LINE_STATE = {"isInComm": False, "loopLevel": 0}  # cross line state
    for lineno, line in enumerate(doc.lines):
        # Max line length
        if len(line) > MAX_LINE_LENGTH:
            diagnostics.append(create_diagnostic(lineno, MAX_LINE_LENGTH, MAX_LINE_LENGTH, MAX_LINE_LENGTH_MESSAGE, MAX_LINE_LENGTH_SEVERITY))
        skip_tokens = []

        # Comment block
        if LINE_STATE['isInComm'] is False:
            match = re.match(BLOCK_COMMENTS_BG, line)
            if match is None:
                pass
            elif match.group(1) == '':
                LINE_STATE['isInComm'] = True
                continue
            else:
                LINE_STATE['isInComm'] = True
                start, end = match.start(1), match.end(1)  # python index
                skip_tokens.append([start, end])
        else:
            match = re.match(BLOCK_COMMENTS_END, line)
            if match is None:
                continue
            elif match.group(1) == '':
                LINE_STATE['isInComm'] = False
                continue
            else:
                LINE_STATE['isInComm'] = False
                start, end = match.start(1), match.end(1)
                skip_tokens.append([start, end])

        # Star Comments
        if re.match(STAR_COMMENTS, line):
            continue

        # Inline Comment
        match = re.match(INLINE_COMM_RE, line)
        if match and match.group(1) != '':
            start, end = match.start(1), match.end(1)
            skip_tokens.append([start, end])

        # STRING
        for match in STRING.finditer(line):
            start, end = match.span()
            if not inSkipTokens(start, end, skip_tokens):
                skip_tokens.append([start, end])

        # Operator Checker
        for match in OPERATOR_REGEX.finditer(line):
            for sindex in range(1, 3):
                start, end = match.start(sindex), match.end(sindex)
                if not inSkipTokens(start, end, skip_tokens):
                    if end - start != 1:
                        diagnostics.append(
                            create_diagnostic(lineno, end, end, OP_WHITESPACE_MESSAGE, OP_WHITESPACE_SEVERITY))

        # Comma Checker
        for match in WHITESPACE_AFTER_COMMA_REGEX.finditer(line):
            start, end = match.start(1), match.end(1)
            if not inSkipTokens(start, end, skip_tokens):
                if end - start != 1:
                    diagnostics.append(
                            create_diagnostic(lineno, end, end, COMMA_WHITESPACE_MESSAGE, COMMA_WHITESPACE_SEVERITY))

        # Loop Indent Checker
        if re.match(LOOP_END, line) and LINE_STATE['loopLevel'] > 0:
            LINE_STATE['loopLevel'] -= 1

        match = re.match(INDENT_REGEX, line)
        if match:
            start, end = match.start(1), match.end(1)
            actual_space = end - start
            if actual_space != LINE_STATE['loopLevel'] * INDENT_SPACE:
                diagnostics.append(create_diagnostic(lineno, end, end, INAP_INDENT_MESSAGE, INAP_INDENT_SEVERITY))

        if re.match(LOOP_START, line):
            LINE_STATE['loopLevel'] += 1

    ls.publish_diagnostics(uri=uri, diagnostics=diagnostics)


def clear_diagnostics(ls: StataLanguageServer, params):
    """Clear diagnostics."""
    uri = ls.workspace.get_document(params.text_document.uri).uri
    ls.publish_diagnostics(uri=uri, diagnostics=[])


def _config_callback(config):
    global MAX_LINE_LENGTH, INDENT_SPACE, ENABLECOMPLETION, ENABLEDOCSTRING, ENABLESTYLECHECKING
    try:
        # Instead of reassigning constants, update the module values
        if 'setMaxLineLength' in config[0]:
            globals()['MAX_LINE_LENGTH'] = int(config[0].get('setMaxLineLength'))
        if 'setIndentSpace' in config[0]:  
            globals()['INDENT_SPACE'] = int(config[0].get('setIndentSpace'))
        if 'enableCompletion' in config[0]:
            globals()['ENABLECOMPLETION'] = config[0].get('enableCompletion')
        if 'enableDocstring' in config[0]:
            globals()['ENABLEDOCSTRING'] = config[0].get('enableDocstring')
        if 'enableStyleChecking' in config[0]:
            globals()['ENABLESTYLECHECKING'] = config[0].get('enableStyleChecking')
    except Exception as e:
        ls.show_message_log(f'Error ocurred: {e}')


@stata_server.feature("workspace/didChangeConfiguration")
def refresh_config(ls: StataLanguageServer, params: DidChangeConfigurationParams):
    if params.settings == 200:
        get_configuration_callback(ls)
