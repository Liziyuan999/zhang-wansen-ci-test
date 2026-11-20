# -*- coding: utf-8 -*-
"""文档解析：读取各类文件文本并生成重叠切片。"""
import hashlib
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import docx  # python-docx
except Exception:  # pragma: no cover
    docx = None

try:
    import openpyxl
except Exception:  # pragma: no cover
    openpyxl = None

try:
    import pptx  # python-pptx
except Exception:  # pragma: no cover
    pptx = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(path: str) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(path)
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"【第{i}页】\n{text}")
    return "\n".join(parts)


def _extract_docx(path: str) -> str:
    if docx is None:
        return ""
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())


def _extract_xlsx(path: str, file_type: str) -> tuple[str, dict | None]:
    if openpyxl is None:
        return "", None
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet_info: dict[str, Any] = {"sheets": []}
    parts = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = [str(v) if v is not None else "" for v in row]
            rows.append(vals)
        sheet_info["sheets"].append({"name": ws.title, "rows": len(rows), "cols": ws.max_column})
        parts.append(f"【工作表:{ws.title}】")
        for r in rows:
            parts.append(" | ".join(r))
    if file_type in ("et", "xls"):
        # xls 由 read_file 兼容层处理，这里返回空文本由上层标记
        wb.close()
        return _clean("\n".join(parts)), sheet_info
    wb.close()
    return _clean("\n".join(parts)), sheet_info


def _extract_pptx(path: str) -> str:
    if pptx is None:
        return ""
    prs = pptx.Presentation(path)
    parts = []
    for i, slide in enumerate(prs.slides, start=1):
        texts = [shp.text for shp in slide.shapes if hasattr(shp, "text") and shp.text.strip()]
        parts.append(f"【第{i}页】\n" + "\n".join(texts))
    return _clean("\n".join(parts))


def _extract_txt(path: str) -> str:
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def parse_document(path: str, file_type: str) -> tuple[str, dict | None]:
    """返回 (text, extra)。extra 含 excel_sheet_info / ocr_content。"""
    file_type = file_type.lower()
    if file_type == "pdf":
        text = _extract_pdf(path)
        return text, None
    if file_type == "docx":
        return _extract_docx(path), None
    if file_type in ("xlsx", "et"):
        text, sheet_info = _extract_xlsx(path, file_type)
        return text, {"excel_sheet_info": sheet_info}
    if file_type == "pptx":
        return _extract_pptx(path), None
    # csv 为分隔符纯文本，复用编码自适应读取（utf-8 / gbk / utf-8-sig）
    if file_type in ("txt", "md", "csv"):
        return _extract_txt(path), None
    if file_type in ("png", "jpg", "jpeg"):
        return _ocr_image(path), None
    return "", None


def _ocr_image(path: str) -> str:
    """图片 OCR：优先 PaddleOCR；未安装时返回占位说明。"""
    try:
        from paddleocr import PaddleOCR  # type: ignore

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = ocr.ocr(path, cls=True)
        lines = []
        for res in result or []:
            for item in res or []:
                lines.append(item[1][0])
        return "\n".join(lines)
    except Exception as exc:  # pragma: no cover
        logger.warning("PaddleOCR 未安装或不可用: %s", exc)
        return "【图片内容 OCR 不可用：未安装 paddleocr】"


def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """重叠切片：优先按段落/句号边界切分，支持重叠。"""
    if not text.strip():
        return []
    text = text.strip()
    units = re.split(r"(?<=[。！？!?；;\n])", text)
    units = [u.strip() for u in units if u.strip()]
    if not units:
        units = [text]
    chunks: list[str] = []
    current = ""
    for unit in units:
        while len(unit) > chunk_size:
            if current:
                chunks.append(current)
            current = ""
            chunks.append(unit[:chunk_size])
            unit = unit[chunk_size:]
        if len(current) + len(unit) > chunk_size and current:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = tail + unit
        else:
            current += unit
    if current:
        chunks.append(current)
    return chunks
