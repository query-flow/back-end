# QueryFlow API

**Linguagem Natural para SQL** - Plataforma SaaS Multi-Tenant com consultas potencializadas por IA

Backend FastAPI com autenticação JWT, arquitetura em camadas e pipeline LLM baseada em stages para converter perguntas em linguagem natural em queries SQL.

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

# 6. Execute as migrações do banco
python run_migration.py

# 7. Inicie a aplicação
uvicorn app.main:app --reload
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

A aplicação utiliza uma arquitetura em camadas, combinando padrões MVC2 para operações CRUD com camadas adicionais para separação de responsabilidades.

### Estrutura de Camadas

```
app/
├── models/              ← Entidades de Dados (SQLModel)
│   ├── user_model.py
│   ├── organization_model.py
│   ├── document_model.py
│   ├── member_model.py
│   ├── conversation.py
│   └── query_history.py
│
├── schemas/             ← Validação de Request/Response (Pydantic)
│   ├── user_schema.py
│   ├── org_schema.py
│   ├── query_schema.py
│   ├── conversation_schema.py
│   ├── suggestion_schema.py
│   └── chart_schema.py
│
├── dtos/                ← Data Transfer Objects (contextos internos)
│   ├── organization/
│   │   └── context.py   ← OrgContext
│   └── query/
│       ├── context.py   ← QueryExecutionContext
│       ├── intent.py    ← IntentAnalysisResult
│       └── validation.py
│
├── repositories/        ← Camada de Acesso a Dados
│   ├── org_repository.py
│   ├── conversation_repository.py
│   ├── query_history_repository.py
│   ├── clarification_repository.py
│   └── audit_repository.py
│
├── services/            ← Lógica de Negócio
│   ├── query_service.py         ← Orquestração do pipeline de queries
│   ├── enrichment_service.py    ← Geração de insights
│   ├── suggestion_service.py    ← Sugestões inteligentes
│   ├── chart_service.py         ← Geração de gráficos via LLM
│   └── database_service.py      ← Descoberta de databases
│
├── controllers/         ← Endpoints da API (FastAPI routers)
│   ├── auth_controller.py
│   ├── members_controller.py
│   ├── documents_controller.py
│   ├── queries_controller.py
│   ├── conversations_controller.py
│   ├── suggestions_controller.py
│   ├── chart_controller.py
│   └── database_controller.py
│
└── pipeline/            ← Pipeline de Processamento LLM
    ├── llm/
    │   ├── client.py            ← Cliente Azure OpenAI
    │   ├── prompts.py           ← Templates de prompts
    │   └── parsers.py           ← Parsing de respostas LLM
    │
    ├── stages/                  ← Stages do pipeline
    │   ├── intent_analyzer.py   ← Análise de intenção
    │   ├── sql_generator.py     ← Geração de SQL
    │   ├── sql_validator.py     ← Validação e correção
    │   └── result_enricher.py   ← Enriquecimento de resultados
    │
    └── sql/
        ├── catalog.py           ← Introspecção de schemas
        ├── executor.py          ← Execução read-only
        └── protector.py         ← Proteção contra SQL perigoso
```

**Princípios de Design:**
- **Controllers**: Orquestram requisições, delegam para services
- **Services**: Contém lógica de negócio complexa
- **Repositories**: Isolam acesso a dados
- **DTOs**: Transferem dados entre camadas
- **Pipeline**: Processamento especializado de IA/LLM

---

## 🤖 Pipeline de Processamento LLM

### Arquitetura Baseada em Stages

O pipeline converte perguntas em linguagem natural para SQL através de múltiplos estágios de processamento:

```
app/pipeline/
├── llm/
│   ├── client.py                ← Interface Azure OpenAI
│   ├── prompts.py               ← Templates de prompts especializados
│   └── parsers.py               ← Parse JSON/SQL das respostas
│
├── stages/
│   ├── intent_analyzer.py       ← Stage 1: Análise de intenção
│   ├── sql_generator.py         ← Stage 2: Geração de SQL
│   ├── sql_validator.py         ← Stage 3: Validação e correção
│   └── result_enricher.py       ← Stage 4: Insights e visualizações
│
└── sql/
    ├── catalog.py               ← Introspecção do schema do banco
    ├── executor.py              ← Execução segura de SQL
    └── protector.py             ← Proteção contra operações perigosas
```

### 4 Stages Principais

**Stage 1: Intent Analysis** (`intent_analyzer.py`)
- Analisa clareza da pergunta
- Detecta ambiguidades
- Valida compatibilidade com schema
- Retorna: `IntentAnalysisResult` (confidence, is_clear, questions)

**Stage 2: SQL Generation** (`sql_generator.py`)
- Converte pergunta em SQL
- Usa contexto de schema
- Suporta histórico de conversação
- Retorna: SQL válido

**Stage 3: SQL Validation** (`sql_validator.py`)
- Valida segurança do SQL
- Bloqueia operações perigosas (INSERT, UPDATE, DELETE, DROP)
- Adiciona LIMIT se ausente
- Tenta correção via LLM em caso de erro
- Retorna: SQL validado e protegido

**Stage 4: Enrichment** (`result_enricher.py`)
- Gera insights de negócio via LLM
- Cria gráficos automaticamente
- Usa documentos da org como contexto
- Retorna: Insights + visualizações

### Templates de Prompts Especializados

```python
# prompts.py - 5 templates principais

1. build_intent_analysis_prompt()
   → Analisa clareza e valida schema

2. build_nl_to_sql_prompt()
   → Converte NL para SQL

3. build_sql_correction_prompt()
   → Corrige erros de SQL

4. build_insights_prompt()
   → Gera análise de negócio

5. build_schema_selection_prompt()
   → Escolhe schema apropriado
```

---

## 💬 Sistema de Conversações

Suporte a conversas persistentes com contexto histórico.

### Funcionalidades

✅ **Conversas multi-turno** - Mantém contexto entre perguntas
✅ **Histórico completo** - Armazena perguntas, SQL, resultados e insights
✅ **Auto-nomeação** - Gera título automaticamente da primeira pergunta
✅ **Salvamento de dados** - Persiste table_data e insights para revisão

### Tabelas

```sql
-- Conversas
conversations (
    id, org_id, user_id, title,
    created_at, updated_at
)

-- Mensagens da conversa
conversation_messages (
    id, conversation_id,
    role,              -- 'user' ou 'assistant'
    content,           -- Pergunta ou resposta
    sql_executed,      -- SQL gerado (se assistant)
    schema_used,       -- Schema utilizado
    row_count,         -- Número de resultados
    duration_ms,       -- Tempo de execução
    table_data,        -- JSON: {columns: [], rows: []}
    insights,          -- JSON: {summary: str, chart: {...}}
    created_at
)
```

### Endpoints

- `POST /conversations` - Criar nova conversa
- `GET /conversations` - Listar conversas do usuário
- `GET /conversations/{id}` - Obter histórico completo
- `POST /conversations/{id}/ask` - Perguntar dentro de conversa (com contexto)
- `POST /conversations/{id}/messages` - Adicionar mensagem manualmente
- `DELETE /conversations/{id}` - Deletar conversa

---

## 💡 Sistema de Sugestões Inteligentes

Ajuda usuários a descobrirem o que perguntar através de múltiplas camadas de sugestões.

### 3 Camadas de Sugestões

**1. Sugestões Estáticas** (por schema)
- Perguntas pré-configuradas baseadas em schemas conhecidos
- Ex: "Top 10 clientes por vendas", "Produtos mais vendidos"

**2. Sugestões Personalizadas**
- Baseadas no histórico do usuário
- Mostra perguntas que o usuário já fez com sucesso
- Ordenadas por frequência de uso

**3. Sugestões Populares da Organização**
- Perguntas mais comuns na organização
- Filtrável por schema
- Permite descobrir análises feitas por colegas

### Tabela de Histórico

```sql
-- Histórico de queries do usuário
user_query_history (
    id, user_id, org_id,
    pergunta,              -- Pergunta original
    schema_used,           -- Schema utilizado
    sql_executed,          -- SQL gerado
    row_count,             -- Resultados retornados
    duration_ms,           -- Performance
    conversation_id,       -- Conversa relacionada
    created_at
)
```

### Endpoints

- `GET /suggestions` - Obter sugestões (estáticas + personalizadas + populares)
- `GET /suggestions/stats` - Estatísticas do usuário (total queries, schemas mais usados)

---

## 📊 Sistema de Geração de Gráficos

Geração inteligente de visualizações usando LLM para criar configurações D3.js.

### Funcionalidades

✅ **Geração automática** - LLM analisa dados e escolhe melhor visualização
✅ **Edição em linguagem natural** - "Mude para gráfico de pizza", "Deixe azul"
✅ **Múltiplos tipos de gráfico** - Linha, barra, pizza, área, scatter
✅ **Configuração D3.js** - Retorna spec completo para renderização no frontend

### Fluxo de Geração

1. **Frontend envia** colunas + dados + pergunta
2. **LLM analisa** estrutura dos dados
3. **LLM escolhe** tipo de gráfico apropriado
4. **LLM gera** configuração D3.js completa
5. **Frontend renderiza** usando spec retornada

### Endpoints

- `POST /generate-chart` - Gerar configuração inicial de gráfico
- `POST /regenerate-chart` - Editar gráfico existente com instrução NL

**Exemplo de Request:**
```json
{
  "columns": ["month", "revenue"],
  "data": [["Jan", 1000], ["Feb", 1500], ["Mar", 2000]],
  "question": "Mostre a receita por mês",
  "chart_hint": "use linha" // opcional
}
```

**Exemplo de Response:**
```json
{
  "chart_type": "line",
  "title": "Receita por Mês",
  "x_axis": {"field": "month", "label": "Mês"},
  "y_axis": {"field": "revenue", "label": "Receita (R$)"},
  "colors": ["#3b82f6"],
  "legend": false
}
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

-- Conversações persistentes
conversations (
    id, org_id, user_id, title,
    created_at, updated_at
)

-- Mensagens das conversas
conversation_messages (
    id, conversation_id, role, content,
    sql_executed, schema_used,
    row_count, duration_ms,
    table_data,    -- JSON: dados da tabela
    insights,      -- JSON: insights + gráfico
    created_at
)

-- Histórico de queries (para sugestões)
user_query_history (
    id, user_id, org_id,
    pergunta, schema_used, sql_executed,
    row_count, duration_ms, conversation_id,
    created_at
)

-- Sessões de clarificação (expiram em 10 min)
clarification_sessions (
    id, org_id, user_id,
    original_question, schema_name,
    intent_analysis, created_at, expires_at
)

-- Log de auditoria de queries
query_audit (
    id, org_id, schema_used,
    prompt_snip, sql_text,
    row_count, duration_ms, created_at
)
```

---

## 🔐 Fluxo de Autenticação (JWT)

### Membros da Organização

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

### 🔐 Autenticação (4 endpoints)
- `POST /auth/login` - Login de membro da org
- `POST /auth/refresh` - Renovar access token
- `POST /auth/accept-invite` - Aceitar convite e definir senha
- `POST /auth/register` - Registro público (se habilitado)

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

### 📊 Query - NL→SQL (2 endpoints)
**Requer:** Membro da Org

- `POST /perguntar_org` - Converter NL para SQL e executar
- `POST /perguntar_org_stream` - Versão com streaming (Server-Sent Events)

**Request:**
```json
{
  "pergunta": "Quais são os 5 atores que aparecem em mais filmes?",
  "max_linhas": 5,
  "enrich": true,
  "conversation_id": "optional-conv-id"
}
```

**Response (com enrich=true):**
```json
{
  "schema_usado": "sakila",
  "sql": "SELECT actor_id, first_name, last_name, COUNT(*) as film_count...",
  "resultado": {
    "colunas": ["actor_id", "first_name", "last_name", "film_count"],
    "dados": [
      {"actor_id": 107, "first_name": "GINA", "last_name": "DEGENERES", "film_count": 42}
    ]
  },
  "insights": {
    "summary": "GINA DEGENERES é a atriz mais prolífica com 42 filmes...",
    "chart": {
      "chart_type": "bar",
      "title": "Top 5 Atores",
      "x_axis": {"field": "last_name"},
      "y_axis": {"field": "film_count"}
    }
  }
}
```

### 💬 Conversações (6 endpoints)
**Requer:** Membro da Org

- `POST /conversations` - Criar nova conversa
- `GET /conversations` - Listar conversas do usuário
- `GET /conversations/{id}` - Obter histórico completo
- `POST /conversations/{id}/ask` - Perguntar dentro de conversa (usa contexto)
- `POST /conversations/{id}/messages` - Adicionar mensagem
- `DELETE /conversations/{id}` - Deletar conversa

### 💡 Sugestões (2 endpoints)
**Requer:** Membro da Org

- `GET /suggestions` - Obter sugestões (estáticas + personalizadas + populares)
  - Query params: `schema`, `include_personalized`, `include_org_popular`
- `GET /suggestions/stats` - Estatísticas do usuário

### 📊 Gráficos (2 endpoints)
**Requer:** Membro da Org

- `POST /generate-chart` - Gerar configuração de gráfico via LLM
- `POST /regenerate-chart` - Editar gráfico com linguagem natural

### 🗄️ Database Discovery (2 endpoints)
**Público** (para setup inicial)

- `POST /databases/test-connection` - Testar conexão com banco
- `POST /databases/list` - Listar databases disponíveis

---

## 🔄 Fluxo de Query NL→SQL

### Fluxo Principal

1. **Controller recebe a pergunta** e obtém contexto da organização
2. **Carrega histórico de conversa** (se `conversation_id` fornecido)
3. **Stage 1: Intent Analysis**
   - Analisa clareza da pergunta
   - Valida compatibilidade com schema
   - Se ambíguo/incompatível → retorna clarificação
4. **Seleção de Schema**
   - Ranking por sobreposição de termos
   - LLM escolhe se necessário
5. **Stage 2: SQL Generation**
   - Gera SQL a partir da pergunta
   - Usa contexto de schema e histórico
6. **Stage 3: SQL Validation**
   - Valida e protege SQL (bloqueia operações perigosas)
   - Executa no banco da org (read-only)
   - Se erro → LLM corrige e tenta novamente (max 2 tentativas)
7. **Stage 4: Enrichment** (se `enrich=true`)
   - Gera insights via LLM
   - Gera configuração de gráfico
8. **Salva em histórico** e **registra auditoria**
9. **Adiciona à conversa** (se `conversation_id` fornecido)
10. **Retorna resultado** completo

### Streaming (SSE)

O endpoint `/perguntar_org_stream` emite eventos de progresso:

- `started` - Processamento iniciado
- `selecting_schema` - Selecionando schema
- `analyzing_intent` - Analisando intenção
- `generating_sql` - Gerando SQL
- `executing_sql` - Executando no banco
- `enriching` - Gerando insights
- `completed` - Resultado final
- `error` - Erro ocorrido

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
- **Tokens de convite:** Expiram em 7 dias

### Controle de Acesso (RBAC)
- **Nível de plataforma:** `admin` vs `user`
- **Nível de organização:** `org_admin` vs `member`
- **Claims JWT:** `user_id`, `org_id`, `role`, `role_in_org`

---

## 🧪 Testando com Postman

Importe `postman_collection.json` para requests pré-configuradas:
- Salvamento automático de tokens
- Variáveis de ambiente
- Exemplos de requests para todos endpoints

**Fluxo de teste rápido:**
1. Member Login → salva token
2. Query com NL→SQL → veja resultados + insights
3. Criar Conversa → salva conversation_id
4. Perguntar na conversa → veja contexto sendo usado
5. Obter sugestões → veja recomendações

---

## 🎯 Funcionalidades Principais

### 🤖 Pipeline LLM
- ✅ Arquitetura baseada em stages (modular, testável)
- ✅ Análise de intenção com validação de schema
- ✅ Correção automática de SQL (retry com LLM)
- ✅ Type-safe com Pydantic em toda parte
- ✅ 5 templates de prompt especializados
- ✅ Suporte a histórico de conversação

### 🏢 Multi-Tenancy
- ✅ Isolamento de organizações
- ✅ Conexões de banco por org (credenciais criptografadas)
- ✅ Permissões em nível de schema
- ✅ Sistema de convite de membros
- ✅ Controle de acesso baseado em papéis

### 💬 Conversações Persistentes
- ✅ Chat multi-turno com contexto
- ✅ Histórico completo armazenado
- ✅ Auto-nomeação de conversas
- ✅ Salvamento de dados e insights

### 💡 Sugestões Inteligentes
- ✅ Sugestões estáticas por schema
- ✅ Recomendações personalizadas por histórico
- ✅ Perguntas populares da organização
- ✅ Estatísticas de uso

### 📊 Visualizações Inteligentes
- ✅ Geração automática de gráficos via LLM
- ✅ Edição em linguagem natural
- ✅ Configurações D3.js prontas para uso
- ✅ Múltiplos tipos de gráfico

### 📄 Processamento de Documentos
- ✅ Upload de arquivos PDF, DOCX, TXT
- ✅ Extração automática de texto
- ✅ Extração de metadados via LLM (KPIs, metas)
- ✅ Contexto de negócio para insights

### 🔄 Streaming
- ✅ Server-Sent Events (SSE)
- ✅ Progresso em tempo real
- ✅ Eventos tipados e estruturados

---

## 🛠️ Desenvolvimento

### Estrutura do Projeto
```
back-end/
├── app/
│   ├── models/           # Entidades SQLModel
│   ├── schemas/          # Schemas Pydantic (API)
│   ├── dtos/             # DTOs (contextos internos)
│   ├── repositories/     # Acesso a dados
│   ├── services/         # Lógica de negócio
│   ├── controllers/      # Routers FastAPI
│   ├── pipeline/         # Pipeline LLM (stages)
│   ├── core/             # Auth, DB, config, security
│   └── utils/            # Helpers (DB, documentos)
│
├── migrations/           # Migrações SQL
├── .env.example          # Template de ambiente
├── requirements.txt      # Dependências Python
└── postman_collection.json   # Collection de testes da API
```

### Adicionando um Novo Endpoint

1. **Defina schema** em `app/schemas/`
2. **Crie repository** (se necessário) em `app/repositories/`
3. **Crie service** (se lógica complexa) em `app/services/`
4. **Crie rota no controller** em `app/controllers/`
5. **Registre router** em `app/main.py`

Exemplo:
```python
# schemas/exemplo_schema.py
class ExemploRequest(BaseModel):
    nome: str

# services/exemplo_service.py
class ExemploService:
    def processar(self, nome: str):
        return f"Processado: {nome}"

# controllers/exemplo_controller.py
@router.post("/exemplo")
async def criar_exemplo(
    req: ExemploRequest,
    user: AuthedUser = Depends(get_current_user)
):
    service = ExemploService()
    resultado = service.processar(req.nome)
    return {"ok": True, "resultado": resultado}
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
- Confira se o nome do deployment da Azure OpenAI está correto
- Teste a conexão com Azure via `curl`

### Migrações falhando
```bash
# Execute as migrações manualmente
python run_migration.py
```

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
- [ ] Rastreamento de custos por org (uso de tokens LLM)
- [ ] Suporte a PostgreSQL
- [ ] Exportação de conversas (PDF, CSV)
- [ ] Compartilhamento de queries/conversas
- [ ] Dashboard de analytics
- [ ] Rate limiting por org

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
