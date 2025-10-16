# QueryFlow

Bem-vindo! Este serviço expõe uma API **FastAPI** que:

- cadastra empresas (organizações) com **autoconfiguração** (bootstrap público),
- gerencia **usuários** e **vínculos** (RBAC simples),
- conecta no(s) **schema(s)** MySQL do cliente,
- traduz perguntas em linguagem natural → **SQL somente-leitura**,
- retorna **dados** e, opcionalmente, **insights** e **gráficos**,
- permite **extrair metadados de documentos** (PDF/Word/Excel/TXT) para guiar os insights.

---

## Como rodar

```bash
# 1) Criar venv e instalar deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  

# 2) Configurar .env
cp .env.example 

# 3) Subir a API
uvicorn app.main:app --reload
```

### `.env` (exemplo)

```env
# ===== LLM (Azure OpenAI) =====
AZURE_OPENAI_ENDPOINT=https://SUA-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=SEU_TOKEN
AZURE_OPENAI_DEPLOYMENT=gpt-4o_ou_equivalente
AZURE_OPENAI_API_VERSION=2025-01-01-preview
# Coloque 1 para NÃO chamar a LLM (útil dev/local)
DISABLE_AZURE_LLM=0

# ===== Banco de configuração da plataforma =====
CONFIG_DB_URL=mysql+pymysql://root:senha@127.0.0.1:3306/empresas?charset=utf8mb4

# ===== Criptografia (senhas de DBs das orgs) =====
# Gere assim no Python:
#   from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
FERNET_KEY=GERADA_AQUI

# (Opcional) Superadmin seed
SUPERADMIN_NAME=Super Admin
SUPERADMIN_EMAIL=superadmin@minha-plataforma.com
SUPERADMIN_API_KEY=UMA_API_KEY_LONGA_MIN_16_CHARS
```

> ⚠️ **Segurança**
>
> - NUNCA faça commit de chaves reais do Azure nem da `FERNET_KEY`.
> - A senha do banco do cliente é **criptografada** (Fernet) na tabela `org_db_connections`.
> - A API-Key do usuário é **hash (SHA-256)** em `users.api_key_sha`. O usuário guarda sua chave em seguro.

---

## Estrutura do banco `empresas` (configuração da plataforma)

**Schemas e tabelas (MySQL):**

- `orgs`  
  - `id` (PK, string)  
  - `name` (string)  
  - `status` (string: `active`, …)

- `org_db_connections` (1:1 com orgs)  
  - `org_id` (PK, FK → orgs.id)  
  - `driver`, `host`, `port`, `username`  
  - `password_enc` (Fernet)  
  - `database_name` (schema default)  
  - `options_json` (JSON de query params)

- `org_allowed_schemas` (N:1)  
  - `org_id` (PK, FK)  
  - `schema_name` (PK)

- `users`  
  - `id` (PK)  
  - `name`, `email` (unique)  
  - `role` (`admin` | `user`)  
  - `api_key_sha` (unique — **SHA-256** da API-Key do usuário)

- `org_members` (N:N)  
  - `user_id` (PK, FK)  
  - `org_id`  (PK, FK)  
  - `role_in_org` (`member` | `analyst` | `admin_org` …)

- `biz_documents` (documentos de contexto para insights)  
  - `id` (PK autoincrement)  
  - `org_id` (FK)  
  - `title` (string)  
  - `metadata_json` (JSON **detalhado** extraído do arquivo)

- `query_audit` (auditoria de execuções)  
  - `id` (PK autoincrement)  
  - `org_id`, `schema_used`  
  - `prompt_snip`, `sql_text`  
  - `row_count`, `duration_ms`

> **Documentos**: não armazenamos o arquivo nem `storage_url`. Guardamos apenas um **resumo rico** em `metadata_json` (ex.: KPIs, metas, definições de negócio, glossário, regras de agrupamento etc.), que é usado como contexto nos **insights**.

---

## Rotas da API (ordem da jornada)

### 1) **Cadastro público da empresa (Bootstrap)**
**POST** `/public/bootstrap_org`  
Cria **org** + **conexão** + **schemas permitidos** + **admin (usuário)** + vínculo `admin_org`.

**Body (JSON):**
```json
{
  "org_name": "Empresa X",
  "database_url": "mysql+pymysql://user:senha@host:3306/sakila?charset=utf8mb4",
  "allowed_schemas": ["sakila","outro"],
  "admin_name": "Fulano Admin",
  "admin_email": "admin@empresa.com",
  "admin_api_key": "UMA_CHAVE_LONGA_MIN_16"
}
```

**Response 200:**
```json
{
  "org_id": "ab123...",
  "admin_user_id": "cd456...",
  "admin_email": "admin@empresa.com"
}
```

> A `admin_api_key` é **definida pelo próprio admin** (como uma “senha de API”).  
> Armazenamos **apenas o hash** (`api_key_sha`). A chave em si fica com o usuário.

---

### 2) **Login (descobrir seu usuário/orgs)**
**POST** `/login`  
Troca **X-API-Key** por informações do usuário e de quais orgs ele participa.  
**Headers:** `X-API-Key: <sua_api_key>`

**Response 200:**
```json
{
  "user": {"id":"...", "name":"...", "email":"...", "role":"admin"},
  "orgs": [{"org_id":"...", "role_in_org":"admin_org"}]
}
```

---

### 3) **(Admin) Ver dados da org**
**GET** `/admin/orgs/{org_id}`  
**Headers:** `X-API-Key: <api_key de um admin>`

**Response 200:**
```json
{
  "org_id": "...",
  "name": "Empresa X",
  "allowed_schemas": ["sakila"]
}
```

---

### 4) **(Admin) Testar conexão da org**
**POST** `/admin/orgs/{org_id}/test-connection`  
**Headers:** `X-API-Key: <admin>`

**Response 200:**
```json
{
  "ok": true,
  "database_corrente": "sakila",
  "select_1": 1
}
```

---

### 5) **(Admin) Criar usuário**
**POST** `/admin/users`  
Cria um novo usuário na plataforma. (Vínculo à org é feito na rota de **membros**.)

**Headers:** `X-API-Key: <admin>`
**Body:**
```json
{
  "name": "Beltrano",
  "email": "beltrano@empresa.com",
  "role": "user",
  "api_key_plain": "CHAVE_PROPRIA_DO_USUARIO"
}
```

**Response 200:**
```json
{
  "user_id": "....",
  "name": "Beltrano",
  "email": "beltrano@empresa.com",
  "role": "user"
}
```

---

### 6) **(Admin) Vincular usuário à org**
**POST** `/admin/orgs/{org_id}/members`  
Adiciona/atualiza o vínculo e a role do usuário **dentro da org**.

**Headers:** `X-API-Key: <admin>`
**Body:**
```json
{"user_id":"<id_do_usuario>","role_in_org":"member"}
```

**Response 200:**
```json
{"ok": true, "org_id":"...","user_id":"...","role_in_org":"member"}
```

> Para dar permissões administrativas na org, use `role_in_org: "admin_org"`.

---

### 7) **(Admin) Anexar documento & extrair metadados**
**POST** `/admin/orgs/{org_id}/documents/extract`  
Recebe arquivo (PDF/Word/Excel/TXT) + título. Extrai metadados via LLM local/Azure e **salva em `biz_documents`**.

**Headers:** `X-API-Key: <admin>`  
**Form-Data (multipart):**
- `title`: texto curto
- `file`: upload do arquivo

**Response 200:**
```json
{
  "id": 123,
  "org_id": "...",
  "title": "Sakila Contexto 2025",
  "metadata_json": { "KPIs": {...}, "metas": {...}, "glossario": {...}, "exemplos_perguntas": [...], "regras_agrupamento": {...}, "observacoes": "...", "fonte": "...", "periodicidade": "...", "moeda": "...", "datas_referencia": {...} }
}
```

> **Não guardamos o arquivo** nem URL. Mantemos **somente** `metadata_json` detalhado — que alimenta o contexto de **insights**.

---

### 8) **Fazer perguntas (usuário final)**
**POST** `/perguntar_org`  
Escolhe automaticamente o **schema** mais provável, traduz a pergunta para **SQL somente-leitura**, executa, audita e (se `enrich=true`) gera **insights** e, quando aplicável, **gráfico** (PNG em base64) no payload.

**Headers:** `X-API-Key: <user ou admin>`  
**Body:**
```json
{
  "org_id": "<org da qual você é membro>",
  "pergunta": "quais são os 5 atores com mais filmes?",
  "max_linhas": 5,
  "enrich": true
}
```

**Response 200 (exemplo):**
```json
{
  "org_id": "...",
  "schema_usado": "sakila",
  "sql": "SELECT ...",
  "resultado": {
    "colunas": ["actor_id","first_name","last_name","film_count"],
    "dados": [ ... ]
  },
  "insights": {
    "summary": "Texto em linguagem de negócio…",
    "chart": {
      "mime": "image/png",
      "base64": "iVBORw0KGgoAAA..."
    }
  }
}
```

#### Visualizar o gráfico (macOS)

```bash
# Supondo que a resposta foi salva em resp.json
jq -r '.insights.chart.base64 // empty' resp.json > chart.b64
if [ -s chart.b64 ]; then base64 -D chart.b64 > chart.png && open chart.png; fi
```

> **Quando sai gráfico?**  
> Se o resultado tem **exatamente 2 colunas** (categoria + valor) e **a 2ª coluna é numérica**, a API gera um **bar chart** embutido em base64.

---

### 9) **Utilitários (admin)**

- **POST** `/_debug_connect`  
  Faz “ping” em uma `database_url` arbitrária.  
  **Body**:
  ```json
  {"database_url":"mysql+pymysql://user:senha@host:3306/sakila?charset=utf8mb4","pergunta":"(ignorado)","max_linhas":1}
  ```

- **GET** `/_env`  
  Exibe flags de ambiente carregadas (sem segredos). Útil para debug.

---

## Jornada completa (com `curl`)

> Ajuste as variáveis conforme seu ambiente.

```bash
# 0) variáveis úteis
API_KEY_ADMIN="ANA_ADMIN_API_KEY_32+CHARS"

# 1) bootstrap (cria org + admin)
curl -s -X POST http://127.0.0.1:8000/public/bootstrap_org   -H "Content-Type: application/json"   -d '{
    "org_name": "Empresa Demo",
    "database_url": "mysql+pymysql://root:SUA_SENHA_URL_ENCODED@127.0.0.1:3306/sakila?charset=utf8mb4",
    "allowed_schemas": ["sakila"],
    "admin_name": "Ana Admin",
    "admin_email": "ana.admin+demo@empresa.com",
    "admin_api_key": "'"$API_KEY_ADMIN"'"
  }' | tee bootstrap.json

ORG_ID=$(jq -r '.org_id' bootstrap.json)

# 2) (opcional) login com admin para listar suas orgs
curl -s -X POST http://127.0.0.1:8000/login   -H "X-API-Key: $API_KEY_ADMIN" | jq

# 3) ver org
curl -s http://127.0.0.1:8000/admin/orgs/$ORG_ID   -H "X-API-Key: $API_KEY_ADMIN" | jq

# 4) testar conexão
curl -s -X POST http://127.0.0.1:8000/admin/orgs/$ORG_ID/test-connection   -H "X-API-Key: $API_KEY_ADMIN" | jq

# 5) anexar documento e extrair metadados
curl -s -X POST http://127.0.0.1:8000/admin/orgs/$ORG_ID/documents/extract   -H "X-API-Key: $API_KEY_ADMIN"   -F "title=Sakila Contexto 2025"   -F "file=@./sakila_context.txt" | jq

# 6) criar um usuário comum
USER_API_KEY="USER_KEY_32+CHARS"
curl -s -X POST http://127.0.0.1:8000/admin/users   -H "X-API-Key: $API_KEY_ADMIN" -H "Content-Type: application/json"   -d '{
    "name":"Bia Usuária",
    "email":"bia.user@empresa.com",
    "role":"user",
    "api_key_plain":"'"$USER_API_KEY"'"
  }' | tee user.json

USER_ID=$(jq -r '.user_id' user.json)

# 7) vincular esse usuário à org como member
curl -s -X POST http://127.0.0.1:8000/admin/orgs/$ORG_ID/members   -H "X-API-Key: $API_KEY_ADMIN" -H "Content-Type: application/json"   -d '{"user_id":"'"$USER_ID"'","role_in_org":"member"}' | jq

# 8) perguntar (com admin ou com o user)
jq -n --arg org "$ORG_ID"       --arg q "quais são os 5 atores com mais filmes?"       '{org_id:$org, pergunta:$q, max_linhas:5, enrich:true}' > payload.json

curl -s -X POST http://127.0.0.1:8000/perguntar_org   -H "X-API-Key: '"$USER_API_KEY"'"   -H "Content-Type: application/json"   --data-binary @payload.json > resp.json

jq '.sql, .resultado | . as $r | {colunas: $r.colunas, primeiras_5: ($r.dados[:5])}' resp.json

# 9) visualizar gráfico (se houver)
jq -r '.insights.chart.base64 // empty' resp.json > chart.b64
[ -s chart.b64 ] && base64 -D chart.b64 > chart.png && open chart.png
```

---

## Como o roteamento de schema funciona?

1. Indexamos (via `information_schema.COLUMNS`) **tabelas/colunas** dos schemas permitidos.  
2. Comparamos os **tokens** da pergunta com esse índice e ordenamos por **overlap**.  
3. Se houver empate/baixa confiança, consultamos um **palpite do LLM** (opcional).  
4. Executamos no schema preferido; se falhar por “tabela ausente”, tentamos o próximo.

> **Guardrails:** **somente SELECT**, sem DDL/DML. Forçamos `LIMIT` quando ausente e bloqueamos **multi-DB** na query.

---

## Como os insights são gerados?

- Usamos:
  - **dados retornados** (amostra de até 10 linhas e nomes de colunas),
  - **contexto de negócio** de `biz_documents.metadata_json` da org,
  - a **pergunta** do usuário.

- O LLM gera:
  - um **resumo objetivo** (até 8 linhas),
  - **3 próximos passos**.

- **Gráfico**: quando a tabela é “**categoria + valor**” (2 colunas, sendo a 2ª numérica), geramos um **bar chart** (`image/png` em base64).

---

## Roadmap curto

- Paginação/stream de resultados.  
- Histórico por usuário.  
- Políticas por `role_in_org` (limites de linhas, tabelas bloqueadas etc.).  
- Upload múltiplo de documentos + enriquecimento incremental de metadados.

---
