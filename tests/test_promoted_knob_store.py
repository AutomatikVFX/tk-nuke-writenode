import importlib.util
import os
import unittest


def _load_store():
    """
    Load the settings codec without importing the Nuke handler.

    :returns: promoted_knob_store module
    :rtype: module
    """
    path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "python",
        "tk_nuke_writenode",
        "promoted_knob_store.py",
    )
    spec = importlib.util.spec_from_file_location("promoted_knob_store", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store = _load_store()
choose_promoted_scripts = store.choose_promoted_scripts
decode_promoted_settings = store.decode_promoted_settings
encode_promoted_settings = store.encode_promoted_settings
legacy_promoted_scripts = store.legacy_promoted_scripts


class TestPromotedKnobStore(unittest.TestCase):

    def test_roundtrip_keeps_file_type_knob_scripts(self):
        nk = 'file_type exr\ndatatype "16 bit half"\nautocrop true\n'
        promoted = {
            "interleave": '"channels"',
            "first_part": "rgb",
            "autocrop": "true",
            "channels": "all",
        }

        stored = encode_promoted_settings(nk, promoted)
        legacy, explicit = decode_promoted_settings(stored)

        self.assertIn("file_type exr", legacy)
        self.assertIn("autocrop true", legacy)
        self.assertNotIn("#ATK_PROMOTED_KNOBS_V1", legacy)
        self.assertEqual(promoted, explicit)

    def test_legacy_record_without_block_stays_intact(self):
        nk = 'datatype "16 bit half"\nautocrop true\n'

        legacy, explicit = decode_promoted_settings(nk)

        self.assertEqual(nk, legacy)
        self.assertEqual({}, explicit)

    def test_legacy_parser_reads_indented_promoted_lines_only(self):
        nk = '\n file /tmp/out.exr\n autocrop true\n interleave "channels and layers"\n'

        found = legacy_promoted_scripts(nk, ["autocrop", "interleave", "first_part"])

        self.assertEqual(
            {"autocrop": "true", "interleave": '"channels and layers"'},
            found,
        )

    def test_explicit_block_is_not_parsed_as_legacy_knobs(self):
        stored = encode_promoted_settings(
            "autocrop true\n",
            {"interleave": '"channels"', "first_part": "rgb"},
        )
        legacy, _explicit = decode_promoted_settings(stored)

        found = legacy_promoted_scripts(
            legacy, ["autocrop", "interleave", "first_part"]
        )

        self.assertEqual({"autocrop": "true"}, found)

    def test_encoding_twice_does_not_duplicate_the_block(self):
        once = encode_promoted_settings("autocrop true\n", {"interleave": '"channels"'})
        twice = encode_promoted_settings(once, {"interleave": '"channels and layers"'})

        _legacy, explicit = decode_promoted_settings(twice)

        self.assertEqual({'"channels and layers"'}, set(explicit.values()))
        self.assertEqual(1, twice.count("#ATK_PROMOTED_KNOBS_V1"))

    def test_open_node_keeps_the_live_value_over_a_stale_record(self):
        chosen = choose_promoted_scripts(
            True,
            {"interleave": '"channels"', "first_part": "rgb"},
            {"interleave": '"channels and layers"'},
            {"interleave": '"channels and layers"', "first_part": "rgba"},
        )

        self.assertEqual(
            {"interleave": '"channels"', "first_part": "rgb"},
            chosen,
        )

    def test_open_node_fills_a_knob_the_live_write_does_not_have_yet(self):
        chosen = choose_promoted_scripts(
            True,
            {"autocrop": "true"},
            {},
            {"first_part": "rgb"},
        )

        self.assertEqual({"autocrop": "true", "first_part": "rgb"}, chosen)

    def test_script_load_prefers_the_explicit_record(self):
        chosen = choose_promoted_scripts(
            False,
            {"interleave": '"channels"'},
            {"interleave": '"channels and layers"', "autocrop": "true"},
            {"interleave": '"channels"', "first_part": "rgb"},
        )

        self.assertEqual(
            {
                "interleave": '"channels"',
                "autocrop": "true",
                "first_part": "rgb",
            },
            chosen,
        )

    def test_script_load_uses_the_write_when_the_record_missed_the_knob(self):
        chosen = choose_promoted_scripts(
            False,
            {"interleave": '"channels"', "first_part": "rgb"},
            {"autocrop": "true"},
            {},
        )

        self.assertEqual(
            {
                "interleave": '"channels"',
                "first_part": "rgb",
                "autocrop": "true",
            },
            chosen,
        )


if __name__ == "__main__":
    unittest.main()
