-- 規格カラムをcost_masterテーブルに追加
ALTER TABLE public.cost_master
ADD COLUMN IF NOT EXISTS spec TEXT;

-- 規格カラムにコメントを追加
COMMENT ON COLUMN public.cost_master.spec IS 'CSVの規格列（16列目）から抽出した規格情報（そのまま保持）';

-- インデックスを作成（検索用）
CREATE INDEX IF NOT EXISTS idx_cost_master_spec ON public.cost_master(spec);
