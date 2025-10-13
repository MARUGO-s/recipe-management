-- 取引先名と取引日付の列を追加
ALTER TABLE public.cost_master 
ADD COLUMN IF NOT EXISTS supplier_name TEXT,
ADD COLUMN IF NOT EXISTS transaction_date TEXT;

-- インデックスを追加
CREATE INDEX IF NOT EXISTS idx_cost_master_supplier_name ON public.cost_master(supplier_name);
CREATE INDEX IF NOT EXISTS idx_cost_master_transaction_date ON public.cost_master(transaction_date);

-- コメントを追加
COMMENT ON COLUMN public.cost_master.supplier_name IS '取引先名';
COMMENT ON COLUMN public.cost_master.transaction_date IS '取引日付';
