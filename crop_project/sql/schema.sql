-- SQLite compatible schema for crop monitoring system

-- Create the crops table
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Create the soil_types table
CREATE TABLE IF NOT EXISTS soil_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Create the growth_stages table
CREATE TABLE IF NOT EXISTS growth_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Create the readings table
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id INTEGER,
    soil_name TEXT,
    growth_stage_id INTEGER,
    moi REAL,
    temp REAL,
    humidity REAL,
    result INTEGER NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE SET NULL,
    FOREIGN KEY (growth_stage_id) REFERENCES growth_stages(id) ON DELETE SET NULL
);

-- Create a table for logging
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Note: SQLite doesn't support stored procedures or triggers in the same way as MySQL
-- The application should handle this logic instead
