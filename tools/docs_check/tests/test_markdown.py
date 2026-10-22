"""Markdown parsing shared by the checks: slugs, fences, links."""

import unittest

from tools.docs_check import markdown
from tools.docs_check.tests.fixture_tree import CheckerCase

FENCED = """\
# Title

```
## Hidden heading
[hidden](nowhere.md)
AAA-999
```

~~~python
[also hidden](nowhere-either.md)
~~~

## Visible

[shown](shown.md)
"""


class SlugTest(unittest.TestCase):
    def test_github_slug_drops_punctuation_and_numbers_duplicates(self):
        text = "## Known traps\n\n## A — b\n\n## `x` y\n\n## Known traps\n"
        self.assertEqual(markdown.heading_slugs(text), ["known-traps", "a--b", "x-y", "known-traps-1"])

    def test_explicit_anchors_are_anchors(self):
        text = '- <a id="AAA-001"></a>**AAA-001** rule\n<a name="Other"></a>\n'
        self.assertTrue({"AAA-001", "Other"} <= markdown.anchors(text))


class FenceTest(CheckerCase):
    def test_fenced_blocks_hide_links_ids_and_headings(self):
        self.assertEqual([target for _, target in markdown.links(FENCED)], ["shown.md"])
        self.assertEqual([text for _, _, text in markdown.headings(FENCED)], ["Title", "Visible"])
        tree = self.tree()
        tree.append("specs/first.md", "\n```\n[broken](nowhere.md) AAA-999 D-12\n```\n")
        self.assertClean(tree.run())


if __name__ == "__main__":
    unittest.main()
