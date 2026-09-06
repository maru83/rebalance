PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    user_name TEXT NOT NULL,
    birth_date TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    current_age INTEGER NOT NULL,
    simulation_years INTEGER NOT NULL DEFAULT 30,
    currency TEXT NOT NULL DEFAULT 'JPY',
    display_unit TEXT NOT NULL DEFAULT 'yen',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id),
    CHECK(current_age >= 0 AND current_age <= 150),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    asset_name TEXT NOT NULL,
    institution_name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    purpose TEXT NOT NULL,
    is_investment INTEGER NOT NULL,
    display_order INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, asset_name),
    CHECK(asset_type IN ('investment_fund', 'government_bond', 'deposit')),
    CHECK(purpose IN ('asset_formation', 'retirement', 'emergency_fund')),
    CHECK(is_investment IN (0, 1)),
    CHECK(is_active IN (0, 1)),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS asset_balances (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    as_of_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(asset_id),
    CHECK(balance >= 0),
    FOREIGN KEY(asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS asset_balance_history (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    balance INTEGER NOT NULL,
    record_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(asset_id, record_date),
    CHECK(balance >= 0),
    FOREIGN KEY(asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS investment_plans (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    plan_name TEXT NOT NULL,
    frequency TEXT NOT NULL,
    amount INTEGER NOT NULL,
    month INTEGER NULL,
    day INTEGER NULL,
    start_date TEXT NULL,
    end_date TEXT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(amount >= 0),
    CHECK(frequency IN ('monthly', 'yearly', 'one_time')),
    CHECK(month IS NULL OR month BETWEEN 1 AND 12),
    CHECK(day IS NULL OR day BETWEEN 1 AND 31),
    CHECK(is_active IN (0, 1)),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS simulation_scenarios (
    id INTEGER PRIMARY KEY,
    scenario_code TEXT NOT NULL UNIQUE,
    scenario_name TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    CHECK(is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS asset_return_assumptions (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    scenario_id INTEGER NOT NULL,
    annual_return_rate REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(asset_id, scenario_id),
    CHECK(annual_return_rate >= -1 AND annual_return_rate <= 1),
    FOREIGN KEY(asset_id) REFERENCES assets(id),
    FOREIGN KEY(scenario_id) REFERENCES simulation_scenarios(id)
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    goal_name TEXT NOT NULL,
    target_age INTEGER NOT NULL,
    target_amount INTEGER NOT NULL,
    purpose TEXT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(target_age > 0),
    CHECK(target_amount >= 0),
    CHECK(is_active IN (0, 1)),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_asset_balances_asset_id
    ON asset_balances(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_balance_history_asset_id
    ON asset_balance_history(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_balance_history_record_date
    ON asset_balance_history(record_date);

CREATE INDEX IF NOT EXISTS idx_investment_plans_user_id
    ON investment_plans(user_id);

CREATE INDEX IF NOT EXISTS idx_investment_plans_asset_id
    ON investment_plans(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_return_assumptions_asset_id
    ON asset_return_assumptions(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_return_assumptions_scenario_id
    ON asset_return_assumptions(scenario_id);

CREATE INDEX IF NOT EXISTS idx_goals_user_id
    ON goals(user_id);

-- MVP initial user
INSERT OR IGNORE INTO users
    (id, user_name, birth_date, created_at, updated_at)
VALUES
    (1, 'ユーザー', NULL, datetime('now'), datetime('now'));

-- MVP scenarios
INSERT OR IGNORE INTO simulation_scenarios
    (scenario_code, scenario_name, display_order, is_active)
VALUES
    ('BEAR', '悲観', 1, 1),
    ('BASE', '標準', 2, 1),
    ('BULL', '楽観', 3, 1);

-- MVP assets
INSERT OR IGNORE INTO assets
    (user_id, asset_name, institution_name, asset_type, purpose, is_investment, display_order, is_active, created_at, updated_at)
VALUES
    (1, 'NISA・オルカン', 'SMBC日興証券', 'investment_fund', 'asset_formation', 1, 1, 1, datetime('now'), datetime('now')),
    (1, '個人向け国債', 'SMBC日興証券', 'government_bond', 'asset_formation', 1, 2, 1, datetime('now'), datetime('now')),
    (1, '企業型DC・オルカン', 'NRK', 'investment_fund', 'retirement', 1, 3, 1, datetime('now'), datetime('now')),
    (1, '定期預金', '三井住友銀行', 'deposit', 'emergency_fund', 0, 4, 1, datetime('now'), datetime('now'));

-- Initial return assumptions.
INSERT OR IGNORE INTO asset_return_assumptions
    (asset_id, scenario_id, annual_return_rate, created_at, updated_at)
SELECT a.id, s.id,
       CASE
           WHEN a.asset_name IN ('NISA・オルカン', '企業型DC・オルカン')
               THEN CASE s.scenario_code WHEN 'BEAR' THEN 0.05 WHEN 'BASE' THEN 0.06 WHEN 'BULL' THEN 0.07 END
           WHEN a.asset_name = '個人向け国債'
               THEN CASE s.scenario_code WHEN 'BEAR' THEN 0.003 WHEN 'BASE' THEN 0.005 WHEN 'BULL' THEN 0.007 END
           WHEN a.asset_name = '定期預金'
               THEN CASE s.scenario_code WHEN 'BEAR' THEN 0.001 WHEN 'BASE' THEN 0.002 WHEN 'BULL' THEN 0.003 END
       END,
       datetime('now'), datetime('now')
FROM assets a
CROSS JOIN simulation_scenarios s
WHERE a.user_id = 1;
