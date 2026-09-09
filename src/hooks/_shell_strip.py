# INFRASTRUCTURE


# FUNCTIONS

class _StripError(Exception):
    pass


_CMD_SUBST = '$('


def _strip_non_shell_active(command: str) -> str:
    try:
        return _strip_impl(command)
    except Exception:
        return command


def _scan_heredoc(command: str, i: int, n: int) -> tuple:
    parts = []
    j = i + 2
    if j < n and command[j] == '-':
        j += 1
    while j < n and command[j] in (' ', '\t'):
        j += 1
    q = None
    if j < n and command[j] in ("'", '"'):
        q = command[j]
        j += 1
    mk = []
    while j < n and command[j] not in ('\n', ' ', '\t'):
        if q and command[j] == q:
            j += 1
            break
        mk.append(command[j])
        j += 1
    marker = ''.join(mk)
    if not marker:
        return command[i], i + 1
    while i < j:
        parts.append(command[i])
        i += 1
    while i < n and command[i] != '\n':
        parts.append(command[i])
        i += 1
    if i < n:
        parts.append('\n')
        i += 1
    found_term = False
    while i < n:
        ls = i
        while i < n and command[i] != '\n':
            i += 1
        line = command[ls:i]
        if i < n:
            i += 1
        if line.strip() == marker:
            parts.append(line)
            parts.append('\n')
            found_term = True
            break
        parts.append(' ' * len(line))
        parts.append('\n')
    if not found_term:
        raise _StripError("unclosed heredoc")
    return ''.join(parts), i


def _scan_ansi_c_quote(command: str, i: int, n: int) -> tuple:
    parts = ['  ']
    i += 2
    closed = False
    while i < n:
        if command[i] == '\\' and i + 1 < n:
            parts.append('  ')
            i += 2
        elif command[i] == "'":
            parts.append(' ')
            i += 1
            closed = True
            break
        else:
            parts.append(' ')
            i += 1
    if not closed:
        raise _StripError("unclosed ANSI-C quote")
    return ''.join(parts), i


def _scan_cmd_subst(command: str, i: int, n: int) -> tuple:
    parts = [_CMD_SUBST]
    i += 2
    depth = 1
    while i < n and depth > 0:
        if command[i] == '(':
            depth += 1
        elif command[i] == ')':
            depth -= 1
            if depth == 0:
                parts.append(')')
                i += 1
                break
        parts.append(command[i])
        i += 1
    return ''.join(parts), i


def _scan_backtick(command: str, i: int, n: int) -> tuple:
    parts = ['`']
    i += 1
    while i < n and command[i] != '`':
        parts.append(command[i])
        i += 1
    if i < n:
        parts.append('`')
        i += 1
    return ''.join(parts), i


def _scan_single_quote(command: str, i: int, n: int) -> tuple:
    parts = [' ']
    i += 1
    while i < n and command[i] != "'":
        parts.append(' ')
        i += 1
    if i >= n:
        raise _StripError("unclosed single quote")
    parts.append(' ')
    i += 1
    return ''.join(parts), i


def _scan_double_quote(command: str, i: int, n: int) -> tuple:
    parts = [' ']
    i += 1
    closed = False
    while i < n:
        if command[i] == '\\' and i + 1 < n:
            parts.append('  ')
            i += 2
        elif command[i] == '"':
            parts.append(' ')
            i += 1
            closed = True
            break
        else:
            parts.append(' ')
            i += 1
    if not closed:
        raise _StripError("unclosed double quote")
    return ''.join(parts), i


def _strip_impl(command: str) -> str:
    out = []
    i = 0
    n = len(command)
    while i < n:
        if command[i:i+2] == '<<' and command[i:i+3] != '<<<':
            fragment, i = _scan_heredoc(command, i, n)
            out.append(fragment)
        elif command[i:i+2] == "$'":
            fragment, i = _scan_ansi_c_quote(command, i, n)
            out.append(fragment)
        elif command[i:i+2] == _CMD_SUBST:
            fragment, i = _scan_cmd_subst(command, i, n)
            out.append(fragment)
        elif command[i] == '`':
            fragment, i = _scan_backtick(command, i, n)
            out.append(fragment)
        elif command[i] == "'":
            fragment, i = _scan_single_quote(command, i, n)
            out.append(fragment)
        elif command[i] == '"':
            fragment, i = _scan_double_quote(command, i, n)
            out.append(fragment)
        else:
            out.append(command[i])
            i += 1
    return ''.join(out)
