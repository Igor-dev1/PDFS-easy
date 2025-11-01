"""
Interface Streamlit para gerar PDFs com logins e senhas editadas diretamente no conteúdo.

Execute localmente com:
    streamlit run PDFS-easy/app.py
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import streamlit as st
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
)

PLACEHOLDER_PATTERN = re.compile(
    rb"/C2_0 19\.2 Tf\s+0\.6375 0 0 0\.6375 157\.2973 535\.605 Tm\s*\[[^\]]+\]TJ\s*372\.799 0 Td\s*\[[^\]]+\]TJ",
    re.S,
)


@dataclass
class CredentialRow:
    output_name: str
    login: str
    password: str


def load_rows_from_csv(
    file_buffer: io.BytesIO,
    allow_empty_credentials: bool = False,
) -> List[CredentialRow]:
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
        if not output:
            raise ValueError(f"Linha {idx}: output_name vazio.")
        if not allow_empty_credentials and (not login or not password):
            raise ValueError(f"Linha {idx}: login/senha vazios.")
        rows.append(CredentialRow(output, login, password))

    if not rows:
        raise ValueError("CSV não possui registros válidos.")
    return rows


def escape_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def ensure_font(page, writer: PdfWriter, font_name: str = "/FSP") -> None:
    resources = page.get("/Resources")
    if isinstance(resources, IndirectObject):
        resources = resources.get_object()
    if resources is None:
        resources = DictionaryObject()
        page[NameObject("/Resources")] = resources

    fonts = resources.get("/Font")
    if fonts is None:
        fonts = DictionaryObject()
        resources[NameObject("/Font")] = fonts
    elif isinstance(fonts, IndirectObject):
        fonts = fonts.get_object()
        resources[NameObject("/Font")] = fonts

    if NameObject(font_name) in fonts:
        return

    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    font_ref = writer._add_object(font_dict)
    fonts[NameObject(font_name)] = font_ref


def update_page_text(page, writer: PdfWriter, login: str, password: str) -> None:
    ensure_font(page, writer)

    contents = page.get("/Contents")
    if contents is None:
        raise RuntimeError("Página não possui conteúdo.")

    if isinstance(contents, ArrayObject):
        data = b"".join(obj.get_object().get_data() for obj in contents)
    else:
        data = contents.get_object().get_data()

    replacement = (
        "/FSP 19.2 Tf\n"
        "0.6375 0 0 0.6375 157.2973 535.605 Tm\n"
        f"({escape_pdf(login)}) Tj\n"
        "372.799 0 Td\n"
        f"({escape_pdf(password)}) Tj"
    ).encode("latin1")

    new_data, count = PLACEHOLDER_PATTERN.subn(replacement, data)
    if count == 0:
        raise RuntimeError("Não foi possível localizar o bloco de login/senha no PDF.")

    stream = DecodedStreamObject()
    stream.set_data(new_data)
    encoded = stream.flate_encode()
    page[NameObject("/Contents")] = writer._add_object(encoded)


def generate_pdfs(
    template_bytes: bytes,
    rows: Iterable[CredentialRow],
    page_index: int,
    keep_credentials: bool,
) -> List[Tuple[str, bytes]]:
    reader = PdfReader(io.BytesIO(template_bytes))
    if page_index < 0 or page_index >= len(reader.pages):
        raise IndexError(
            f"Página {page_index} inválida. O PDF possui {len(reader.pages)} página(s)."
        )
    template_pages = reader.pages

    outputs: List[Tuple[str, bytes]] = []
    for cred in rows:
        writer = PdfWriter()
        for idx, src_page in enumerate(template_pages):
            page_copy = src_page.copy()
            if idx == page_index and not keep_credentials:
                update_page_text(page_copy, writer, cred.login, cred.password)
            writer.add_page(page_copy)
        buffer = io.BytesIO()
        writer.write(buffer)
        outputs.append((cred.output_name, buffer.getvalue()))
    return outputs


def main() -> None:
    st.set_page_config(page_title="Gerador de PDFs (Login/Senha)", layout="wide")
    st.title("📄 Gerador de PDFs com logins e senhas")

    st.markdown(
        """
        1. Envie o PDF modelo.
        2. Envie um CSV com as colunas `output_name, login, password`.
        3. Escolha se deseja manter os logins/senhas originais ou aplicar novos valores.
        4. Clique em **Gerar PDFs** e faça o download.
        """
    )

    with st.sidebar:
        st.header("Configurações")
        page_index = st.number_input(
            "Página alvo (índice começando em 0)", min_value=0, value=0, step=1
        )
        keep_credentials = st.checkbox(
            "Manter login/senha originais do PDF",
            value=False,
            help="Ative para gerar cópias apenas com nomes diferentes.",
        )

    uploaded_pdf = st.file_uploader("PDF modelo", type=["pdf"])
    uploaded_csv = st.file_uploader("Credenciais (CSV)", type=["csv"])

    rows_preview: List[CredentialRow] | None = None
    if uploaded_csv is not None:
        try:
            csv_bytes = io.BytesIO(uploaded_csv.getvalue())
            rows_preview = load_rows_from_csv(
                csv_bytes,
                allow_empty_credentials=keep_credentials,
            )
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

    if st.button("Gerar PDFs", type="primary"):
        if uploaded_pdf is None:
            st.error("Envie o PDF modelo antes de gerar.")
            return
        if rows_preview is None:
            st.error("CSV inválido ou não carregado.")
            return

        if not keep_credentials:
            for row in rows_preview:
                if not row.login or not row.password:
                    st.error("Login/senha vazios não são permitidos quando a opção está desativada.")
                    return

        try:
            outputs = generate_pdfs(
                template_bytes=uploaded_pdf.getvalue(),
                rows=rows_preview,
                page_index=int(page_index),
                keep_credentials=keep_credentials,
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
