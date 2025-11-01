# PDFS-easy (Streamlit)

Interface web para gerar múltiplas cópias de um PDF editando diretamente os textos de login e senha.

## Como executar localmente

```bash
pip install -r PDFS-easy/requirements.txt
streamlit run PDFS-easy/app.py
```

## Passos na interface

1. Faça upload do PDF modelo original.
2. Envie um arquivo CSV UTF-8 com cabeçalho `output_name,login,password`.
3. Defina a página que contém os campos e escolha se deseja manter os logins/senhas originais ou aplicar novos valores.
4. Clique em **Gerar PDFs** para baixar um arquivo único ou um ZIP com todas as cópias personalizadas.

Quando a opção *Manter login/senha* estiver desativada, os textos são substituídos nativamente, preservando o layout original sem sobreposições. Caso contrário, apenas o nome de saída é alterado.
