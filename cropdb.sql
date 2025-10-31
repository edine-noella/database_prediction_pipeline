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

