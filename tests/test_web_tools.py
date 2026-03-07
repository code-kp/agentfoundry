import unittest

from workspace.tools.web_tools import _extract_page_content, _parse_duckduckgo_results


class WebToolsTest(unittest.TestCase):
    def test_parse_duckduckgo_results_extracts_title_snippet_and_target_url(self) -> None:
        html = """
        <html>
          <body>
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fanswer">Example Answer</a>
            <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fanswer">
              Crisp summary from the web.
            </a>
          </body>
        </html>
        """

        results = _parse_duckduckgo_results(html, max_results=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Example Answer")
        self.assertEqual(results[0]["url"], "https://example.com/answer")
        self.assertEqual(results[0]["snippet"], "Crisp summary from the web.")

    def test_extract_page_content_strips_script_and_html_noise(self) -> None:
        html = """
        <html>
          <head>
            <title>Example Page</title>
            <script>console.log("ignore");</script>
          </head>
          <body>
            <main>
              <h1>Headline</h1>
              <p>Useful body text.</p>
            </main>
          </body>
        </html>
        """

        title, content = _extract_page_content(html, max_chars=200)

        self.assertEqual(title, "Example Page")
        self.assertIn("Headline", content)
        self.assertIn("Useful body text.", content)
        self.assertNotIn("console.log", content)


if __name__ == "__main__":
    unittest.main()
