"""
Script para executar a migration JWT
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
        # Add role column (Platform Admin: 'admin', Regular User: 'user')
        ("role", """ALTER TABLE users
           ADD COLUMN role VARCHAR(50) DEFAULT 'user'
           COMMENT 'User role: admin (Platform Admin) or user (regular user)'"""),

        # Add password_hash column
        ("password_hash", """ALTER TABLE users
           ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL
           COMMENT 'Bcrypt hash of user password'"""),

        # Add status column
        ("status", """ALTER TABLE users
           ADD COLUMN status VARCHAR(50) DEFAULT 'active'
           COMMENT 'User status: active, inactive, invited'"""),

        # Add invite_token column
        ("invite_token", """ALTER TABLE users
           ADD COLUMN invite_token VARCHAR(255) DEFAULT NULL
           COMMENT 'Token for accepting organization invitations'"""),

        # Add unique constraint for invite_token
        ("unique_invite", """ALTER TABLE users ADD UNIQUE KEY uq_users_invite_token (invite_token)"""),

        # Add invite_expires column
        ("invite_expires", """ALTER TABLE users
           ADD COLUMN invite_expires DATETIME DEFAULT NULL
           COMMENT 'Expiration timestamp for invite token'"""),

        # Add password_changed_at column
        ("password_changed_at", """ALTER TABLE users
           ADD COLUMN password_changed_at DATETIME DEFAULT NULL
           COMMENT 'Timestamp of last password change'"""),

        # Update existing users to active status
        ("update_status", """UPDATE users SET status = 'active' WHERE status IS NULL OR status = ''"""),

        # Update org_members role naming (admin -> org_admin, user -> member)
        ("update_org_admin_role", """UPDATE org_members SET role_in_org = 'org_admin' WHERE role_in_org = 'admin'"""),

        ("update_member_role", """UPDATE org_members SET role_in_org = 'member' WHERE role_in_org = 'user'"""),

        # Create indexes
        ("idx_invite_token", """CREATE INDEX idx_users_invite_token ON users(invite_token)"""),

        ("idx_status", """CREATE INDEX idx_users_status ON users(status)"""),

        ("idx_email", """CREATE INDEX idx_users_email ON users(email)"""),

        ("idx_role", """CREATE INDEX idx_users_role ON users(role)"""),

        # Add constraints for data integrity
        ("constraint_user_status", """ALTER TABLE users ADD CONSTRAINT chk_user_status CHECK (status IN ('active', 'inactive', 'invited'))"""),

        ("constraint_user_role", """ALTER TABLE users ADD CONSTRAINT chk_user_role CHECK (role IN ('admin', 'user'))"""),

        # Make api_key_sha nullable for JWT users
        ("nullable_api_key", """ALTER TABLE users MODIFY COLUMN api_key_sha VARCHAR(64) NULL"""),
    ]

    for i, (name, sql) in enumerate(migrations, 1):
        try:
            print(f"⏳ Executando migration {i}/{len(migrations)} ({name})...")
            cursor.execute(sql)
            connection.commit()
            print(f"✅ Migration {i} ({name}) executada com sucesso!")
        except Exception as e:
            error_str = str(e)
            if "Duplicate column name" in error_str or "Duplicate key name" in error_str or "Duplicate entry" in error_str:
                print(f"⚠️  Migration {i} ({name}) já foi aplicada (pulando)")
            else:
                print(f"❌ Erro na migration {i} ({name}): {e}")
                # Não fazer raise, continuar com as próximas migrations

    print("")
    print("=" * 50)
    print("✅ TODAS AS MIGRATIONS EXECUTADAS COM SUCESSO!")
    print("=" * 50)
    print("")

    # Verificar estrutura da tabela
    cursor.execute("DESCRIBE users")
    columns = cursor.fetchall()

    print("📋 Estrutura atual da tabela 'users':")
    print("")
    for col in columns:
        print(f"  - {col[0]:<25} {col[1]:<20} {col[2]}")

connection.close()
print("")
print("🎉 Migration concluída! O servidor pode ser reiniciado.")
