"""导出服务。

支持 TXT / CSV / Markdown / Word / Excel / JSON / ZIP。
所有内容均在内存中生成，返回字节流，不落地临时文件。
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Document
from ..utils.text import csv_safe, slugify
from ..utils.time import now

SUPPORTED_FORMATS = {
    "txt": "纯文本",
    "csv": "CSV 表格",
    "md": "Markdown",
    "docx": "Word 文档",
    "xlsx": "Excel 表格",
    "json": "JSON 数据",
    "zip": "ZIP 归档",
}

MEDIA_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}


class ExportError(ValueError):
    """导出失败。"""


@dataclass(slots=True)
class ExportResult:
    filename: str
    content: bytes
    media_type: str
    count: int


def _load(db: Session, ids: list[int]) -> list[Document]:
    if not ids:
        raise ExportError("请选择需要导出的记录")
    if len(ids) > 200:
        raise ExportError("单次最多导出 200 条记录")
    documents = list(db.scalars(select(Document).where(Document.id.in_(ids))).all())
    # 保持用户选择的顺序
    order = {document_id: index for index, document_id in enumerate(ids)}
    documents.sort(key=lambda item: order.get(item.id, 0))
    if not documents:
        raise ExportError("选中的记录不存在")
    return documents


def _base_filename(documents: list[Document], fmt: str) -> str:
    stamp = now().strftime("%Y%m%d_%H%M")
    if len(documents) == 1:
        stem = slugify(documents[0].title or "insightdesk", fallback="insightdesk")
        return f"{stem}_{stamp}.{fmt}"
    return f"识文台导出_{len(documents)}条_{stamp}.{fmt}"


def _document_header(document: Document) -> str:
    return (
        f"标题：{document.title}\n"
        f"来源：{document.source_type}"
        + (f"（{document.source_url}）" if document.source_url else "")
        + f"\n引擎：{document.engine or '-'}\n"
        f"字数：{document.char_count}\n"
        f"创建时间：{document.created_at}\n"
        f"更新时间：{document.updated_at}\n"
    )


def _to_txt(documents: list[Document]) -> bytes:
    chunks = []
    for document in documents:
        chunks.append(
            f"===== {document.title} =====\n{_document_header(document)}\n{document.content}\n"
        )
    return ("\n\n".join(chunks)).encode("utf-8")


def _to_csv(documents: list[Document]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["ID", "标题", "来源类型", "来源链接", "识别引擎", "字数", "标签", "收藏", "创建时间", "内容"])
    for document in documents:
        writer.writerow(
            [
                document.id,
                csv_safe(document.title),
                document.source_type,
                csv_safe(document.source_url or ""),
                document.engine,
                document.char_count,
                csv_safe("、".join(document.tags_list)),
                "是" if document.favorite else "否",
                document.created_at,
                csv_safe(document.content),
            ]
        )
    # UTF-8 BOM：保证 Excel 直接打开中文不乱码
    return buffer.getvalue().encode("utf-8-sig")


def _to_markdown(documents: list[Document]) -> bytes:
    chunks = []
    for document in documents:
        tags = " ".join(f"`#{tag}`" for tag in document.tags_list)
        chunks.append(
            f"# {document.title}\n\n"
            f"> 来源：{document.source_type} ｜ 引擎：{document.engine or '-'} ｜ 字数：{document.char_count}\n"
            f"> 创建：{document.created_at}\n"
            + (f"> 标签：{tags}\n" if tags else "")
            + f"\n{document.content}\n"
        )
    return ("\n\n---\n\n".join(chunks)).encode("utf-8")


def _to_json(documents: list[Document]) -> bytes:
    payload = [
        {
            "id": document.id,
            "title": document.title,
            "source_type": document.source_type,
            "source_url": document.source_url,
            "engine": document.engine,
            "language": document.language,
            "confidence": document.confidence,
            "char_count": document.char_count,
            "tags": document.tags_list,
            "favorite": bool(document.favorite),
            "content": document.content,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }
        for document in documents
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _to_docx(documents: list[Document]) -> bytes:
    docx = DocxDocument()

    # 统一正文字体，确保中文使用微软雅黑、西文使用 Calibri
    style = docx.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    for index, document in enumerate(documents):
        if index:
            docx.add_page_break()

        heading = docx.add_heading(document.title or "未命名文档", level=1)
        heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

        meta = docx.add_paragraph()
        meta_run = meta.add_run(
            f"来源：{document.source_type} ｜ 引擎：{document.engine or '-'} ｜ "
            f"字数：{document.char_count} ｜ 时间：{document.created_at}"
        )
        meta_run.font.size = Pt(8.5)
        meta_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

        if document.source_url:
            link_paragraph = docx.add_paragraph()
            link_run = link_paragraph.add_run(document.source_url)
            link_run.font.size = Pt(8.5)
            link_run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

        docx.add_paragraph("")

        for paragraph in (document.content or "").split("\n"):
            if paragraph.strip():
                text_paragraph = docx.add_paragraph(paragraph)
                text_paragraph.paragraph_format.space_after = Pt(4)
                text_paragraph.paragraph_format.line_spacing = 1.4

        if document.tags_list:
            docx.add_paragraph("")
            tag_run = docx.add_paragraph().add_run("标签：" + "、".join(document.tags_list))
            tag_run.font.size = Pt(8.5)
            tag_run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    buffer = io.BytesIO()
    docx.save(buffer)
    return buffer.getvalue()


def _to_xlsx(documents: list[Document]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "识别记录"

    headers = ["ID", "标题", "来源", "引擎", "字数", "标签", "收藏", "创建时间", "内容"]
    header_fill = PatternFill("solid", fgColor="1F2937")
    header_font = Font(color="FFFFFF", bold=True, size=10)
    thin = Side(style="thin", color="D1D5DB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=column, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for row_index, document in enumerate(documents, start=2):
        values = [
            document.id,
            document.title,
            document.source_type,
            document.engine,
            document.char_count,
            "、".join(document.tags_list),
            "是" if document.favorite else "否",
            document.created_at,
            document.content,
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=column in (2, 9))
            cell.border = border

    widths = [6, 28, 10, 12, 8, 18, 8, 20, 80]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:I{max(1, len(documents) + 1)}"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _to_zip(documents: list[Document]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = io.StringIO(newline="")
        writer = csv.writer(manifest)
        writer.writerow(["文件名", "标题", "来源", "字数", "创建时间"])
        for index, document in enumerate(documents, start=1):
            name = f"{index:03d}_{slugify(document.title, fallback='document')}.txt"
            body = f"{_document_header(document)}\n\n{document.content}"
            archive.writestr(name, body.encode("utf-8"))
            writer.writerow([name, document.title, document.source_type, document.char_count, document.created_at])
        archive.writestr("manifest.csv", manifest.getvalue().encode("utf-8-sig"))
        archive.writestr(
            "说明.txt",
            (
                "识文台 InsightDesk 导出包\n"
                f"导出时间：{now().isoformat()}\n"
                f"记录数量：{len(documents)}\n"
                "文件编码：UTF-8\n"
            ).encode("utf-8"),
        )
    return buffer.getvalue()


def export(db: Session, ids: list[int], fmt: str) -> ExportResult:
    fmt = (fmt or "txt").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ExportError(f"不支持的导出格式：{fmt}")

    documents = _load(db, ids)
    builders = {
        "txt": _to_txt,
        "csv": _to_csv,
        "md": _to_markdown,
        "docx": _to_docx,
        "xlsx": _to_xlsx,
        "json": _to_json,
        "zip": _to_zip,
    }
    content = builders[fmt](documents)
    return ExportResult(
        filename=_base_filename(documents, fmt),
        content=content,
        media_type=MEDIA_TYPES[fmt],
        count=len(documents),
    )


def content_disposition(filename: str) -> str:
    """构造兼容中文文件名的 Content-Disposition。"""

    from urllib.parse import quote

    fallback = f"insightdesk_export_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    encoded = quote(filename)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
