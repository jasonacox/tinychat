"""
Tests for app/static/js/utils/markdown.js renderMarkdownWithMath().

LaTeX blocks are pulled out before markdown/DOMPurify and put back afterwards,
so their contents must be escaped on the way back in. Runs the real
marked.min.js + markdown.js in V8 (mini-racer); DOMPurify is stubbed with a
strict tag filter since the real one needs a browser DOM.
"""

from pathlib import Path

import pytest

MiniRacer = pytest.importorskip("py_mini_racer").MiniRacer

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"

# Stand-in for DOMPurify: drop every tag that is not plain formatting markup.
DOMPURIFY_STUB = r"""
var DOMPurify = { sanitize: function (html) {
    return html.replace(/<\/?([a-zA-Z0-9]+)[^>]*>/g, function (tag, name) {
        var ok = ['p','em','strong','code','pre','span','ul','ol','li','h1','h2','h3','br','a','blockquote'];
        return ok.indexOf(name.toLowerCase()) === -1 ? '' : tag.replace(/\son\w+=("[^"]*"|'[^']*'|[^\s>]+)/g, '');
    });
}};
"""


@pytest.fixture(scope="module")
def js():
    ctx = MiniRacer()
    ctx.eval("var window = this; var self = this; var console = {log: function(){}, warn: function(){}, error: function(){}};")
    ctx.eval((STATIC / "libs" / "marked.min.js").read_text())
    ctx.eval(DOMPURIFY_STUB)
    ctx.eval((STATIC / "js" / "utils" / "markdown.js").read_text())
    return ctx


def render(ctx, text):
    return ctx.call("renderMarkdownWithMath", text)


def test_sanitizer_stub_strips_plain_html(js):
    assert "<img" not in render(js, "hi <img src=x onerror=alert(1)>")


@pytest.mark.parametrize("payload", [
    "$<img src=x onerror=alert(1)>$",
    "$$<img src=x onerror=alert(1)>$$",
    "\\(<img src=x onerror=alert(1)>\\)",
    "\\[<svg onload=alert(1)>\\]",
    "Total: $x</span><script>alert(1)</script>$",
])
def test_math_blocks_cannot_inject_html(js, payload):
    out = render(js, payload)
    assert "<img" not in out and "<svg" not in out and "<script" not in out
    assert "&lt;" in out


def test_math_still_rendered_for_katex(js):
    out = render(js, "Euler: $e^{i\\pi} + 1 = 0$ and $$a < b$$")
    assert '<span class="math-inline">\\(e^{i\\pi} + 1 = 0\\)</span>' in out
    assert "\\[a &lt; b\\]" in out


def test_dollar_patterns_in_math_are_literal(js):
    # "$&" in a String.replace replacement string means "the matched text"
    out = render(js, "\\(a $& b\\)")
    assert "\\(a $&amp; b\\)" in out
    assert "PLACEHOLDER" not in out


def test_currency_still_supported(js):
    assert "$5 and $10" in render(js, "It costs $5 and $10.")
