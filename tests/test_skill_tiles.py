"""The README's tool tiles must match the generator: one link per tool, an image that exists, nothing extra."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_assets as b  # noqa: E402


class SkillTileTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.block = re.search(r"## Tools\n\n(.*?)\n\n## ", text, re.S).group(1)

    def test_every_tool_has_exactly_one_working_link_and_image(self):
        anchors = re.findall(r'<a href="([^"]+)"><img src="(assets/[^"]+)" alt="([^"]+)"', self.block)
        want = []
        for panel, _, items in b.SKILL_PANELS:
            for n, (_, label, url) in enumerate(items):
                want.append((url, "assets/%s.svg" % b.skill_file_stem(panel, n), b.SKILL_FULL_NAMES.get(label, label)))
        self.assertEqual(sorted(anchors), sorted(want))
        for _, src, _ in anchors:
            self.assertTrue((ROOT / src).is_file(), src)

    def test_links_are_plain_https_without_tracking(self):
        for url, _, _ in re.findall(r'<a href="([^"]+)"><img src="(assets/[^"]+)" alt="([^"]+)"', self.block):
            self.assertTrue(url.startswith("https://"), url)
            self.assertNotIn("utm_", url)

    def test_panels_are_stacked_and_every_tile_is_the_same_size(self):
        self.assertEqual(self.block.count("<picture><img"), 2)  # the two titles, wrapped so GitHub adds no link
        self.assertEqual(self.block.count("<br>"), 4)  # a break after each title and after each panel's tiles
        self.assertNotIn("\n", self.block)
        self.assertEqual(set(re.findall(r'<a href="[^"]+"><img [^>]*width="([^"]+)"', self.block)), {str(b.SK_TILE_W)})

    def test_a_row_of_four_tiles_fits_a_phone_and_the_title_does_not_overflow_it(self):
        self.assertLessEqual(4 * b.SK_TILE_W, 328)  # the narrowest common phone's text column
        self.assertLessEqual(b.SK_TITLE_W, 328)
        self.assertLessEqual(8 * b.SK_TILE_W, 700)  # a whole panel is one row on a desktop

    def test_generated_tiles_have_the_declared_size(self):
        files = b.build_all()
        for panel, _, items in b.SKILL_PANELS:
            for n in range(len(items)):
                svg = files["%s.svg" % b.skill_file_stem(panel, n)]
                self.assertIn('width="%d" height="%d"' % (b.SK_TILE_W, b.SK_TILE_H), svg)


if __name__ == "__main__":
    unittest.main()
