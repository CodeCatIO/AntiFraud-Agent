-- 强制 utf8mb4，保证列注释等中文元数据不乱码
-- Force utf8mb4 so Chinese column comments are stored correctly
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS agent_case (
  id BIGINT NOT NULL AUTO_INCREMENT,
  case_no CHAR(36) NOT NULL,
  user_id INT NOT NULL,
  content TEXT NOT NULL,
  source VARCHAR(50) NOT NULL DEFAULT 'user_input',
  status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_case_no (case_no),
  KEY idx_agent_case_user_status (user_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_run (
  id BIGINT NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) NOT NULL,
  case_id BIGINT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
  last_event_seq INT NOT NULL DEFAULT 0,
  config_version VARCHAR(64) NOT NULL DEFAULT 'i1',
  input_hash CHAR(64) NOT NULL,
  result_json JSON NULL,
  error_code VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_run_id (run_id),
  KEY idx_agent_run_case_created (case_id, created_at),
  KEY idx_agent_run_status_updated (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_event (
  id BIGINT NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) NOT NULL,
  event_seq INT NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload_json JSON NOT NULL,
  occurred_at DATETIME(3) NOT NULL,
  received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_event_run_seq (run_id, event_seq),
  KEY idx_agent_event_run_received (run_id, received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
