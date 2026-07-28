-- Phase 0 health check table
-- This file is idempotent: uses CREATE TABLE IF NOT EXISTS and INSERT IGNORE.

CREATE TABLE IF NOT EXISTS phase_0_health (
    status VARCHAR(20) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO phase_0_health (status) VALUES ('ok');
