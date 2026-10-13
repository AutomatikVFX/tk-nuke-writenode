"""
Persistence for knobs promoted off the encapsulated Write node.

Nuke rebuilds file-type knobs (interleave, first_part, and the rest of the
EXR codec knobs) when file_type is set. Write.writeKnobs() does not record
those knobs, so the hidden settings string keeps an explicit toScript() value
for every promoted knob and the handler puts it back with fromScript().
"""

PROMOTED_BEGIN = "#ATK_PROMOTED_KNOBS_V1"
PROMOTED_END = "#ATK_PROMOTED_KNOBS_END"


def encode_promoted_settings(nk_text, promoted_scripts):
    """
    Build the text stored in tk_write_node_settings.

    The legacy writeKnobs() script stays intact so older sessions still parse
    it. Explicit knob scripts are appended in a block those sessions ignore,
    because the block lines do not start with a promoted knob name.

    :param str nk_text: writeKnobs() output for the encapsulated Write
    :param dict promoted_scripts: Promoted knob name to Knob.toScript() value

    :returns: Combined settings text, before pickling
    :rtype: str
    """
    legacy, _explicit = decode_promoted_settings(nk_text)
    lines = [legacy.rstrip("\n")]
    lines.append(PROMOTED_BEGIN)
    for name in sorted(promoted_scripts or {}):
        script = promoted_scripts[name]
        if script is None:
            continue
        lines.append("%s %s" % (name, _single_line(str(script))))
    lines.append(PROMOTED_END)
    return "\n".join(lines).lstrip("\n") + "\n"


def decode_promoted_settings(payload):
    """
    Split a stored settings record into the legacy knob script and explicit values.

    A record written before this block existed is returned unchanged, with an
    empty explicit map.

    :param str payload: Unpickled tk_write_node_settings text

    :returns: Legacy writeKnobs text, and promoted knob name to toScript() value
    :rtype: tuple
    """
    text = _coerce_text(payload)
    marker = PROMOTED_BEGIN + "\n"
    end_marker = PROMOTED_END
    start = text.find(marker)
    if start == -1:
        return text, {}

    finish = text.find(end_marker, start + len(marker))
    if finish == -1:
        return text, {}

    legacy = text[:start] + text[finish + len(end_marker) :]
    explicit_text = text[start + len(marker) : finish]
    explicit = {}
    for line in explicit_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        name, _separator, script = line.partition(" ")
        explicit[name] = script
    return legacy, explicit


def legacy_promoted_scripts(nk_text, promoted_names):
    """
    Pull promoted knob lines out of a writeKnobs() script.

    File-type knobs are usually absent here. Lines that are present, such as
    autocrop, are still honoured for scripts saved before the explicit block.

    :param str nk_text: Legacy writeKnobs() text, without the explicit block
    :param list promoted_names: Knob names the profile promotes

    :returns: Knob name to the script value from that line
    :rtype: dict
    """
    wanted = set(promoted_names or [])
    found = {}
    for line in _coerce_text(nk_text).split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _separator, script = line.partition(" ")
        if name not in wanted:
            continue
        found[name] = script
    return found


def choose_promoted_scripts(in_session, pre_scripts, legacy_scripts, explicit_scripts):
    """
    Choose which promoted knob scripts to put back after file_type is rebuilt.

    An already-open node keeps whatever the artist currently has, including a
    value that matches Nuke's default. A script load prefers the explicit
    record, then anything writeKnobs() captured, then whatever the encapsulated
    Write still held before file_type wiped the file-type knobs.

    :param bool in_session: Node was already constructed in this Nuke session
    :param dict pre_scripts: toScript() values read before file_type was set
    :param dict legacy_scripts: Values parsed from the writeKnobs() record
    :param dict explicit_scripts: toScript() values stored for promoted knobs

    :returns: Knob name to toScript() value to apply
    :rtype: dict
    """
    if in_session:
        chosen = {}
        chosen.update(explicit_scripts or {})
        chosen.update(pre_scripts or {})
        return chosen

    chosen = {}
    chosen.update(pre_scripts or {})
    chosen.update(legacy_scripts or {})
    chosen.update(explicit_scripts or {})
    return chosen


def _single_line(script):
    """
    Flatten a knob script so it stays on one settings line.

    :param str script: Knob.toScript() value

    :returns: That script with line breaks turned into spaces
    :rtype: str
    """
    return " ".join(script.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _coerce_text(payload):
    """
    Normalise an unpickled settings record to a string.

    :param str payload: Unpickled value, which may be empty or bytes

    :returns: Settings text
    :rtype: str
    """
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    return str(payload)
