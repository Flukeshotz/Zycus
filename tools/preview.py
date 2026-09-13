"""
HTML preview from RenderedDoc (D-52, task 4.3). Uses the same intermediate
model as the .docx writer, so the browser preview is always pixel-faithful
to the downloadable document.

Output is an HTML fragment (no <html>/<head>/<body>) suitable for inserting
into the Draft tab's container. Highlights and notes use CSS classes that
styles.css defines.
"""
from __future__ import annotations

import html as html_mod

from tools.assembler import RenderedDoc


def rendered_doc_to_html(rendered: RenderedDoc) -> str:
    parts: list[str] = []

    if rendered.banner:
        parts.append(f'<p class="preview-banner">{_esc(rendered.banner)}</p>')

    parts.append(f'<h2 class="preview-title">{_esc(rendered.title)}</h2>')

    for paragraph in rendered.paragraphs:
        inner = ""
        for run in paragraph.runs:
            if not run.text:
                continue
            text = _esc(run.text)
            cls = ""
            if run.highlight == "yellow":
                cls = "highlight-yellow"
            elif run.highlight == "red":
                cls = "highlight-red"

            if cls:
                text = f'<mark class="{cls}">{text}</mark>'

            if run.note:
                text += f'<span class="preview-note" title="{_esc(run.note)}">[note]</span>'

            inner += text
        parts.append(f"<p>{inner}</p>")

    return "\n".join(parts)


def _esc(s: str) -> str:
    return html_mod.escape(s, quote=True)
