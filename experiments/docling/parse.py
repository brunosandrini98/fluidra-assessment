"""Docling parse experiment for pool_qa.

Converts PDF pages 13, 94, 97 of data/user_manual.pdf with Docling and writes
markdown + JSON per page, to compare against what pypdf extracts. Throwaway
spike script; touches only experiments/docling/.

Run:
    uv run --no-project --python 3.12 --index-strategy unsafe-best-match \
        --extra-index-url https://download.pytorch.org/whl/cpu --with docling==2.128.0 \
        python experiments/docling/parse.py [--full-ocr] [--describe-pictures]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from importlib.metadata import version
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, smolvlm_picture_description
from docling.document_converter import DocumentConverter, PdfFormatOption

SCRIPT_DIR = Path(__file__).resolve().parent
PDF_PATH = SCRIPT_DIR.parent.parent / "data" / "user_manual.pdf"
PAGES = (13, 94, 97)
VLM_PAGES = (94, 97)


def convert_page(converter: DocumentConverter, page: int):
    result = converter.convert(str(PDF_PATH), page_range=(page, page))
    return result.document


def timed_convert(converter: DocumentConverter, page: int):
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    doc = convert_page(converter, page)
    return doc, time.perf_counter() - wall_start, time.process_time() - cpu_start


def write_outputs(doc, stem: str) -> None:
    (SCRIPT_DIR / f"{stem}.md").write_text(doc.export_to_markdown(traverse_pictures=True))
    (SCRIPT_DIR / f"{stem}.json").write_text(json.dumps(doc.export_to_dict(), indent=2))


def run_default() -> None:
    converter = DocumentConverter()
    convert_page(converter, 13)  # warm-up, untimed
    for page in PAGES:
        doc, wall, cpu = timed_convert(converter, page)
        write_outputs(doc, f"p{page}")
        print(f"page {page}: wall={wall:.2f}s cpu={cpu:.2f}s")


def picture_descriptions_section(doc) -> str:
    # docling_core's markdown serializer skips picture descriptions once
    # `item.meta` is set: it only reflows legacy `item.annotations`, and only
    # the doctags/html serializers call serialize_meta(). SmolVLM writes to
    # `item.meta.description`, so export_to_markdown drops it silently.
    # Append it ourselves.
    lines = [
        f"- `{pic.self_ref}` (page {pic.prov[0].page_no if pic.prov else '?'}): {pic.meta.description.text}"
        for pic in doc.pictures
        if pic.meta and pic.meta.description
    ]
    if not lines:
        return ""
    return "\n\n## Picture descriptions (SmolVLM)\n\n" + "\n".join(lines) + "\n"


def write_vlm_outputs(doc, stem: str) -> None:
    markdown = doc.export_to_markdown(traverse_pictures=True) + picture_descriptions_section(doc)
    (SCRIPT_DIR / f"{stem}.md").write_text(markdown)


def run_describe_pictures() -> None:
    opts = PdfPipelineOptions()
    opts.do_picture_description = True
    opts.picture_description_options = smolvlm_picture_description
    opts.generate_picture_images = True
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    convert_page(converter, 94)  # warm-up, untimed; also downloads the SmolVLM weights
    for page in VLM_PAGES:
        doc, wall, cpu = timed_convert(converter, page)
        write_vlm_outputs(doc, f"p{page}_vlm")
        print(f"page {page} (vlm): wall={wall:.2f}s cpu={cpu:.2f}s")


def run_full_ocr() -> None:
    opts = PdfPipelineOptions()
    opts.ocr_options.force_full_page_ocr = True
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    convert_page(converter, 13)  # warm-up, untimed
    doc, wall, cpu = timed_convert(converter, 13)
    (SCRIPT_DIR / "p13_full_ocr.md").write_text(doc.export_to_markdown(traverse_pictures=True))
    print(f"page 13 (full OCR): wall={wall:.2f}s cpu={cpu:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-ocr", action="store_true")
    parser.add_argument("--describe-pictures", action="store_true")
    args = parser.parse_args()

    print(f"docling version: {version('docling')}")
    print(f"cpu count: {os.cpu_count()}")

    if args.describe_pictures:
        run_describe_pictures()
    elif args.full_ocr:
        run_full_ocr()
    else:
        run_default()


if __name__ == "__main__":
    main()
