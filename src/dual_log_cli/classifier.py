# INFRASTRUCTURE

ROLES = ("user", "assistant", "system")
TYPES = ("text", "thinking", "tool_use", "tool_result", "image",
         "system", "system-reminder", "task-notification", "command-message")

ONLY_FORMS = (f"a role ({'/'.join(ROLES)}), a type ({', '.join(TYPES)}), "
              f"or a role/type pair (e.g. user/text)")


class BadClassifierError(Exception):
    pass


# FUNCTIONS


def parse_only(spec: str) -> tuple:
    if not spec:
        return "", ""
    token = spec.strip().lower()
    if "/" in token:
        role, _, type_ = token.partition("/")
        if role not in ROLES or type_ not in TYPES:
            raise BadClassifierError(f"--only {spec!r} is not a known classifier — accepted: {ONLY_FORMS}")
        return role, type_
    if token in ROLES:
        return token, ""
    if token in TYPES:
        return "", token
    raise BadClassifierError(f"--only {spec!r} is not a known classifier — accepted: {ONLY_FORMS}")


def matches_only(role: str, block_types, wanted: tuple) -> bool:
    want_role, want_type = wanted
    if want_role and role.lower() != want_role:
        return False
    if want_type and want_type not in {str(t).lower() for t in block_types}:
        return False
    return True
