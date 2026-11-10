-- 强制 utf8mb4，保证列注释等中文元数据不乱码
-- Force utf8mb4 so Chinese column comments are stored correctly
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS agent_review (
  id BIGINT NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) NOT NULL,
  reviewer_id INT NOT NULL,
  decision VARCHAR(16) NOT NULL,
  comment VARCHAR(2000) NOT NULL DEFAULT '',
  edits_json JSON NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_review_run (run_id),
  KEY idx_agent_review_actor_time (reviewer_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_supplement (
  id BIGINT NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) NOT NULL,
  round_number TINYINT NOT NULL,
  user_id INT NOT NULL,
  answers_json JSON NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_agent_supplement_run_round (run_id, round_number),
  KEY idx_agent_supplement_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
