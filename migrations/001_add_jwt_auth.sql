-- Migration: Add JWT Authentication Support
-- Date: 2025-10-23
-- Description: Migrates from API key authentication to JWT-based authentication

-- ========================================
-- STEP 1: Add new columns to users table
-- ========================================

-- Add user role column (admin = Platform Admin, user = regular user)
ALTER TABLE users
ADD COLUMN role VARCHAR(50) DEFAULT 'user'
COMMENT 'User role: admin (Platform Admin) or user (regular user)';

-- Add password hash column (required for JWT auth)
ALTER TABLE users
ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL
COMMENT 'Bcrypt hash of user password';

-- Add user status column (active, inactive, invited)
ALTER TABLE users
ADD COLUMN status VARCHAR(50) DEFAULT 'active'
COMMENT 'User status: active, inactive, invited';

-- Add invitation token for member invites
ALTER TABLE users
ADD COLUMN invite_token VARCHAR(255) DEFAULT NULL UNIQUE
COMMENT 'Token for accepting organization invitations';

-- Add invitation expiration timestamp
ALTER TABLE users
ADD COLUMN invite_expires DATETIME DEFAULT NULL
COMMENT 'Expiration timestamp for invite token';

-- Add timestamp for password changes/reset
ALTER TABLE users
ADD COLUMN password_changed_at DATETIME DEFAULT NULL
COMMENT 'Timestamp of last password change';

-- ========================================
-- STEP 2: Update role values in org_members
-- ========================================

-- Update existing role values to new naming convention
UPDATE org_members
SET role_in_org = 'org_admin'
WHERE role_in_org = 'admin';

UPDATE org_members
SET role_in_org = 'member'
WHERE role_in_org = 'user';

-- ========================================
-- STEP 3: Handle existing users
-- ========================================

-- Set all existing users to 'active' status
UPDATE users
SET status = 'active'
WHERE status IS NULL;

-- Note: Existing users will need to reset their password
-- on first login since they don't have password_hash yet.
-- You can implement a "forgot password" flow or force reset.

-- ========================================
-- STEP 4: Create indexes for performance
-- ========================================

-- Index for token lookups during invite acceptance
CREATE INDEX idx_users_invite_token ON users(invite_token);

-- Index for status filtering
CREATE INDEX idx_users_status ON users(status);

-- Index for email lookups during login
CREATE INDEX idx_users_email ON users(email);

-- Index for role filtering (for Platform Admin queries)
CREATE INDEX idx_users_role ON users(role);

-- ========================================
-- STEP 5: Add constraints
-- ========================================

-- Ensure status has valid values
ALTER TABLE users
ADD CONSTRAINT chk_user_status
CHECK (status IN ('active', 'inactive', 'invited'));

-- Ensure role has valid values (admin = Platform Admin, user = regular user)
ALTER TABLE users
ADD CONSTRAINT chk_user_role
CHECK (role IN ('admin', 'user'));

-- ========================================
-- OPTIONAL STEP 6: Remove old API key column (CAREFUL!)
-- ========================================

-- UNCOMMENT ONLY AFTER MIGRATION IS COMPLETE AND TESTED
-- This removes the old API key authentication system

-- ALTER TABLE users DROP COLUMN api_key_sha;

-- ========================================
-- ROLLBACK SCRIPT (in case of issues)
-- ========================================

/*
-- Rollback commands (run only if migration fails)

-- Remove new columns
ALTER TABLE users DROP COLUMN role;
ALTER TABLE users DROP COLUMN password_hash;
ALTER TABLE users DROP COLUMN status;
ALTER TABLE users DROP COLUMN invite_token;
ALTER TABLE users DROP COLUMN invite_expires;
ALTER TABLE users DROP COLUMN password_changed_at;

-- Remove indexes
DROP INDEX idx_users_invite_token ON users;
DROP INDEX idx_users_status ON users;
DROP INDEX idx_users_email ON users;
DROP INDEX idx_users_role ON users;

-- Remove constraints
ALTER TABLE users DROP CONSTRAINT chk_user_status;
ALTER TABLE users DROP CONSTRAINT chk_user_role;

-- Revert role names
UPDATE org_members SET role_in_org = 'admin' WHERE role_in_org = 'org_admin';
UPDATE org_members SET role_in_org = 'user' WHERE role_in_org = 'member';
*/

-- ========================================
-- VERIFICATION QUERIES
-- ========================================

-- After running migration, verify with:
-- SELECT column_name, column_type, is_nullable FROM information_schema.columns WHERE table_name = 'users';
-- SELECT DISTINCT role_in_org FROM org_members;
