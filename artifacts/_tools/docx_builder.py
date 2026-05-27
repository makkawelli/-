"""
Минималистичный билдер DOCX-файлов.

Используем НИР.docx как шаблон стилей: копируем все служебные части
(styles.xml, numbering.xml, theme1.xml, settings.xml и т. д.),
а document.xml перегенерируем под нужный контент.

Поддерживаемые элементы документа:
    {"type": "h1", "text": "..."}                  - Заголовок 1
    {"type": "h2", "text": "..."}                  - Заголовок 2
    {"type": "h3", "text": "..."}                  - Заголовок 3
    {"type": "p",  "text": "..."}                  - Обычный параграф
    {"type": "p_bold", "text": "..."}              - Параграф жирным
    {"type": "p_indent", "text": "..."}            - С красной строкой
    {"type": "bullet", "text": "..."}              - Маркированный пункт
    {"type": "toc"}                                - Поле оглавления (обновится при F9 в Word)
    {"type": "page_break"}                         - Разрыв страницы
    {"type": "center", "text": "..."}              - Центрированный
    {"type": "center_bold", "text": "..."}         - Центрированный жирный
    {"type": "table", "rows": [["ячейка", ...], ...], "widths": [w1, w2, ...]}  - Таблица
"""
import os
import shutil
import zipfile
from xml.sax.saxutils import escape


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
W14_NS = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'
MC_NS = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'

DOC_OPEN = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<w:document {W_NS} {W14_NS} {MC_NS} mc:Ignorable="w14">'
    '<w:body>'
)

# Размер страницы A4 (11906 x 16838 twips), поля по ГОСТ: лево 30мм, право 15мм, верх/низ 20мм
SECTION_PR = (
    '<w:sectPr>'
    '<w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1134" w:right="850" w:bottom="1134" w:left="1701" '
    'w:header="708" w:footer="708" w:gutter="0"/>'
    '<w:cols w:space="708"/>'
    '<w:docGrid w:linePitch="360"/>'
    '</w:sectPr>'
)
DOC_CLOSE = SECTION_PR + '</w:body></w:document>'


def _esc(s: str) -> str:
    return escape(s or '', {'"': '&quot;'})


def _run(text: str, *, bold=False, italic=False, size=None) -> str:
    rpr_parts = []
    if bold:
        rpr_parts.append('<w:b/><w:bCs/>')
    if italic:
        rpr_parts.append('<w:i/><w:iCs/>')
    if size:
        rpr_parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    rpr = f'<w:rPr>{"".join(rpr_parts)}</w:rPr>' if rpr_parts else ''
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


def _para(content_xml: str, *, style=None, align=None, ind_first=False, spacing_after=None) -> str:
    ppr_parts = []
    if style:
        ppr_parts.append(f'<w:pStyle w:val="{style}"/>')
    if ind_first:
        ppr_parts.append('<w:ind w:firstLine="709"/>')  # 1.25 см
    if align:
        ppr_parts.append(f'<w:jc w:val="{align}"/>')
    if spacing_after is not None:
        ppr_parts.append(f'<w:spacing w:after="{spacing_after}"/>')
    ppr = f'<w:pPr>{"".join(ppr_parts)}</w:pPr>' if ppr_parts else ''
    return f'<w:p>{ppr}{content_xml}</w:p>'


def _heading(level: int, text: str) -> str:
    style_id = str(level)  # styleId='1','2','3' соответствуют heading 1/2/3 в исходных стилях
    # Заголовки выравниваем по левому краю с авто-нумерацией от стиля (если она есть)
    return _para(_run(text), style=style_id)


def _toc_field() -> str:
    # Поле TOC — Word предложит обновить (F9). До обновления виден заглушечный текст.
    return (
        '<w:p>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t xml:space="preserve">[Оглавление будет сформировано автоматически. '
        'В MS Word откройте файл, кликните по этому полю и нажмите F9 — '
        'либо «Ссылки» → «Обновить таблицу».]</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '</w:p>'
    )


def _page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _table(rows, widths=None) -> str:
    """rows: список строк-списков. widths: список ширин в twips (опц.)."""
    if widths is None:
        widths = [9000 // max(1, len(rows[0]))] * len(rows[0])
    grid = ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)

    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            # Cell может быть строкой или списком абзацев
            if isinstance(cell, str):
                paragraphs = [cell]
            else:
                paragraphs = list(cell)
            cell_paras = ''.join(
                _para(_run(p)) for p in paragraphs
            )
            if not cell_paras:
                cell_paras = _para(_run(''))
            cells.append(
                f'<w:tc>'
                f'<w:tcPr><w:tcW w:w="{widths[i]}" w:type="dxa"/></w:tcPr>'
                f'{cell_paras}'
                f'</w:tc>'
            )
        body_rows.append(f'<w:tr>{"".join(cells)}</w:tr>')

    return (
        '<w:tbl>'
        '<w:tblPr>'
        f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '</w:tblBorders>'
        '<w:tblLayout w:type="fixed"/>'
        '</w:tblPr>'
        f'<w:tblGrid>{grid}</w:tblGrid>'
        f'{"".join(body_rows)}'
        '</w:tbl>'
    )


def render_elements(elements) -> str:
    """Принимает список элементов и возвращает XML тела документа."""
    out = []
    for el in elements:
        t = el['type']
        if t == 'h1':
            out.append(_heading(1, el['text']))
        elif t == 'h2':
            out.append(_heading(2, el['text']))
        elif t == 'h3':
            out.append(_heading(3, el['text']))
        elif t == 'p':
            out.append(_para(_run(el['text']), align='both', ind_first=True))
        elif t == 'p_bold':
            out.append(_para(_run(el['text'], bold=True), align='both', ind_first=True))
        elif t == 'p_left':
            out.append(_para(_run(el['text']), align='left'))
        elif t == 'bullet':
            out.append(_para(_run('•  ' + el['text']), align='both'))
        elif t == 'numbered':
            out.append(_para(_run(el['text']), align='both', ind_first=True))
        elif t == 'center':
            out.append(_para(_run(el['text']), align='center'))
        elif t == 'center_bold':
            out.append(_para(_run(el['text'], bold=True), align='center'))
        elif t == 'page_break':
            out.append(_page_break())
        elif t == 'toc':
            out.append(_toc_field())
        elif t == 'table':
            out.append(_table(el['rows'], el.get('widths')))
        elif t == 'empty':
            out.append(_para(_run('')))
        else:
            raise ValueError(f"Unknown element type: {t}")
    return ''.join(out)


def build_docx(template_docx: str, output_docx: str, elements):
    """Создаёт DOCX, копируя служебные части шаблона и заменяя document.xml."""
    body = render_elements(elements)
    new_doc_xml = DOC_OPEN + body + DOC_CLOSE

    # Файлы, которые НЕ копируем из шаблона (генерируем заново или пропускаем)
    SKIP = {'word/document.xml'}

    os.makedirs(os.path.dirname(output_docx) or '.', exist_ok=True)

    with zipfile.ZipFile(template_docx, 'r') as src, \
         zipfile.ZipFile(output_docx, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item in SKIP:
                continue
            # Не тащим вложенные изображения/футеры из НИР, чтобы не было лишних данных
            if item.startswith('word/media/'):
                continue
            if item.startswith('word/footer'):
                continue
            data = src.read(item)
            dst.writestr(item, data)

        # Записываем наш document.xml
        dst.writestr('word/document.xml', new_doc_xml)

    # Уберём ссылки на удалённые footer/header в document.xml.rels — они не нужны.
    # (фактически их и так не будет, потому что мы перезаписали файл; при копии rels их сохранили,
    # но Word корректно проигнорирует rels, на которые нет ссылок в document.xml)
    return output_docx
