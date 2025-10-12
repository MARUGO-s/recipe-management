-- 1. 取引先テーブルを新規作成
CREATE TABLE public.suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2. cost_masterテーブルにsupplier_id列を追加
ALTER TABLE public.cost_master
ADD COLUMN supplier_id UUID;
