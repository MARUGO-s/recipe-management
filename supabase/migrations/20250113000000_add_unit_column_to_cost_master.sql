-- 単位列をcost_masterテーブルに追加
ALTER TABLE public.cost_master
ADD COLUMN IF NOT EXISTS unit_column TEXT;

-- 既存データの単位列を設定（現在のunit列からコピー）
UPDATE public.cost_master
SET unit_column = unit
WHERE unit_column IS NULL;

-- 単位列にデフォルト値を設定
ALTER TABLE public.cost_master
ALTER COLUMN unit_column SET DEFAULT '個';

-- インデックスを作成（検索用）
CREATE INDEX IF NOT EXISTS idx_cost_master_unit_column ON public.cost_master(unit_column);

-- コメントを追加
COMMENT ON COLUMN public.cost_master.unit_column IS 'CSVの単位列から抽出した単位情報（変換せずそのまま保持: PC, kg, L など）';
COMMENT ON COLUMN public.cost_master.capacity IS '材料の容量（包装容量、kg→g, L→mlに変換済み）';
COMMENT ON COLUMN public.cost_master.unit IS '容量の単位（g, ml, 個など、変換済み）';
