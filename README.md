# Cadastro de Unidades com Exportação e Envio de Planilha

Este projeto é uma aplicação Flask para cadastro de unidades, geração de planilha Excel e envio automático por e-mail.

## 🚀 Funcionalidades

- Cadastro de unidade com diversas informações e múltiplas medidas por tipo.
- Geração automática de planilha Excel (.xlsx) com os dados da unidade.
- Envio automático da planilha para `comercialservico2025@gmail.com`.

## ✅ Configuração no Render

1. Crie um serviço **Web** no [Render](https://render.com).
2. Faça upload dos arquivos deste pacote.
3. Configure as variáveis de ambiente:
   - `EMAIL_USER`
   - `EMAIL_PASS`
   - `EMAIL_SERVER` → smtp.gmail.com
   - `EMAIL_PORT` → 587
4. O Render detectará `render.yaml` e `Procfile` automaticamente.

## 🌐 Uso

- Acesse a aplicação.
- Preencha o formulário na `/` para cadastrar uma unidade.
- Preencha `Localidade - Unidade` no campo de exportação e clique em **Exportar e Enviar**.