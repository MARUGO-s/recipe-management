-- 材料テーブルに容量情報フィールドを追加
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS capacity DECIMAL(10, 2) DEFAULT 1;
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS capacity_unit TEXT DEFAULT '個';

-- コメント追加
COMMENT ON COLUMN ingredients.capacity IS '材料の包装容量（例: 500gパックの場合は500）';
COMMENT ON COLUMN ingredients.capacity_unit IS '包装容量の単位（例: g, ml, 個）';
