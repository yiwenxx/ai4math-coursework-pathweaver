"""Parse the balanced groups and attributes used by the pinned Liberty libraries."""
import re


def strip_comments(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def groups(text):
    """Return direct Liberty child groups, skipping each balanced child body."""
    pattern = re.compile(r"([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{")
    result, position = [], 0
    while match := pattern.search(text, position):
        depth, quote, escape = 1, False, False
        end = match.end()
        while end < len(text) and depth:
            char = text[end]
            if escape:
                escape = False
            elif quote and char == "\\":
                escape = True
            elif char == '"':
                quote = not quote
            elif not quote:
                depth += (char == "{") - (char == "}")
            end += 1
        if depth:
            raise ValueError(f"unbalanced Liberty group {match[1]}")
        result.append((match[1], match[2].strip().strip('"'), text[match.end():end - 1], match.start(), end))
        position = end
    return result


def attributes(text, child_groups):
    pieces, previous = [], 0
    for _, _, _, start, end in child_groups:
        pieces.append(text[previous:start])
        previous = end
    pieces.append(text[previous:])
    result = {}
    for match in re.finditer(r'(\w+)\s*:\s*("(?:\\.|[^"\\])*"|[^;]+)\s*;', "".join(pieces)):
        result[match[1]] = match[2].strip().strip('"')
    return result
