-- ============================================
-- AI反诈风控预警系统 v2.0 - 数据库初始化脚本
-- Database Initialization Script v2.0
-- ============================================
-- 包含：基础表 + 安全功能表 + 索引
-- Includes: base tables + security tables + indexes
--
-- 全新安装直接跑这个脚本即可
-- For fresh installation: run this script directly
--
-- 已有v1数据库升级：请使用 upgrade_v2.sql
-- For upgrading from v1: use upgrade_v2.sql
-- ============================================

-- 强制连接使用 utf8mb4，避免容器内 mysql 客户端默认 latin1 导致种子中文双重编码
-- Force utf8mb4 on the init connection; the containerized mysql client may default to latin1
SET NAMES utf8mb4;

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `anti_fraud` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `anti_fraud`;

-- ===== 保留原有的基础表 =====

-- 字典表
DROP TABLE IF EXISTS `sys_dict`;
CREATE TABLE `sys_dict` (
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '名称',
  `value` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '内容',
  `type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '类型'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

INSERT INTO `sys_dict` VALUES ('shield', 'el-icon-shield', 'icon');
INSERT INTO `sys_dict` VALUES ('document', 'el-icon-document', 'icon');
INSERT INTO `sys_dict` VALUES ('house', 'el-icon-house', 'icon');
INSERT INTO `sys_dict` VALUES ('menu', 'el-icon-menu', 'icon');
INSERT INTO `sys_dict` VALUES ('s-custom', 'el-icon-s-custom', 'icon');
INSERT INTO `sys_dict` VALUES ('s-grid', 'el-icon-s-grid', 'icon');
INSERT INTO `sys_dict` VALUES ('warning', 'el-icon-warning', 'icon');
INSERT INTO `sys_dict` VALUES ('user', 'el-icon-user', 'icon');
INSERT INTO `sys_dict` VALUES ('microphone', 'el-icon-microphone', 'icon');
INSERT INTO `sys_dict` VALUES ('picture', 'el-icon-picture-outline', 'icon');
INSERT INTO `sys_dict` VALUES ('stamp', 'el-icon-stamp', 'icon');
INSERT INTO `sys_dict` VALUES ('link', 'el-icon-link', 'icon');
INSERT INTO `sys_dict` VALUES ('tickets', 'el-icon-tickets', 'icon');
INSERT INTO `sys_dict` VALUES ('data-analysis', 'el-icon-data-analysis', 'icon');
INSERT INTO `sys_dict` VALUES ('connection', 'el-icon-connection', 'icon');
INSERT INTO `sys_dict` VALUES ('search', 'el-icon-search', 'icon');

-- 菜单表
DROP TABLE IF EXISTS `sys_menu`;
CREATE TABLE `sys_menu` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `name` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '名称',
  `path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '路径',
  `icon` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '图标',
  `description` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '描述',
  `pid` int(11) NULL DEFAULT NULL COMMENT '父级id',
  `page_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '页面路径',
  `sort_num` int(11) NULL DEFAULT NULL COMMENT '排序',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 100 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 菜单数据 - AI反诈系统
INSERT INTO `sys_menu` VALUES (10, '首页仪表盘', '/dashboard', 'el-icon-data-analysis', '系统概览', NULL, 'Dashboard', 1);
INSERT INTO `sys_menu` VALUES (20, '智能检测', NULL, 'el-icon-warning', '多模态检测', NULL, NULL, 2);
INSERT INTO `sys_menu` VALUES (21, '文本检测', '/textDetect', 'el-icon-document', '文本诈骗检测', 20, 'TextDetect', 3);
INSERT INTO `sys_menu` VALUES (22, '语音检测', '/voiceDetect', 'el-icon-microphone', '语音伪造检测', 20, 'VoiceDetect', 4);
INSERT INTO `sys_menu` VALUES (23, '图像检测', '/imageDetect', 'el-icon-picture-outline', '图像伪造检测', 20, 'ImageDetect', 5);
INSERT INTO `sys_menu` VALUES (30, '安全工具', NULL, 'el-icon-s-grid', '水印与存证', NULL, NULL, 6);
INSERT INTO `sys_menu` VALUES (31, '水印工具', '/watermarkTool', 'el-icon-stamp', '数字水印嵌入提取', 30, 'WatermarkTool', 7);
INSERT INTO `sys_menu` VALUES (32, '存证溯源', '/blockchainCert', 'el-icon-link', '区块链存证', 30, 'BlockchainCert', 8);
INSERT INTO `sys_menu` VALUES (40, '检测记录', '/detectRecords', 'el-icon-tickets', '历史检测记录', NULL, 'DetectRecords', 9);
INSERT INTO `sys_menu` VALUES (50, '系统管理', NULL, 'el-icon-s-grid', NULL, NULL, NULL, 10);
INSERT INTO `sys_menu` VALUES (51, '用户管理', '/user', 'el-icon-user', NULL, 50, 'User', 11);
INSERT INTO `sys_menu` VALUES (52, '角色管理', '/role', 'el-icon-s-custom', NULL, 50, 'Role', 12);
INSERT INTO `sys_menu` VALUES (53, '菜单管理', '/menu', 'el-icon-menu', NULL, 50, 'Menu', 13);

-- 角色表
DROP TABLE IF EXISTS `sys_role`;
CREATE TABLE `sys_role` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '名称',
  `description` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '描述',
  `flag` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '标识',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

INSERT INTO `sys_role` VALUES (1, '管理员', '系统管理员', 'ROLE_ADMIN');
INSERT INTO `sys_role` VALUES (2, '普通用户', '普通用户', 'ROLE_USER');

-- 角色菜单关联表
DROP TABLE IF EXISTS `sys_role_menu`;
CREATE TABLE `sys_role_menu` (
  `role_id` int(11) NOT NULL COMMENT '角色id',
  `menu_id` int(11) NOT NULL COMMENT '菜单id',
  PRIMARY KEY (`role_id`, `menu_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 管理员拥有所有菜单
INSERT INTO `sys_role_menu` VALUES (1, 10);
INSERT INTO `sys_role_menu` VALUES (1, 20);
INSERT INTO `sys_role_menu` VALUES (1, 21);
INSERT INTO `sys_role_menu` VALUES (1, 22);
INSERT INTO `sys_role_menu` VALUES (1, 23);
INSERT INTO `sys_role_menu` VALUES (1, 30);
INSERT INTO `sys_role_menu` VALUES (1, 31);
INSERT INTO `sys_role_menu` VALUES (1, 32);
INSERT INTO `sys_role_menu` VALUES (1, 40);
INSERT INTO `sys_role_menu` VALUES (1, 50);
INSERT INTO `sys_role_menu` VALUES (1, 51);
INSERT INTO `sys_role_menu` VALUES (1, 52);
INSERT INTO `sys_role_menu` VALUES (1, 53);

-- 普通用户拥有检测和工具菜单
INSERT INTO `sys_role_menu` VALUES (2, 10);
INSERT INTO `sys_role_menu` VALUES (2, 20);
INSERT INTO `sys_role_menu` VALUES (2, 21);
INSERT INTO `sys_role_menu` VALUES (2, 22);
INSERT INTO `sys_role_menu` VALUES (2, 23);
INSERT INTO `sys_role_menu` VALUES (2, 30);
INSERT INTO `sys_role_menu` VALUES (2, 31);
INSERT INTO `sys_role_menu` VALUES (2, 32);
INSERT INTO `sys_role_menu` VALUES (2, 40);

-- 用户表
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '用户名',
  `password` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '密码',
  `nickname` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '昵称',
  `email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '邮箱',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '电话',
  `address` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '地址',
  `avatar_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '头像',
  `role` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '角色',
  `roleid` int(11) NULL DEFAULT NULL COMMENT '角色编号',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 10 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 默认管理员账号 admin/AntiFraud@2026（首次登录后请立即修改）
INSERT INTO `sys_user` VALUES (1, 'admin', '925c3f34c53ea9b5a99c01e901c11318', '管理员', 'admin@antifraud.com', '13800138000', NULL, NULL, 'ROLE_ADMIN', 1, NOW());
INSERT INTO `sys_user` VALUES (2, 'user', 'e10adc3949ba59abbe56e057f20f883e', '普通用户', 'user@antifraud.com', NULL, NULL, NULL, 'ROLE_USER', 2, NOW());

-- ===== 新增：检测记录表 =====
DROP TABLE IF EXISTS `detection_record`;
CREATE TABLE `detection_record` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `user_id` int(11) NULL DEFAULT NULL COMMENT '用户id',
  `type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '检测类型(text/voice/image/composite)',
  `input_content` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '输入内容摘要',
  `risk_score` int(11) NULL DEFAULT 0 COMMENT '风险分数(0-100)',
  `risk_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '风险等级(低风险/中风险/高风险)',
  `detail` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '详细结果JSON',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'completed' COMMENT '任务状态(pending/processing/completed/failed)',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_type` (`type`),
  INDEX `idx_risk_level` (`risk_level`),
  INDEX `idx_create_time` (`create_time`)
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '检测记录表';

-- ===== 新增：存证记录表 =====
DROP TABLE IF EXISTS `cert_record`;
CREATE TABLE `cert_record` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `user_id` int(11) NULL DEFAULT NULL COMMENT '用户id',
  `content_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'SHA-256哈希',
  `block_index` int(11) NULL DEFAULT NULL COMMENT '区块索引',
  `content` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '存证内容摘要',
  `certify_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '存证时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_content_hash` (`content_hash`),
  INDEX `idx_user_id` (`user_id`)
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '区块链存证记录表';

-- ===== 新增：文件表（用于文件上传管理）=====
DROP TABLE IF EXISTS `sys_file`;
CREATE TABLE `sys_file` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '文件名',
  `type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '文件类型',
  `size` bigint(20) NULL DEFAULT NULL COMMENT '文件大小',
  `url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '下载链接',
  `md5` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'md5',
  `is_delete` tinyint(1) NULL DEFAULT 0 COMMENT '是否删除',
  `enable` tinyint(1) NULL DEFAULT 1 COMMENT '是否启用',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '文件表';

-- ===== 新增：操作日志表（审计功能）=====
DROP TABLE IF EXISTS `sys_operation_log`;
CREATE TABLE `sys_operation_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` int(11) NULL DEFAULT NULL COMMENT '操作人ID',
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '操作人用户名',
  `module` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '模块 e.g. user, detect, system',
  `type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '操作类型 e.g. login, create, update, delete',
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '操作描述',
  `method` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'HTTP请求方式 GET/POST/PUT/DELETE',
  `url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '请求URL',
  `ip` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '客户端IP',
  `params` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '请求参数JSON',
  `result` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '操作结果 success/fail',
  `error_msg` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '错误信息',
  `cost_time` bigint(20) NULL DEFAULT NULL COMMENT '执行耗时(毫秒)',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_module` (`module`),
  INDEX `idx_create_time` (`create_time`)
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT = '操作日志表';

SET FOREIGN_KEY_CHECKS = 1;
