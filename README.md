# QueryFlow API

**Linguagem Natural para SQL** - Plataforma SaaS Multi-Tenant com consultas potencializadas por IA

Backend FastAPI com autenticação JWT, arquitetura MVC2 e pipeline LLM baseada em nodes para converter perguntas em linguagem natural em queries SQL.

---

## 🚀 Início Rápido

### Pré-requisitos
- Python 3.10+
- MySQL 8.0+
- Acesso à API Azure OpenAI

### Configuração

```bash
# 1. Clone e entre no diretório
cd back-end

# 2. Crie o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais

# 5. Crie o banco de dados
# MySQL deve estar rodando
mysql -u root -p -e "CREATE DATABASE empresas CHARACTER SET utf8mb4"

# 6. Inicie a aplicação
uvicorn app.main:app --reload

# 7. Crie o admin da plataforma (em outro terminal)
python create_platform_admin.py
```

Acesse a documentação da API: **http://localhost:8000/docs**

---

## ⚙️ Variáveis de Ambiente

```env
# Azure OpenAI (Necessário para recursos de LLM)
AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com
AZURE_OPENAI_API_KEY=sua_chave_api_aqui
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Banco de Dados da Plataforma (armazena orgs, usuários, configurações)
CONFIG_DB_URL=mysql+pymysql://root:senha@localhost:3306/empresas?charset=utf8mb4

# Criptografia (para senhas dos bancos das orgs)
# Gerar: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
FERNET_KEY=sua_chave_fernet_aqui

# JWT Secret (para access/refresh tokens)
# Gerar: import secrets; print(secrets.token_urlsafe(32))
JWT_SECRET_KEY=seu_jwt_secret_aqui
```

⚠️ **Nunca faça commit de credenciais reais no git!**

---

## 🏗️ Arquitetura

### Padrão MVC2 (Operações CRUD)

```
app/
├── models/              ← Modelos de dados com CRUD embutido (SQLModel)
│   ├── user_model.py
│   ├── organization_model.py
│   ├── document_model.py
│   └── member_model.py
│
├── schemas/             ← Validação de Request/Response (Pydantic)
│   ├── user_schema.py
│   ├── org_schema.py
│   ├── query_schema.py
│   ├── member_schema.py
│   └── document_schema.py
│
└── controllers/         ← Endpoints da API (FastAPI routers)
    ├── auth_controller.py
    ├── admin_controller.py
    ├── members_controller.py
    ├── documents_controller.py
    └── queries_controller.py
```

**Princípio de Design:** Controllers coordenam Models e retornam Views (respostas JSON). Sem lógica de negócio nos controllers - apenas orquestração.

---

### Arquitetura Pipeline (IA/LLM)

**Separada do MVC2** - Pipeline baseada em nodes para conversão NL→SQL e enriquecimento.

```
app/pipeline/
├── llm/                           ← Core do Pipeline LLM
│   ├── llm_provider.py            ← Interface cliente de alto nível
│   ├── chains.py                  ← 3 chains pré-definidas
│   ├── cache.py                   ← Cache em memória com TTL
│   │
│   └── nodes/                     ← Nodes individuais do pipeline
│       ├── base.py                ← BaseNode, NodeChain, modelos Pydantic
│       │
│       ├── llm/                   ← Nodes de processamento LLM
│       │   ├── prompt_node.py     ← Constrói prompts a partir de templates
│       │   ├── cache_node.py      ← Verifica/salva cache
│       │   ├── execute_node.py    ← Chama Azure OpenAI
│       │   └── parse_node.py      ← Limpa respostas do LLM
│       │
│       └── processing/            ← Nodes não-LLM
│           ├── chart_node.py      ← Gera gráficos (matplotlib)
│           └── format_node.py     ← Formata resposta final
│
├── catalog.py                     ← Introspecção do schema do banco
└── sql_executor.py                ← Validação e execução de SQL
```

#### Conceito de Pipeline Baseada em Nodes

**BaseNode<InputT, OutputT>**
- Classe genérica com input/output tipados (modelos Pydantic)
- Cada node é uma unidade de processamento isolada
- Logging e tratamento de erros automáticos

**NodeChain**
- Encadeia múltiplos nodes sequencialmente
- Output de um node = Input do próximo
- Exemplo: `[BuildPrompt → CheckCache → ExecuteLLM → Parse → SaveCache]`

**3 Chains Pré-definidas:**

1. **Chain NL→SQL** (5 nodes, cache de 1 hora)
   - Converte linguagem natural para SQL
   - Trata retries com backoff exponencial
   - Usado para: `generate_sql()`, `correct_sql()`, `pick_schema()`

2. **Chain de Insights** (5 nodes, cache de 30 min)
   - Gera insights de negócio a partir dos resultados das queries
   - Processamento apenas com LLM
   - Conecta dados ao contexto de negócio

3. **Chain de Enriquecimento** (3 nodes, sem cache)
   - Enriquecimento completo: Insights + Gráfico + Formatação
   - Combina processamento LLM e matplotlib
   - Retorna: SQL + Dados + Insights + Gráfico (base64)

**5 Templates de Prompt:**
- `nl_to_sql` - Tradução NL→SQL
- `sql_correction` - Correção de erros SQL
- `insights` - Análise de negócio
- `schema_selection` - Escolha do schema apropriado
- `document_metadata` - Extração de KPIs de documentos

---

### Camada de Infraestrutura

```
app/
├── core/
│   ├── auth.py          ← Dependências JWT (get_current_user, require_admin)
│   ├── database.py      ← Gerenciamento de sessão, init_db
│   ├── config.py        ← Settings do .env
│   └── security.py      ← JWT, hash de senhas, criptografia Fernet
│
└── utils/
    ├── database.py      ← Parsing/construção de URLs SQLAlchemy
    └── documents.py     ← Extração de texto (PDF, DOCX, TXT)
```

---

## 🗄️ Schema do Banco de Dados

**Banco da Plataforma** (`empresas`) - Armazena configuração e multi-tenancy

```sql
-- Organizações
orgs (id, name, status)

-- Conexões de banco (senhas criptografadas)
org_db_connections (
    org_id, driver, host, port, username,
    password_enc,  -- Criptografado com Fernet
    database_name, options_json
)

-- Schemas permitidos por org
org_allowed_schemas (org_id, schema_name)

-- Usuários (autenticação JWT)
users (
    id, name, email,
    password_hash,  -- bcrypt
    status, role,
    invite_token, invite_expires
)

-- Membros da organização (N:N)
org_members (user_id, org_id, role_in_org)
-- role_in_org: 'org_admin' | 'member'

-- Documentos de negócio (contexto para insights)
biz_documents (id, org_id, title, metadata_json)

-- Log de auditoria de queries
query_audit (
    id, org_id, schema_used,
    prompt_snip, sql_text,
    row_count, duration_ms, created_at
)
```

---

## 🔐 Fluxo de Autenticação (JWT)

### 1. Admin da Plataforma
```bash
# Criar primeiro admin
python create_platform_admin.py

# Login
POST /auth/admin-login
Body: {"email": "admin@plataforma.com", "password": "admin123"}
Response: {"access_token": "...", "refresh_token": "..."}
```

### 2. Membros da Organização

**Fluxo de Convite:**
```bash
# Org admin convida membro
POST /members/invite
Headers: Authorization: Bearer {admin_token}
Body: {"org_id": "abc123", "email": "usuario@empresa.com", "name": "João Silva"}
Response: {"invite_token": "xyz789"}

# Membro aceita convite
POST /auth/accept-invite
Body: {"invite_token": "xyz789", "password": "novasenha"}

# Membro faz login
POST /auth/login
Body: {"email": "usuario@empresa.com", "password": "novasenha"}
Response: {"access_token": "...", "org_id": "abc123"}
```

**Renovação de Token:**
```bash
POST /auth/refresh
Body: {"refresh_token": "..."}
Response: {"access_token": "..."}
```

---

## 📡 Endpoints da API

### 🔐 Autenticação (5 endpoints)
- `POST /auth/admin-login` - Login de admin da plataforma
- `POST /auth/login` - Login de membro da org
- `POST /auth/refresh` - Renovar access token
- `POST /auth/accept-invite` - Aceitar convite e definir senha
- `POST /auth/register` - Registro público (se habilitado)

### 👨‍💼 Admin - Organizações (5 endpoints)
**Requer:** Admin da Plataforma (`role='admin'`)

- `POST /admin/orgs` - Criar organização
- `GET /admin/orgs/{org_id}` - Obter detalhes da org
- `POST /admin/orgs/{org_id}/test-connection` - Testar conexão DB
- `POST /admin/orgs/{org_id}/members` - Adicionar membro à org
- `DELETE /admin/users/{user_id}` - Deletar usuário da plataforma

### 👥 Gerenciamento de Membros (4 endpoints)
**Requer:** Org Admin (`role_in_org='org_admin'`)

- `POST /members/invite` - Convidar novo membro
- `GET /members/{org_id}` - Listar membros da org
- `PUT /members/{org_id}/{user_id}` - Atualizar papel do membro
- `DELETE /members/{org_id}/{user_id}` - Remover membro

### 📁 Documentos (4 endpoints)
**Requer:** Membro da Org (qualquer papel)

- `GET /documents` - Listar documentos
- `POST /documents` - Criar documento (manual)
- `POST /documents/extract` - Upload e extração (PDF/DOCX/TXT)
- `DELETE /documents/{doc_id}` - Deletar documento

### 📊 Query - NL→SQL (1 endpoint)
**Requer:** Membro da Org

- `POST /perguntar_org` - Converter NL para SQL e executar

**Request:**
```json
{
  "org_id": "abc123",
  "pergunta": "Quais são os 5 atores que aparecem em mais filmes?",
  "max_linhas": 5,
  "enrich": true
}
```

**Response (com enrich=true):**
```json
{
  "org_id": "abc123",
  "schema_usado": "sakila",
  "sql": "SELECT actor_id, first_name, last_name, COUNT(*) as film_count...",
  "resultado": {
    "colunas": ["actor_id", "first_name", "last_name", "film_count"],
    "dados": [
      {"actor_id": 107, "first_name": "GINA", "last_name": "DEGENERES", "film_count": 42},
      ...
    ]
  },
  "insights": {
    "summary": "GINA DEGENERES é a atriz mais prolífica com 42 filmes...",
    "chart": {
      "mime": "image/png",
      "base64": "iVBORw0KGgoAAAANSUhEUgA..."
    }
  }
}
```

---

## 🔄 Fluxo de Query NL→SQL

1. **Controller recebe a pergunta** e obtém schemas permitidos da org
2. **Ranking de schemas** por sobreposição de termos com a pergunta
3. **Se ambíguo:** LLM escolhe o schema mais apropriado
4. **Para cada schema** (em ordem de prioridade):
   - Obtém estrutura do schema (catalog)
   - **LLM gera SQL** a partir da pergunta
   - **Valida e protege SQL** (bloqueia INSERT/UPDATE/DELETE/DROP)
   - **Executa SQL** no banco da org (read-only)
   - **Se erro:** LLM corrige o SQL e tenta novamente
   - **Se sucesso + enrich=true:**
     - Gera insights via LLM
     - Gera gráfico via matplotlib
     - Retorna dados enriquecidos
5. **Retorna resultado** com SQL, dados, insights e gráfico

---

## 🔒 Recursos de Segurança

### Proteção SQL
- **Bloqueia operações perigosas:** INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE
- **Valida existência de tabelas** nos schemas permitidos
- **Adiciona LIMIT** se estiver faltando
- **Previne queries multi-DB**
- **Execução read-only** com rollback automático

### Senhas & Segredos
- **Senhas de usuários:** Hash bcrypt
- **Senhas de DB das orgs:** Criptografia simétrica Fernet
- **Tokens JWT:** Assinatura HS256 com chave secreta
- **API keys nunca armazenadas:** Apenas hashes SHA-256 (legado, descontinuado)

### Controle de Acesso (RBAC)
- **Nível de plataforma:** `admin` (pode gerenciar todas orgs) vs `user`
- **Nível de organização:** `org_admin` (pode convidar/remover) vs `member` (apenas consultar)
- **Claims JWT:** `user_id`, `org_id`, `role`, `role_in_org`

---

## 🧪 Testando com Postman

Importe `postman_collection.json` para 20 requests pré-configuradas:
- Salvamento automático de tokens
- Variáveis de ambiente
- Exemplos de requests para todos endpoints

**Fluxo de teste rápido:**
1. Platform Admin Login → salva token
2. Criar Organização → salva org_id
3. Org Member Login → salva member token
4. Query com NL→SQL → veja resultados + insights

---

## 🎯 Funcionalidades Principais

### 🤖 Pipeline LLM
- ✅ Arquitetura baseada em nodes (modular, testável)
- ✅ Cache em memória com TTL (1h para SQL, 30min para insights)
- ✅ Retry automático com backoff exponencial (3 tentativas)
- ✅ Type-safe com Pydantic em toda parte
- ✅ 5 templates de prompt especializados
- ✅ Correção de erros SQL (retry com correção via LLM)

### 🏢 Multi-Tenancy
- ✅ Isolamento de organizações
- ✅ Conexões de banco por org (credenciais criptografadas)
- ✅ Permissões em nível de schema
- ✅ Sistema de convite de membros
- ✅ Controle de acesso baseado em papéis

### 📊 Enriquecimento de Dados
- ✅ Geração de insights de negócio via LLM
- ✅ Geração automática de gráficos (matplotlib)
- ✅ Análise consciente de contexto usando documentos de negócio
- ✅ Imagens de gráficos codificadas em base64 na resposta

### 📄 Processamento de Documentos
- ✅ Upload de arquivos PDF, DOCX, TXT
- ✅ Extração automática de texto
- ✅ Extração de metadados via LLM (KPIs, metas, timeframe)
- ✅ Contexto de negócio para insights de queries

---

## 📊 Performance

### Efetividade do Cache
- **Primeira query:** ~2-3s (chamada LLM)
- **Query em cache:** ~50-100ms (cache hit)
- **TTL do cache:** 1 hora (SQL), 30 min (insights)

### Estratégia de Retry
- **Max retries:** 3 tentativas
- **Backoff:** 1s, 2s, 4s (exponencial)
- **Pula retry em:** erros 400, 401, 403, 404
- **Retry em:** 429, 5xx, timeouts

---

## 🛠️ Desenvolvimento

### Estrutura do Projeto
```
back-end/
├── app/
│   ├── models/           # Modelos SQLModel com CRUD
│   ├── schemas/          # Schemas de validação Pydantic
│   ├── controllers/      # Routers FastAPI
│   ├── pipeline/         # Pipeline LLM (baseada em nodes)
│   ├── core/             # Auth, DB, config, security
│   └── utils/            # Helpers (DB, documentos)
│
├── migrations/           # Migrações de banco (se houver)
├── .env.example          # Template de ambiente
├── requirements.txt      # Dependências Python
├── create_platform_admin.py  # Script de bootstrap do admin
└── postman_collection.json   # Collection de testes da API
```

### Adicionando um Novo Endpoint

1. **Defina schema** em `app/schemas/`
2. **Adicione método ao model** (se necessário) em `app/models/`
3. **Crie rota no controller** em `app/controllers/`
4. **Registre router** em `app/main.py`

Exemplo:
```python
# schemas/exemplo_schema.py
class ExemploRequest(BaseModel):
    nome: str

# controllers/exemplo_controller.py
@router.post("/exemplo")
async def criar_exemplo(
    req: ExemploRequest,
    user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Controller orquestra Model
    resultado = ExemploModel.create(db=db, nome=req.nome)
    return {"ok": True, "id": resultado.id}
```

---

## 🐛 Solução de Problemas

### "Connection refused" ao MySQL
```bash
# Verifique se o MySQL está rodando
docker ps | grep mysql
# Ou para MySQL local:
brew services list | grep mysql
```

### "Database 'empresas' does not exist"
```bash
mysql -u root -p -e "CREATE DATABASE empresas CHARACTER SET utf8mb4"
```

### Erros de "Module not found"
```bash
# Certifique-se que o ambiente virtual está ativado
source .venv/bin/activate
pip install -r requirements.txt
```

### "Invalid token" / "Token expired"
- Access tokens expiram após 30 minutos
- Use o refresh token para obter novo access token
- Ou faça login novamente

### LLM não funciona
- Verifique se o `.env` tem as credenciais corretas da Azure OpenAI
- Verifique `DISABLE_AZURE_LLM=0` (não 1)
- Confira se o nome do deployment da Azure OpenAI está correto

---

## 📚 Documentação

- **Docs da API:** http://localhost:8000/docs (Swagger UI)
- **Collection Postman:** `postman_collection.json`
- **Código-fonte:** Docstrings inline em todos os módulos

---

## 🔮 Melhorias Futuras

- [ ] Cache Redis (substituir in-memory)
- [ ] Paginação de resultados de queries
- [ ] Notificações via webhook
- [ ] Integração SSO (Google, Microsoft)
- [ ] Histórico de queries por usuário
- [ ] Rastreamento de custos por org (uso de tokens LLM)
- [ ] Suporte a PostgreSQL
- [ ] Tipos avançados de gráficos (Plotly)

---

## 📄 Licença

Licença MIT - Veja o arquivo LICENSE para detalhes

---

## 👥 Contribuindo

Contribuições são bem-vindas! Por favor:
1. Faça fork do repositório
2. Crie branch de feature (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit suas mudanças (`git commit -m 'Adiciona funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

## 🆘 Suporte

Para issues e perguntas:
- Abra uma issue no GitHub
- Consulte a documentação existente
- Revise os exemplos da collection do Postman
