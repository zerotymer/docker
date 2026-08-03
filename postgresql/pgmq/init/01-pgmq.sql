\set ON_ERROR_STOP on
CREATE EXTENSION IF NOT EXISTS pgmq;
SELECT pgmq.create('test_queue');
