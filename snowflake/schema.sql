-- Run this entire file in Snowflake's web UI (Worksheets tab)

-- 1. Create database and schema
CREATE DATABASE IF NOT EXISTS HL_CREDIT_RISK;
USE DATABASE HL_CREDIT_RISK;
CREATE SCHEMA IF NOT EXISTS PUBLIC;
USE SCHEMA PUBLIC;

-- 2. Create warehouse (compute resource)
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

USE WAREHOUSE COMPUTE_WH;

-- 3. Create the main loans table
CREATE OR REPLACE TABLE LOANS_RAW (
    loan_amnt         FLOAT,
    funded_amnt       FLOAT,
    term              VARCHAR(20),
    int_rate          FLOAT,
    grade             VARCHAR(5),
    sub_grade         VARCHAR(5),
    annual_inc        FLOAT,
    dti               FLOAT,
    delinq_2yrs       FLOAT,
    fico_range_low    FLOAT,
    fico_range_high   FLOAT,
    open_acc          FLOAT,
    pub_rec           FLOAT,
    revol_util        FLOAT,
    total_acc         FLOAT,
    loan_status       VARCHAR(100),
    purpose           VARCHAR(50),
    home_ownership    VARCHAR(20),
    addr_state        VARCHAR(5),
    issue_d           VARCHAR(20),
    target            INTEGER
);

-- Verify table was created
SHOW TABLES;