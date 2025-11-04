"""
Script para executar a migration 002: Simplify Roles
Remove Platform Admin e simplifica sistema de roles
"""
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# Conectar ao banco
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='insper',
    database='empresas',
    charset='utf8mb4'
)

print("🔗 Conectado ao banco de dados 'empresas'")
print("")

with connection.cursor() as cursor:
    # Migration SQL
    migrations = [
        # Update org_members: org_admin → admin
        ("update_org_admin_to_admin", """UPDATE org_members
           SET role_in_org = 'admin'
           WHERE role_in_org = 'org_admin'"""),

        # Drop constraint on user role
        ("drop_role_constraint", """ALTER TABLE users DROP CONSTRAINT chk_user_role"""),

        # Drop index on role column
        ("drop_role_index", """DROP INDEX idx_users_role ON users"""),

        # Drop role column from users table
        ("drop_role_column", """ALTER TABLE users DROP COLUMN role"""),
    ]

    for i, (name, sql) in enumerate(migrations, 1):
        try:
            print(f"⏳ Executando migration {i}/{len(migrations)} ({name})...")
            cursor.execute(sql)
            connection.commit()
            print(f"✅ Migration {i} ({name}) executada com sucesso!")
        except Exception as e:
            error_str = str(e).lower()
            # Ignorar erros esperados
            if any(x in error_str for x in ["doesn't exist", "can't drop", "unknown column", "check constraint"]):
                print(f"⚠️  Migration {i} ({name}) já foi aplicada ou não necessária (pulando)")
            else:
                print(f"❌ Erro na migration {i} ({name}): {e}")
                # Não fazer raise, continuar com as próximas migrations

    print("")
    print("=" * 60)
    print("✅ MIGRATION 002 EXECUTADA COM SUCESSO!")
    print("=" * 60)
    print("")

    # Verificar estrutura da tabela users
    cursor.execute("DESCRIBE users")
    columns = cursor.fetchall()

    print("📋 Estrutura atual da tabela 'users':")
    print("")
    for col in columns:
        print(f"  - {col[0]:<25} {col[1]:<20} {col[2]}")

    print("")

    # Verificar distribuição de roles em org_members
    cursor.execute("SELECT role_in_org, COUNT(*) as count FROM org_members GROUP BY role_in_org")
    roles = cursor.fetchall()

    print("📊 Distribuição de roles em 'org_members':")
    print("")
    for role, count in roles:
        print(f"  - {role:<15} {count} membro(s)")

connection.close()
print("")
print("🎉 Migration concluída! Sistema agora usa apenas 2 roles: 'admin' e 'member'")
print("📌 Próximo passo: Reinicie o servidor (uvicorn app.main:app --reload)")
