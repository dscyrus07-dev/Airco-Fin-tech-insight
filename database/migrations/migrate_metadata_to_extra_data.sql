-- Migration: Rename 'metadata' column to 'extra_data' across all audit tables
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor)
-- Safe: uses IF EXISTS checks

DO $$
BEGIN
    -- tenants
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='metadata') THEN
        ALTER TABLE tenants RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'tenants: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'tenants: extra_data already exists or metadata not found, skipping';
    END IF;

    -- audit_logs
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='audit_logs' AND column_name='metadata') THEN
        ALTER TABLE audit_logs RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'audit_logs: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'audit_logs: skipping';
    END IF;

    -- batches
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='batches' AND column_name='metadata') THEN
        ALTER TABLE batches RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'batches: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'batches: skipping';
    END IF;

    -- processing_jobs
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='processing_jobs' AND column_name='metadata') THEN
        ALTER TABLE processing_jobs RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'processing_jobs: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'processing_jobs: skipping';
    END IF;

    -- job_events
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='job_events' AND column_name='metadata') THEN
        ALTER TABLE job_events RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'job_events: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'job_events: skipping';
    END IF;

    -- hygiene_reports
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='hygiene_reports' AND column_name='metadata') THEN
        ALTER TABLE hygiene_reports RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'hygiene_reports: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'hygiene_reports: skipping';
    END IF;

    -- report_generation_logs
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='report_generation_logs' AND column_name='metadata') THEN
        ALTER TABLE report_generation_logs RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'report_generation_logs: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'report_generation_logs: skipping';
    END IF;

    -- download_logs
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='download_logs' AND column_name='metadata') THEN
        ALTER TABLE download_logs RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'download_logs: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'download_logs: skipping';
    END IF;

    -- parser_metrics
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='parser_metrics' AND column_name='metadata') THEN
        ALTER TABLE parser_metrics RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'parser_metrics: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'parser_metrics: skipping';
    END IF;

    -- unsupported_format_queue
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='unsupported_format_queue' AND column_name='metadata') THEN
        ALTER TABLE unsupported_format_queue RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'unsupported_format_queue: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'unsupported_format_queue: skipping';
    END IF;

    -- error_logs
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='error_logs' AND column_name='metadata') THEN
        ALTER TABLE error_logs RENAME COLUMN metadata TO extra_data;
        RAISE NOTICE 'error_logs: metadata -> extra_data';
    ELSE
        RAISE NOTICE 'error_logs: skipping';
    END IF;

END $$;
