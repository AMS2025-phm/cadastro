# Cadastro de Unidades com Exportação e Envio de Planilha

Este projeto é uma aplicação Flask para cadastro de unidades, geração de planilha Excel e envio automático por e-mail.

## 🚀 Funcionalidades

- Cadastro de unidade com diversas informações e medidas.
- Geração automática de planilha Excel (.xlsx) com os dados da unidade.
- Envio automático da planilha para `comercialservico2025@gmail.com`.

## 📦 Estrutura do Projeto

- `app.py` → Código principal Flask.
- `templates/index.html` → Formulário de cadastro com medidas dinâmicas.
- `.env.example` → Exemplo de variáveis de ambiente.
- `requirements.txt` → Dependências.
- `render.yaml` → Configuração para deploy no Render.
- `Procfile` → Arquivo para rodar com Gunicorn.

## ✅ Configuração no Render

1. Crie um novo serviço **Web** no [Render](https://render.com).

2. Faça upload de todos os arquivos deste pacote.

3. Configure as seguintes **variáveis de ambiente**:

| Variável       | Descrição                                |
|----------------|------------------------------------------|
| `EMAIL_USER`   | Seu e-mail remetente (ex: seu@gmail.com) |
| `EMAIL_PASS`   | Senha de app do Gmail                    |
| `EMAIL_SERVER` | `smtp.gmail.com`                         |
| `EMAIL_PORT`   | `587`                                    |

⚠️ Se estiver usando Gmail: ative a verificação em duas etapas e gere uma **senha de app**.

4. O Render detectará automaticamente `render.yaml` e `Procfile`.

5. O serviço será iniciado automaticamente com Gunicorn.

## 🌐 Uso

- Acesse a aplicação pelo link gerado pelo Render.
- Preencha o formulário na `/` para cadastrar uma unidade.
- Preencha `Localidade - Unidade` no campo de exportação e clique em **Exportar e Enviar**.
- O sistema enviará automaticamente o Excel para `comercialservico2025@gmail.com`.

## 📝 Tecnologias

- Python 3.x
- Flask
- OpenPyXL
- Gunicorn

## 🤝 Contribuição

Para melhorias ou sugestões, fique à vontade para enviar pull requests ou abrir issues.

---

Desenvolvido para automação de cadastros e envio de relatórios via e-mail.