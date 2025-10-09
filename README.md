# NL→SQL (MySQL) – Multi-DB via FastAPI

Serviço que:
1) recebe uma **URL de conexão MySQL** e uma **pergunta em linguagem natural**;  
2) extrai/condensa o esquema;  
3) usa uma **LLM (Azure OpenAI)** para gerar **SQL (somente SELECT)**;  
4) valida (guard-rails) e **executa** a consulta;  
5) retorna o **SQL final** e os **dados**.

Suporta múltiplos **schemas (databases)** no mesmo servidor. Você pode:
- Enviar a URL **com** ou **sem** schema (`/sakila`).  
- Forçar o schema no **próprio prompt** com frases do tipo:  
  `No schema sakila: ...` ou `schema xtremo: ...` ou `use vendinha ...`

---

## Requisitos

- Python 3.10+ (testado com 3.11/3.12/3.13)  
- MySQL acessível localmente (ou remoto)  
- Bibliotecas Python:
  - `fastapi`, `uvicorn`
  - `SQLAlchemy`
  - `pymysql`
  - `python-dotenv`
  - `httpx`

---

## Instalação

```bash
# 1) Clonar o projeto
git clone <repo>
cd <repo>

# 2) Virtualenv (opcional)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3) Instalar dependências
pip install fastapi uvicorn sqlalchemy pymysql python-dotenv httpx
```

---

## Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto com:

```ini
# Endpoint do seu recurso Azure OpenAI (sem barra no final)
AZURE_OPENAI_ENDPOINT=https://<seu-recurso>.openai.azure.com

# Chave do Azure OpenAI
AZURE_OPENAI_API_KEY=<sua_api_key>

# Nome do deployment (ex: gpt-4o_TechSolucoes)
AZURE_OPENAI_DEPLOYMENT=<nome_do_deployment>

# Versão da API
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Opcional: se quiser desativar a chamada à LLM (responde com SELECT 1)
DISABLE_AZURE_LLM=0
```

> **Importante:** **não** comite o `.env` no repositório.

---

## Executando o servidor

```bash
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000
```

---

## Rotas

### `POST /perguntar`
Gera SQL a partir da pergunta em linguagem natural (NL) + executa o SELECT.

**Body (JSON):**
```json
{
  "database_url": "mysql+pymysql://USER:PASSWORD@HOST:3306/sakila",
  "pergunta": "Quais são os 10 filmes mais alugados? Devolva title e total de alugueis.",
  "max_linhas": 10
}
```

**Observações sobre `database_url`:**
- Formato SQLAlchemy/`pymysql`:  
  `mysql+pymysql://USUARIO:SENHA@HOST:PORTA/<opcional:db>?charset=utf8mb4`
- Caracteres especiais na senha devem ser **URL-encoded** (ex.: `@` → `%40`). Exemplo: `SENHA` = `Minha@Senha` ⇒ use `Minha%40Senha`.
- Pode vir **com** DB (ex. `/sakila`) ou **sem** DB (ex.: `...:3306?charset=utf8mb4`).  
  Se vier **sem** DB, o serviço escolherá com base no prompt/heurística.
- Você pode **sobrepor** o DB via prompt:  
  `No schema sakila: ...` | `schema xtremo: ...` | `use vendinha ...`

**Exemplos (curl) – com placeholders:**

- **Usando `sakila` diretamente na URL:**
```bash
curl -s -X POST http://127.0.0.1:8000/perguntar \
  -H "Content-Type: application/json" \
  -d '{
    "database_url":"mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/sakila",
    "pergunta":"Quais são os 10 filmes mais alugados? Devolva title e total de alugueis.",
    "max_linhas":10
  }' | jq
```

- **URL aponta para `xtremo`, mas o prompt força `sakila`:**
```bash
curl -s -X POST http://127.0.0.1:8000/perguntar \
  -H "Content-Type: application/json" \
  -d '{
    "database_url":"mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/xtremo",
    "pergunta":"No schema sakila: Quais são os 10 filmes mais alugados? Devolva title e total de alugueis.",
    "max_linhas":10
  }' | jq
```

---

### `POST /_debug_connect`
Diagnóstico de conexão (não executa LLM).

**Body (JSON):**
```json
{ "database_url": "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/sakila", "pergunta": "ping" }
```

**Exemplo:**
```bash
curl -s -X POST http://127.0.0.1:8000/_debug_connect \
  -H "Content-Type: application/json" \
  -d '{"database_url":"mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/sakila","pergunta":"ping"}' | jq
```

**Resposta típica:**
```json
{
  "ok": true,
  "database_corrente": "sakila",
  "databases": ["..."],
  "select_1": 1
}
```

---

### `POST /_catalog`
Gera um catálogo **multi-DB** tolerante a erros (lista tabelas/colunas/FKs para cada DB de usuário).  
Restaura o schema original ao final.

**Body (JSON):**
```json
{ "database_url": "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/sakila", "pergunta": "ping" }
```
> Opcional: para **limitar a um DB**, cite no prompt: `schema sakila:`

**Exemplo:**
```bash
curl -s -X POST http://127.0.0.1:8000/_catalog \
  -H "Content-Type: application/json" \
  -d '{"database_url":"mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/sakila","pergunta":"ping"}' | jq
```

---

## Como funciona (resumo técnico)

- Se a URL vier **com** DB: conectamos nele. Se o prompt disser **outro schema**, aplicamos `USE <schema>` após validar que existe.  
- Se a URL vier **sem** DB: conectamos via um DB “neutro” (`information_schema`/`mysql`), escolhemos o schema por heurística/prompt e aplicamos `USE`.
- Extração de esquema é **tolerante por tabela** (loga e ignora tabelas problemáticas).
- Guard-rails:
  - bloqueiam DDL/DML;
  - validam tabelas referenciadas contra **catálogo multi-DB**; se faltar, consultam **`information_schema`**.
  - garantem `LIMIT` quando não especificado.
- Se a execução falhar, fazemos **uma tentativa** de correção via LLM.

---

## Dicas
- Para senhas com `@`, use `%40` (URL-encode).  
- Caso use outro driver (ex. `mysql+mysqlconnector`), ajuste a `database_url` conforme o driver instalado.
- Em produção, use um **usuário read-only** no MySQL.

---

## Licença
MIT
