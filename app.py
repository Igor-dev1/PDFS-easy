"""
Interface Streamlit para gerar PDFs com logins e senhas personalizados.

Execute localmente com:
    streamlit run PDFS-easy/app.py
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import streamlit as st
from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject
from reportlab.lib.colors import black, white
from reportlab.pdfgen import canvas


DEFAULT_LOGIN_POS = (170.0, 510.0)
DEFAULT_PASSWORD_POS = (440.0, 510.0)
DEFAULT_ERASE_BOX = (150.0, 495.0, 260.0, 45.0)


@dataclass
class CredentialRow:
    output_name: str
    login: str
    password: str


@dataclass
class OverlayOptions:
    login_pos: Tuple[float, float]
    password_pos: Tuple[float, float]
    font_name: str
    font_size: float
    erase_box: Tuple[float, float, float, float] | None


def load_rows_from_csv(file_buffer: io.BytesIO) -> List[CredentialRow]:
    text_wrapper = io.TextIOWrapper(file_buffer, encoding="utf-8-sig")
    reader = csv.DictReader(text_wrapper)
    required = {"output_name", "login", "password"}
    if reader.fieldnames is None or required - set(reader.fieldnames):
        raise ValueError(
            f"CSV precisa conter as colunas: {', '.join(sorted(required))}. "
            f"Encontrado: {reader.fieldnames!r}"
        )
    rows: List[CredentialRow] = []
    for idx, record in enumerate(reader, start=2):
        output = (record.get("output_name") or "").strip()
        login = (record.get("login") or "").strip()
        password = (record.get("password") or "").strip()
        if not output or not login or not password:
            raise ValueError(
                f"Linha {idx}: campos vazios (output_name='{output}', "
                f"login='{login}', password='{password}')"
            )
        rows.append(CredentialRow(output, login, password))
    if not rows:
        raise ValueError("CSV não possui registros válidos.")
    return rows


def build_overlay(
    page_width: float,
    page_height: float,
    credential: CredentialRow,
    opts: OverlayOptions,
) -> PageObject:
    buffer = io.BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    if opts.erase_box and opts.erase_box[0] >= 0:
        x, y, w, h = opts.erase_box
        canv.setFillColor(white)
        canv.rect(x, y, w, h, stroke=0, fill=1)
    canv.setFillColor(black)
    canv.setFont(opts.font_name, opts.font_size)
    canv.drawString(opts.login_pos[0], opts.login_pos[1], credential.login)
    canv.drawString(opts.password_pos[0], opts.password_pos[1], credential.password)
    canv.save()
    buffer.seek(0)
    overlay_reader = PdfReader(buffer)
    return overlay_reader.pages[0]


def merge_pages(base_page: PageObject, overlay: PageObject) -> PageObject:
    merged = PageObject.create_blank_page(
        width=float(base_page.mediabox.width),
        height=float(base_page.mediabox.height),
    )
    merged.merge_page(base_page)
    merged.merge_page(overlay)
    return merged


def generate_pdfs(
    template_bytes: bytes,
    rows: Iterable[CredentialRow],
    page_index: int,
    opts: OverlayOptions,
) -> List[Tuple[str, bytes]]:
    reader = PdfReader(io.BytesIO(template_bytes))
    if page_index < 0 or page_index >= len(reader.pages):
        raise IndexError(
            f"Página {page_index} inválida. O PDF possui {len(reader.pages)} página(s)."
        )
    template_pages = reader.pages
    page_width = float(template_pages[page_index].mediabox.width)
    page_height = float(template_pages[page_index].mediabox.height)

    outputs: List[Tuple[str, bytes]] = []
    for cred in rows:
        overlay_page = build_overlay(page_width, page_height, cred, opts)
        writer = PdfWriter()
        for idx, src_page in enumerate(template_pages):
            page_copy = PageObject.create_blank_page(
                width=float(src_page.mediabox.width),
                height=float(src_page.mediabox.height),
            )
            page_copy.merge_page(src_page)
            if idx == page_index:
                page_copy = merge_pages(page_copy, overlay_page)
            writer.add_page(page_copy)
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        outputs.append((cred.output_name, output_buffer.getvalue()))
    return outputs


def main() -> None:
    st.set_page_config(page_title="Gerador de PDFs (Login/Senha)", layout="wide")
    st.title("📄 Gerador de PDFs com logins e senhas")

    st.markdown(
        """
        1. Envie o PDF modelo.
        2. Envie um CSV com as colunas `output_name, login, password`.
        3. Ajuste posicionamento, fonte e tamanho se necessário.
        4. Clique em **Gerar PDFs** e baixe o pacote ZIP resultante.
        """
    )

    with st.sidebar:
        st.header("Configurações")
        page_index = st.number_input(
            "Página alvo (índice começando em 0)", min_value=0, value=0, step=1
        )
        login_x = st.number_input("Login X", value=DEFAULT_LOGIN_POS[0], step=1.0)
        login_y = st.number_input("Login Y", value=DEFAULT_LOGIN_POS[1], step=1.0)
        password_x = st.number_input("Senha X", value=DEFAULT_PASSWORD_POS[0], step=1.0)
        password_y = st.number_input("Senha Y", value=DEFAULT_PASSWORD_POS[1], step=1.0)
        font_name = st.selectbox(
            "Fonte",
            options=[
                "Helvetica",
                "Helvetica-Bold",
                "Helvetica-Oblique",
                "Times-Roman",
                "Times-Bold",
                "Courier",
            ],
            index=1,
        )
        font_size = st.number_input("Tamanho da fonte", value=18.0, step=1.0)
        erase_enabled = st.checkbox("Limpar área antiga com retângulo branco", value=True)
        erase_box = DEFAULT_ERASE_BOX if erase_enabled else None
        if erase_enabled:
            erase_x = st.number_input("Caixa X", value=DEFAULT_ERASE_BOX[0], step=1.0)
            erase_y = st.number_input("Caixa Y", value=DEFAULT_ERASE_BOX[1], step=1.0)
            erase_w = st.number_input("Caixa largura", value=DEFAULT_ERASE_BOX[2], step=1.0)
            erase_h = st.number_input("Caixa altura", value=DEFAULT_ERASE_BOX[3], step=1.0)
            erase_box = (erase_x, erase_y, erase_w, erase_h)

    uploaded_pdf = st.file_uploader("PDF modelo", type=["pdf"])
    uploaded_csv = st.file_uploader("Credenciais (CSV)", type=["csv"])

    rows_preview: List[CredentialRow] | None = None
    if uploaded_csv is not None:
        try:
            csv_bytes = io.BytesIO(uploaded_csv.getvalue())
            rows_preview = load_rows_from_csv(csv_bytes)
            st.success(f"{len(rows_preview)} registros carregados do CSV.")
            st.dataframe(
                {
                    "output_name": [row.output_name for row in rows_preview],
                    "login": [row.login for row in rows_preview],
                    "password": [row.password for row in rows_preview],
                }
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erro ao ler CSV: {exc}")

    options = OverlayOptions(
        login_pos=(login_x, login_y),
        password_pos=(password_x, password_y),
        font_name=font_name,
        font_size=font_size,
        erase_box=erase_box,
    )

    if st.button("Gerar PDFs", type="primary"):
        if uploaded_pdf is None:
            st.error("Envie o PDF modelo antes de gerar.")
            return
        if rows_preview is None:
            st.error("CSV inválido ou não carregado.")
            return

        try:
            outputs = generate_pdfs(
                template_bytes=uploaded_pdf.getvalue(),
                rows=rows_preview,
                page_index=int(page_index),
                opts=options,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erro durante a geração: {exc}")
            return

        if not outputs:
            st.warning("Nenhum PDF gerado.")
            return

        if len(outputs) == 1:
            filename, pdf_bytes = outputs[0]
            st.download_button(
                label=f"Baixar PDF: {filename}.pdf",
                data=pdf_bytes,
                file_name=f"{filename}.pdf",
                mime="application/pdf",
            )
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, pdf_bytes in outputs:
                    zf.writestr(f"{filename}.pdf", pdf_bytes)
            st.download_button(
                label=f"Baixar {len(outputs)} PDFs (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="pdfs_personalizados.zip",
                mime="application/zip",
            )


if __name__ == "__main__":
    main()
