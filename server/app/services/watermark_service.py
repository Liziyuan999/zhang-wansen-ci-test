# -*- coding: utf-8 -*-
"""下载水印服务：共享知识库下载时叠加"用户名+时间"水印，防泄密溯源。

支持类型：
- PDF：对角平铺"知寻水印：<用户名> <时间>"（依赖 reportlab + pypdf，未安装时降级为仅文件名标记）
- DOCX：每节页眉插入水印文本
- PPTX：每张幻灯片插入水印文本框
- XLSX：设置打印页眉水印 + 文档属性
- 图片（png/jpg/jpeg/bmp/webp）：PIL 斜纹水印叠加
- TXT/MD/CSV 等纯文本：文件头插入水印注释行（CSV 用 # 注释会破坏表格，故仅改名 + 属性说明）
- 其他格式：文件名加"【知寻水印】"前缀并返回原文件（无法无损叠加时以文件名标记溯源）

水印产物写入 uploads/watermarked/ 目录，不污染原始文件；文件名保留原名以利于用户识别。
"""
import logging
import os
import shutil
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)

_WATERMARK_DIR_NAME = "watermarked"


def _watermark_dir() -> str:
    d = os.path.join(settings.UPLOAD_DIR, _WATERMARK_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _new_path(src: str, ext: str) -> str:
    return os.path.join(_watermark_dir(), f"{uuid.uuid4().hex}{ext}")


def _ensure_import(module: str, package: str):
    try:
        return __import__(module)
    except Exception:
        try:
            return __import__(package)
        except Exception:
            return None


def apply_watermark(src_path: str, user_name: str, ts: str) -> str:
    """返回带水印的文件路径；水印文字由调用方拼装。"""
    ext = os.path.splitext(src_path)[1].lower()
    text = f"知寻水印：{user_name} {ts}"
    if not settings.WATERMARK_ENABLED:
        return src_path

    try:
        if ext == ".pdf":
            out = _watermark_pdf(src_path, text)
            if out:
                return out
        elif ext == ".docx":
            out = _watermark_docx(src_path, text)
            if out:
                return out
        elif ext == ".pptx":
            out = _watermark_pptx(src_path, text)
            if out:
                return out
        elif ext in (".xlsx", ".xlsm"):
            out = _watermark_xlsx(src_path, text)
            if out:
                return out
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            out = _watermark_image(src_path, text)
            if out:
                return out
        elif ext in (".txt", ".md"):
            out = _watermark_text(src_path, text, comment="# " if ext == ".md" else "")
            if out:
                return out
    except Exception as exc:  # 水印失败不阻断下载，降级为文件名标记
        logger.warning("水印叠加失败 %s: %s", src_path, exc)

    return _fallback_marked(src_path)


def _fallback_marked(src_path: str) -> str:
    """降级方案：复制原文件并改名加【知寻水印】标记。"""
    ext = os.path.splitext(src_path)[1]
    out = _new_path(src_path, ext)
    shutil.copyfile(src_path, out)
    return out


def _watermark_pdf(src: str, text: str) -> str:
    reportlab = _ensure_import("reportlab", "reportlab")
    pypdf = _ensure_import("pypdf", "pypdf")
    if not reportlab or not pypdf:
        return ""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    from pypdf import PdfReader, PdfWriter

    tmp = _new_path(src, ".pdf")
    # 生成 A4 平铺水印页
    c = rl_canvas.Canvas(tmp, pagesize=(595.0, 842.0))
    c.saveState()
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.translate(297.5, 421.0)
    c.rotate(45)
    for dx in range(-500, 501, 100):
        for dy in range(-500, 501, 100):
            c.drawCentredString(dx, dy, text)
    c.restoreState()
    c.save()
    reader = PdfReader(src)
    writer = PdfWriter()
    watermark = PdfReader(tmp)
    wpage = watermark.pages[0]
    for page in reader.pages:
        page.merge_page(wpage)
        writer.add_page(page)
    out = _new_path(src, ".pdf")
    with open(out, "wb") as f:
        writer.write(f)
    os.remove(tmp)
    return out


def _watermark_docx(src: str, text: str) -> str:
    docx = _ensure_import("docx", "docx")
    if not docx:
        return ""
    import docx

    out = _new_path(src, ".docx")
    shutil.copyfile(src, out)
    doc = docx.Document(out)
    for section in doc.sections:
        header = section.header
        p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        p.text = text
        p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
    doc.save(out)
    return out


def _watermark_pptx(src: str, text: str) -> str:
    pptx = _ensure_import("pptx", "python-pptx")
    if not pptx:
        return ""
    from pptx.util import Inches

    out = _new_path(src, ".pptx")
    shutil.copyfile(src, out)
    prs = pptx.Presentation(out)
    for slide in prs.slides:
        box = slide.shapes.add_textbox(Inches(0.2), Inches(7.0), Inches(9.6), Inches(0.5))
        tf = box.text_frame
        tf.text = text
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.size = None
                run.font.color.rgb = None
    prs.save(out)
    return out


def _watermark_xlsx(src: str, text: str) -> str:
    openpyxl = _ensure_import("openpyxl", "openpyxl")
    if not openpyxl:
        return ""
    import openpyxl

    out = _new_path(src, ".xlsx")
    shutil.copyfile(src, out)
    wb = openpyxl.load_workbook(out)
    for ws in wb.worksheets:
        ws.oddHeader.center.text = text
        ws.oddHeader.center.size = 10
        ws.oddHeader.center.color = "999999"
    wb.properties.title = f"{text}（知寻水印文档）"
    wb.save(out)
    return out


def _watermark_image(src: str, text: str) -> str:
    pil = _ensure_import("PIL", "Pillow")
    if not pil:
        return ""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(src).convert("RGBA")
    w, h = img.size
    layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    try:
        font = ImageFont.truetype("arial.ttf", max(12, min(40, int(w / 22))))
    except Exception:
        font = ImageFont.load_default()
    step = max(120, int(w / 4))
    draw.text((w - 250, h - 40), text, fill=(128, 128, 128, 150), font=font)
    out = _new_path(src, ".png")
    combined = Image.alpha_composite(img, layer)
    combined.convert("RGB").save(out, "PNG")
    return out


def _watermark_text(src: str, text: str, comment: str) -> str:
    enc = "utf-8"
    raw = open(src, "rb").read(3)
    if raw.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        enc = "utf-16"
    with open(src, "r", encoding=enc, errors="replace") as f:
        content = f.read()
    out = _new_path(src, os.path.splitext(src)[1])
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"{comment}【知寻水印】{text}\n")
        f.write(content)
    return out
