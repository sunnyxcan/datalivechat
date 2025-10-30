# api/filters.py

import re

def render_cell(cell_content):
    if not isinstance(cell_content, str):
        return str(cell_content)

    text = cell_content.strip()
    if not text:
        return ''

    url_pattern = re.compile(r'(?:^|\s+)(\d+\.\s*)?(https?://\S+|prnt\.sc/\S+)', re.IGNORECASE)
    matches = list(url_pattern.finditer(text))

    if not matches:
        return f'<span class="cell-content">{text}</span>'

    output_html = []
    last_end = 0

    for match in matches:
        full_match_start = match.start(0)
        full_match_end = match.end(0)
        number_prefix = match.group(1)
        link_part = match.group(2)

        non_link_text = text[last_end:full_match_start]
        if non_link_text.strip():
            output_html.append(non_link_text.strip())
            output_html.append('<br>')

        display_text = link_part.strip()
        full_url = display_text

        if display_text.startswith('prnt.sc'):
            full_url = 'https://' + display_text

        link_html = f'<a href="{full_url}" target="_blank">{display_text}</a>'

        if number_prefix:
            display_num = number_prefix.strip()
            output_html.append(f'{display_num} ')

        output_html.append(link_html)
        output_html.append('<br>')

        last_end = full_match_end

    trailing_text = text[last_end:].strip()
    if trailing_text:
        output_html.append(trailing_text)

    final_output = "".join(output_html).rstrip('<br>')

    if not final_output and text:
        return f'<span class="cell-content">{text}</span>'

    return final_output

def format_number(value):
    """
    Format angka dengan pemisah ribuan.
    Jika float, tampilkan dengan 2 angka desimal.
    Jika integer, tampilkan sebagai integer.
    """
    if isinstance(value, float):
        # 💡 KOREKSI: Menggunakan .2f untuk menampilkan 2 angka desimal
        # Contoh: 0.75 akan ditampilkan sebagai 0.75
        # Contoh: 3.00 akan ditampilkan sebagai 3.00
        return f"{value:,.2f}"
    elif isinstance(value, int):
        # Untuk integer, tetap tampilkan tanpa desimal
        return f"{value:,}"
    try:
        # Coba konversi string menjadi float dan format
        float_val = float(value)
        return f"{float_val:,.2f}"
    except (ValueError, TypeError):
        return str(value)