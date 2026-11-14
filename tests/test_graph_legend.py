"""The legend under the knowledge graph must cover every kind of dot, use the graph's colours, and link to the graph."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_assets as b  # noqa: E402


class GraphLegendTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_every_kind_of_dot_has_a_chip_in_the_readme_that_links_to_the_graph(self):
        chips = re.findall(r'<a href="(https://gitchrisqueen\.github\.io/gitchrisqueen/graph/[^"]*)">'
                           r'<img src="assets/(graph-legend-[a-z]+\.svg)" alt="([^"]+)" align="top"></a>', self.readme)
        self.assertEqual([c[1] for c in chips], [b.legend_file(stem) for stem, *_ in b.LEGEND])
        self.assertEqual(len({c[0] for c in chips}), 1)
        self.assertEqual([c[2] for c in chips], [desc for *_, desc in b.LEGEND])
        for _, src, _ in chips:
            self.assertTrue((ROOT / "assets" / src).is_file(), src)

    def test_legend_covers_every_kind_in_the_graph_data(self):
        import json
        kinds = {n["kind"] for n in json.loads((ROOT / "data" / "graph.json").read_text())["nodes"]}
        self.assertEqual(kinds, {kind for _, kind, *_ in b.LEGEND})

    def test_chip_colours_are_the_graphs(self):
        files = b.build_all()
        for stem, kind, *_ in b.LEGEND:
            svg = files[b.legend_file(stem)]
            if kind == "me":  # a lit ball: a gradient of the brand gold and cream, not a flat dot
                self.assertIn('fill="url(#meBall)"', svg)
                self.assertIn('stop-color="%s"' % b.GOLD, svg)
            elif kind != "tech":
                self.assertIn('fill="%s"' % b.KIND_STYLE[kind][1], svg)

    def test_a_row_of_chips_wraps_two_to_a_line_on_a_phone(self):
        self.assertLessEqual(2 * b.LEGEND_W, 278)  # the README column on a 360 px phone


if __name__ == "__main__":
    unittest.main()
