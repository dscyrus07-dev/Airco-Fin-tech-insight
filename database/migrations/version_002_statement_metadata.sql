-- =========================================================================
-- Airco Insights — Statement Metadata
-- One row per processed bank statement, summarising channel/salary/loan
-- metrics extracted from the classified transactions.
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.statement_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id)          ON DELETE CASCADE,
    user_id   UUID NOT NULL REFERENCES public.users(id)            ON DELETE CASCADE,
    job_id    UUID NOT NULL REFERENCES public.processing_jobs(id)  ON DELETE CASCADE,

    -- Header
    chitid          VARCHAR(100),               -- mirrors job_id for external consumers
    filename        VARCHAR(500),
    bankname        VARCHAR(100),
    accountno       VARCHAR(50),                -- masked
    formatidentify  VARCHAR(100),
    startdate       DATE,
    enddate         DATE,
    nooftransactions INTEGER NOT NULL DEFAULT 0,

    -- Salary
    havesalary        BOOLEAN NOT NULL DEFAULT FALSE,
    noofsalarycredit  INTEGER NOT NULL DEFAULT 0,
    amtofsalarycredit NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Loan repayment (debit)
    hasloanrepayment    BOOLEAN NOT NULL DEFAULT FALSE,
    noofloanrepayments  INTEGER NOT NULL DEFAULT 0,
    amtofloanrepayments NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Loan credit (disbursement)
    loancredit       BOOLEAN NOT NULL DEFAULT FALSE,
    noofloancredits  INTEGER NOT NULL DEFAULT 0,
    amtofloancredits NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Credit aggregates
    noofcredits              INTEGER NOT NULL DEFAULT 0,
    amtofcredits             NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofcashdeposits         INTEGER NOT NULL DEFAULT 0,
    amtofcashdeposits        NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofupicredits           INTEGER NOT NULL DEFAULT 0,
    amtofupicredits          NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofneft_imps_credits    INTEGER NOT NULL DEFAULT 0,
    amtofneft_imps_credits   NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofnetbanking_credits   INTEGER NOT NULL DEFAULT 0,
    amtofnetbanking_credits  NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Debit aggregates
    noofdebits               INTEGER NOT NULL DEFAULT 0,
    amtofdebits              NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofcashwithdrawals      INTEGER NOT NULL DEFAULT 0,
    amtofcashwithdrawals     NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofupidebits            INTEGER NOT NULL DEFAULT 0,
    amtofupidebits           NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofneft_imps_debits     INTEGER NOT NULL DEFAULT 0,
    amtofneft_imps_debits    NUMERIC(18,2) NOT NULL DEFAULT 0,
    noofnetbanking_debits    INTEGER NOT NULL DEFAULT 0,
    amtofnetbanking_debits   NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Free-form extras (salary recurrence months, classifier version, etc.)
    extra JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT statement_metadata_job_id_unique UNIQUE (job_id)
);

CREATE INDEX IF NOT EXISTS idx_statement_metadata_tenant     ON public.statement_metadata(tenant_id);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_user       ON public.statement_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_chitid     ON public.statement_metadata(chitid);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_bankname   ON public.statement_metadata(bankname);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_accountno  ON public.statement_metadata(accountno);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_format     ON public.statement_metadata(formatidentify);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_havesalary ON public.statement_metadata(havesalary);
CREATE INDEX IF NOT EXISTS idx_statement_metadata_hasloan    ON public.statement_metadata(hasloanrepayment);

-- Row Level Security
ALTER TABLE public.statement_metadata ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS statement_metadata_tenant_isolation ON public.statement_metadata;
CREATE POLICY statement_metadata_tenant_isolation
  ON public.statement_metadata
  FOR ALL
  TO authenticated
  USING (tenant_id::text = (current_setting('request.jwt.claims', true)::json ->> 'tenant_id'))
  WITH CHECK (tenant_id::text = (current_setting('request.jwt.claims', true)::json ->> 'tenant_id'));

DROP POLICY IF EXISTS statement_metadata_service_role ON public.statement_metadata;
CREATE POLICY statement_metadata_service_role
  ON public.statement_metadata
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
