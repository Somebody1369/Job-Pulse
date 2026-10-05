from vacancies.collectors.html import html_to_text


def test_html_to_text_separates_blocks_list_items_and_line_breaks() -> None:
    markup = "<h3>About <b>us</b></h3><ul><li>Python</li><li>Django</li></ul><p>First<br>Second</p>"

    assert html_to_text(markup) == "About us\n• Python\n• Django\nFirst\nSecond"


def test_html_to_text_collapses_whitespace_inside_blocks() -> None:
    markup = "<p>Remote&nbsp;&nbsp;and\n\t  hybrid</p>\n\n<p>  Kyiv  </p>"

    assert html_to_text(markup) == "Remote and hybrid\nKyiv"


def test_html_to_text_preserves_preformatted_lines() -> None:
    assert html_to_text("<pre>pip install\n  django</pre>") == "pip install\ndjango"


def test_html_to_text_drops_excluded_nodes_and_empty_list_items() -> None:
    markup = (
        "<ul><li></li><li>Go</li></ul>"
        '<div><a href="https://jobs.dou.ua/vacancies/1/#reply-btn-id">Apply</a></div>'
    )

    assert html_to_text(markup, exclude='a[href$="#reply-btn-id"]') == "• Go"


def test_html_to_text_ignores_comments() -> None:
    assert html_to_text("<p>Visible<!-- hidden --></p>") == "Visible"
