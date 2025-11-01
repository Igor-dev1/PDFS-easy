# PDFS-easy (Streamlit)

Interface web para gerar múltiplas cópias de um PDF preenchendo automaticamente campos de login e senha.

## Como executar localmente

```bash
pip install -r PDFS-easy/requirements.txt
streamlit run PDFS-easy/app.py
```

## Passos na interface

1. Faça upload do PDF modelo original.
2. Envie um arquivo CSV UTF-8 com cabeçalho `output_name,login,password`.
3. Ajuste coordenadas, fonte, tamanho e retângulo de limpeza no painel lateral conforme necessário.
4. Clique em **Gerar PDFs** para baixar um arquivo único ou um ZIP com todas as cópias personalizadas.

Os parâmetros correspondem aos mesmos utilizados no script de linha de comando `bulk_pdf_credentials.py`, mantendo o comportamento consistente entre CLI e interface web.
