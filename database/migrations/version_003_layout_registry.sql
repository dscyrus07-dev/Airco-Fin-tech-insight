-- =========================================================================
-- Airco Insights - Layout registry (slice 3C)
-- Centralised, versioned layout configuration for the shared extraction
-- engine. config_json holds a serialised LayoutSpec
-- (backend/app/services/statement_engine/extraction/spec_codec.py).
-- Platform-level reference data: no tenant_id, read-only for tenants.
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.banks (
    id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code   VARCHAR(50)  NOT NULL UNIQUE,        -- bank_key, e.g. 'hdfc'
    name   VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.layout_families (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(100) NOT NULL UNIQUE,   -- e.g. 'column_split_drcr_header_first_page'
    name        VARCHAR(200) NOT NULL,
    engine_type VARCHAR(50)  NOT NULL DEFAULT 'coordinate_table',
    version     INTEGER NOT NULL DEFAULT 1,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.bank_layouts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id          UUID NOT NULL REFERENCES public.banks(id)           ON DELETE CASCADE,
    layout_family_id UUID NOT NULL REFERENCES public.layout_families(id) ON DELETE RESTRICT,
    layout_id        VARCHAR(200) NOT NULL UNIQUE,   -- LayoutSpec.layout_id
    priority         INTEGER NOT NULL DEFAULT 100,   -- lower wins when several headers match
    config_json      JSONB   NOT NULL,
    config_version   INTEGER NOT NULL DEFAULT 1,
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bank_layouts_bank ON public.bank_layouts (bank_id, active, priority);
