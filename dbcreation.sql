-- Create the database for the MUSH server
CREATE DATABASE pymush;
GO

-- Use the newly created database
USE pymush;
GO

-- Create the user_data table to store usernames, passwords, and email addresses
CREATE TABLE user_data (
    user_id INT IDENTITY(1,1) PRIMARY KEY,  -- Unique ID for each user
    username VARCHAR(50) NOT NULL UNIQUE,   -- Username must be unique
    salt VARCHAR(64) NOT NULL,              -- Salt for password hashing
    password_hash VARCHAR(64) NOT NULL,     -- Hashed password
    email VARCHAR(100) NOT NULL             -- User email address
);
GO
