-- Migration: Simplify Roles - Remove Platform Admin
-- Date: 2025-11-04
-- Description: Migra de 3 roles (Platform Admin, Org Admin, Member) para 2 roles (Admin, Member)
--              Remove o conceito de Platform Admin para modelo self-service

-- ========================================
-- STEP 1: Update role_in_org (org_admin → admin)
-- ========================================

-- Renomear 'org_admin' para 'admin' na tabela org_members
UPDATE org_members
SET role_in_org = 'admin'
WHERE role_in_org = 'org_admin';

-- ========================================
-- STEP 2: Remove user role system
-- ========================================

-- Drop constraint that validates user role
ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_user_role;

-- Drop index on role column
DROP INDEX IF EXISTS idx_users_role ON users;

-- Drop role column (Platform Admin concept removed)
ALTER TABLE users DROP COLUMN IF EXISTS role;

-- ========================================
-- VERIFICATION QUERIES
-- ========================================

-- After running migration, verify with:
-- SELECT DISTINCT role_in_org FROM org_members;  -- Should only show 'admin' and 'member'
-- DESCRIBE users;  -- Should NOT have 'role' column

-- ========================================
-- ROLLBACK SCRIPT (in case of issues)
-- ========================================

/*
-- Rollback commands (run only if migration fails)

-- Re-add role column
ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user'
COMMENT 'User role: admin (Platform Admin) or user (regular user)';

-- Re-create index
CREATE INDEX idx_users_role ON users(role);

-- Re-create constraint
ALTER TABLE users ADD CONSTRAINT chk_user_role
CHECK (role IN ('admin', 'user'));

-- Revert role naming
UPDATE org_members SET role_in_org = 'org_admin' WHERE role_in_org = 'admin';
*/
