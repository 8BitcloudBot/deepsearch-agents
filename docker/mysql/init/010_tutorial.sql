-- Phase 2 tutorial catalog (idempotent)
-- Preserves existing data volume; re-seeds inside a transaction.

START TRANSACTION;

DROP TABLE IF EXISTS sales_records;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS drugs;

CREATE TABLE drugs (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10,2)
);

CREATE TABLE inventory (
    drug_id INT,
    quantity INT,
    warehouse VARCHAR(20),
    FOREIGN KEY (drug_id) REFERENCES drugs(id)
);

CREATE TABLE sales_records (
    id INT PRIMARY KEY AUTO_INCREMENT,
    drug_id INT,
    sale_date DATE,
    amount INT,
    FOREIGN KEY (drug_id) REFERENCES drugs(id)
);

-- Seed data
INSERT INTO drugs (id, name, category, price) VALUES
    (1, 'Aspirin', 'NSAID', 5.99),
    (2, 'Ibuprofen', 'NSAID', 7.49),
    (3, 'Paracetamol', 'Analgesic', 3.99);

INSERT INTO inventory (drug_id, quantity, warehouse) VALUES
    (1, 100, 'WH-A'),
    (2, 50, 'WH-B'),
    (3, 200, 'WH-A');

INSERT INTO sales_records (drug_id, sale_date, amount) VALUES
    (1, '2026-01-15', 3),
    (2, '2026-01-16', 2),
    (3, '2026-01-17', 5);

COMMIT;

-- Create SELECT-only tutorial_reader account
CREATE USER IF NOT EXISTS 'tutorial_reader'@'%' IDENTIFIED BY 'tutorial_reader';
ALTER USER 'tutorial_reader'@'%' IDENTIFIED BY 'tutorial_reader';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'tutorial_reader'@'%';
GRANT SELECT ON research_copilot.* TO 'tutorial_reader'@'%';
FLUSH PRIVILEGES;
