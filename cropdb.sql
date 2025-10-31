--- Create the cropdb database
CREATE DATABASE cropdb;
USE cropdb;

-- Create the crops table
CREATE TABLE crops (crop_id INT AUTO_INCREMENT PRIMARY KEY,
name VARCHAR(255) NOT NULL UNIQUE
);

-- Create the soil_properties table
CREATE TABLE IF NOT EXISTS soils (
soil_id INT AUTO_INCREMENT PRIMARY KEY,
name VARCHAR(255) NOT NULL UNIQUE
);

-- Create the seedling_stages table
CREATE TABLE IF NOT EXISTS seedling_stages (
stage_id INT AUTO_INCREMENT PRIMARY KEY,
name VARCHAR(255) NOT NULL UNIQUE
);

--Observation table
CREATE TABLE IF NOT EXISTS observations (
observation_id INT AUTO_INCREMENT PRIMARY KEY,
crop_id INT NOT NULL,
soil_id INT NOT NULL,
stage_id INT NOT NULL,
MOI DECIMAL(8,3) NOT NULL,
temp DECIMAL(6,2) NOT NULL,
humidity DECIMAL(5,2) NOT NULL CHECK (humidity BETWEEN 0 AND 100),
result TINYINT NOT NULL,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
CONSTRAINT fk_obs_crop FOREIGN KEY (crop_id) REFERENCES crops(crop_id) ON DELETE RESTRICT ON UPDATE CASCADE,
CONSTRAINT fk_obs_soil FOREIGN KEY (soil_id) REFERENCES soils(soil_id) ON DELETE RESTRICT ON UPDATE CASCADE,
CONSTRAINT fk_obs_stage FOREIGN KEY (stage_id) REFERENCES seedling_stages(stage_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Create observation_audit table
CREATE TABLE IF NOT EXISTS observation_audit (
audit_id INT AUTO_INCREMENT PRIMARY KEY,
observation_id INT,
action ENUM('INSERT','UPDATE','DELETE') NOT NULL,
action_time DATETIME DEFAULT CURRENT_TIMESTAMP,
changed_data JSON,
actor VARCHAR(255)
;

-- Stored Procedure to insert observation
DELIMITER $$
CREATE PROCEDURE sp_insert_observation(
IN p_crop_name VARCHAR(255),
IN p_soil_name VARCHAR(255),
IN p_stage_name VARCHAR(255),
IN p_moi DECIMAL(8,3),
IN p_temp DECIMAL(6,2),
IN p_humidity DECIMAL(5,2),
IN p_result TINYINT
)
BEGIN
DECLARE v_crop_id INT;
DECLARE v_soil_id INT;
DECLARE v_stage_id INT;


-- Validate numeric ranges
IF p_humidity < 0 OR p_humidity > 100 THEN
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'humidity must be between 0 and 100';
END IF;
IF p_temp < -50 OR p_temp > 80 THEN
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'temp out of expected range';
END IF;
IF p_moi < 0 THEN
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'MOI must be non-negative';
END IF;


-- Upsert crop
INSERT INTO crops (name)
VALUES (p_crop_name)
ON DUPLICATE KEY UPDATE crop_id = LAST_INSERT_ID(crop_id);
SET v_crop_id = LAST_INSERT_ID();


-- Upsert soil
INSERT INTO soils (name)
VALUES (p_soil_name)
ON DUPLICATE KEY UPDATE soil_id = LAST_INSERT_ID(soil_id);
SET v_soil_id = LAST_INSERT_ID();


-- Upsert stage
INSERT INTO seedling_stages (name)
VALUES (p_stage_name)
ON DUPLICATE KEY UPDATE stage_id = LAST_INSERT_ID(stage_id);
SET v_stage_id = LAST_INSERT_ID();


-- Insert observation
INSERT INTO observations (crop_id, soil_id, stage_id, MOI, temp, humidity, result)
VALUES (v_crop_id, v_soil_id, v_stage_id, p_moi, p_temp, p_humidity, p_result);


-- Optionally return the new id
SELECT LAST_INSERT_ID() AS new_observation_id;
END$$
DELIMITER ;

