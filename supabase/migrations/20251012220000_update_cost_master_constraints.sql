-- 古いユニーク制約を削除
-- 制約名は環境によって異なる可能性があるため、事前に確認するのが望ましい
ALTER TABLE public.cost_master
DROP CONSTRAINT IF EXISTS cost_master_ingredient_name_key;

-- 新しい複合ユニーク制約を追加
-- これにより、同じ取引先の同じ商品（容量・単位が同じ）が重複して登録されるのを防ぐ
ALTER TABLE public.cost_master
ADD CONSTRAINT cost_master_unique_product_key
UNIQUE (ingredient_name, supplier_id, capacity, unit);
