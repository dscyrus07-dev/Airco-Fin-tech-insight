-- Airco Insights Database Initialization

CREATE TABLE IF NOT EXISTS merchants (
    id SERIAL PRIMARY KEY,
    normalized_name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    confidence FLOAT DEFAULT 0.95,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255),
    bank_name VARCHAR(100),
    account_type VARCHAR(50),
    date DATE,
    description TEXT,
    debit DECIMAL(15, 2),
    credit DECIMAL(15, 2),
    balance DECIMAL(15, 2),
    category VARCHAR(100),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_bank ON transactions(bank_name);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_merchants_name ON merchants(normalized_name);
