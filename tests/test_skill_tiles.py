"""The README's tool tiles must match the generator, and the tile widths must give a clean layout at every screen width."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_assets as b  # noqa: E402


def readme_column(screen_width: int, scrollbar: int) -> int:
    """Width of the README's text column on github.com/<user>, measured in headless Chrome on 2026-11-14.

    Phone layout (up to 767 px): screen - 82. Two-column layout: 768 to 1011 px, screen - 370; 1012 px and up,
    screen - 434, which stops growing at 846. A desktop scroll bar (15 px in headless Chrome, none on a phone or an
    overlay-scroll-bar Mac) takes its width out of the screen first.
    """
    usable = screen_width - scrollbar
    if screen_width <= 767:
        return usable - 82
    if screen_width <= 1011:
        return usable - 370
    return min(usable - 434, 846)


class SkillTileTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.block = re.search(r"## Tools\n\n(.*?)\n\n## ", text, re.S).group(1)

    def test_readme_block_is_the_generated_one(self):
        self.assertEqual(self.block, b.skills_readme_block(), "run: python scripts/build_assets.py --tools-block")

    def test_every_tool_has_exactly_one_working_link_and_every_image_exists(self):
        anchors = re.findall(r'<a href="([^"]+)"><picture>.*?alt="([^"]+)"', self.block)
        want = [(url, b.SKILL_FULL_NAMES.get(label, label)) for _, _, items in b.SKILL_PANELS for _, label, url in items]
        self.assertEqual(sorted(anchors), sorted(want))
        for src in re.findall(r'(?:src|srcset)="(assets/[^"]+)"', self.block):
            self.assertTrue((ROOT / src).is_file(), src)
        for url, _ in anchors:
            self.assertTrue(url.startswith("https://"), url)
            self.assertNotIn("utm_", url)

    def test_panels_are_stacked_with_the_title_in_a_picture_and_no_newline(self):
        self.assertEqual(self.block.count("<br>"), 4)  # after each title and after each panel's tiles
        self.assertEqual(len(re.findall(r'<picture><img src="assets/skills-[a-z]+-title\.svg"', self.block)), 2)
        self.assertNotIn("\n", self.block)
        # a width on a tile's img would pin every source to that width
        self.assertEqual(len(re.findall(r'<img src="assets/skills-[a-z]+-[a-z.]+\.svg" alt="[^"]+" title="[^"]+" align="top">',
                                        self.block)), 16)

    def test_title_fits_the_narrowest_column(self):
        self.assertLessEqual(b.SK_TITLE_W, readme_column(320, 15))

    def test_generated_tiles_have_the_declared_size(self):
        files = b.build_all()
        for panel, _, items in b.SKILL_PANELS:
            for n in range(len(items)):
                for w in [b.SK_TILE_W] + [t for t, _ in b.SK_TIERS]:
                    svg = files["%s.svg" % b.skill_file_stem(panel, n, w)]
                    self.assertIn('width="%d" height="%d"' % (w, b.SK_TILE_H), svg)

    def test_tier_ranges_do_not_overlap(self):
        spans = sorted(r for _, ranges in b.SK_TIERS for r in ranges)
        for (_, hi), (lo, _) in zip(spans, spans[1:]):
            self.assertLess(hi, lo)

    def test_the_readme_queries_select_the_tier_widths(self):
        queries = re.findall(r'<source media="([^"]+)" srcset="assets/skills-build-python-(\d+)\.svg">', self.block)
        self.assertEqual([int(w) for _, w in queries], [w for w, _ in b.SK_TIERS])
        for media, w in queries:
            for part in media.split(", "):
                m = re.fullmatch(r"(?:\(min-width: (\d+)px\) and )?\(max-width: (\d+)px\)", part)
                self.assertTrue(m, part)
                lo, hi = int(m.group(1) or 0), int(m.group(2))
                for screen in (lo, hi):
                    self.assertEqual(b.skill_tile_width_at(screen), int(w))

    def test_two_tiles_to_a_line_when_the_column_is_narrow_and_a_whole_panel_when_it_is_wide(self):
        for screen in range(320, 1800):
            w = b.skill_tile_width_at(screen)
            for scrollbar in (0, 15):
                column = readme_column(screen, scrollbar)
                if w == b.SK_TILE_W:
                    self.assertGreaterEqual(column // w, 8, (screen, scrollbar, column))
                else:
                    self.assertEqual(column // w, 2, (screen, scrollbar, column, w))


if __name__ == "__main__":
    unittest.main()
