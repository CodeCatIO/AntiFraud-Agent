-- ============================================================
--  V003: Seed roles referenced by RoleEnum
--  V003：补齐 RoleEnum 中声明但初始化脚本缺失的角色
--  Idempotent: safe to run on existing volumes.
-- ============================================================

-- 强制 utf8mb4，避免角色中文名双重编码
-- Force utf8mb4 so Chinese role names are stored correctly
SET NAMES utf8mb4;

INSERT INTO `sys_role` (`name`, `description`, `flag`)
SELECT '研判员', '线索研判与工单处理', 'ROLE_WORKER'
WHERE NOT EXISTS (SELECT 1 FROM `sys_role` WHERE `flag` = 'ROLE_WORKER');

INSERT INTO `sys_role` (`name`, `description`, `flag`)
SELECT '运维审核', '人工复核与运维管理', 'ROLE_MAINTENANCE'
WHERE NOT EXISTS (SELECT 1 FROM `sys_role` WHERE `flag` = 'ROLE_MAINTENANCE');
