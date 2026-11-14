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

    def test_panel_titles_are_not_links_and_rows_are_explicit(self):
        self.assertEqual(self.block.count("<picture><img"), 2)  # the two titles, wrapped so GitHub adds no link
        self.assertEqual(self.block.count("<br>"), 3)
        self.assertNotIn("\n", self.block)

    def test_tiles_cover_the_old_panel_exactly(self):
        widths = [b._skill_crop(c)[2] for c in range(4)]
        self.assertEqual(sum(widths), b.SK_W)
        _, y0, _, h0 = b._skill_crop(0)
        _, y1, _, h1 = b._skill_crop(4)
        self.assertEqual(b.SK_TITLE_H + h0 + h1, 216)
        self.assertEqual(y0 + h0, y1)


if __name__ == "__main__":
    unittest.main()
