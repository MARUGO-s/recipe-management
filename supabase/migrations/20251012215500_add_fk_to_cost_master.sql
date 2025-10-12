-- cost_masterテーブルに外部キー制約を追加
ALTER TABLE public.cost_master
ADD CONSTRAINT fk_supplier
FOREIGN KEY (supplier_id)
REFERENCES public.suppliers(id)
ON DELETE SET NULL; -- 取引先が削除された場合、関連する材料のsupplier_idをNULLにする
