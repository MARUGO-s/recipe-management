-- cost_masterテーブルにcapacityカラムを追加
ALTER TABLE cost_master
ADD COLUMN IF NOT EXISTS capacity DECIMAL(10, 2) DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS unit TEXT DEFAULT '個';

-- 既存のデータを更新（reference_quantityからcapacityに移行）
UPDATE cost_master 
SET capacity = COALESCE(reference_quantity, 1.0),
    unit = COALESCE(reference_unit, '個')
WHERE capacity IS NULL OR capacity = 1.0;

-- 不要になったカラムを削除（オプション）
-- ALTER TABLE cost_master DROP COLUMN IF EXISTS reference_quantity;
-- ALTER TABLE cost_master DROP COLUMN IF EXISTS reference_unit;
