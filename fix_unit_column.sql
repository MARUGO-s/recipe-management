-- 単位列を完全にリセットするSQL
-- SupabaseのSQL Editorで実行してください

-- 1. まず現在の状況を確認
SELECT ingredient_name, capacity, unit, unit_column 
FROM public.cost_master 
WHERE unit_column IS NOT NULL 
LIMIT 10;

-- 2. 単位列を完全にクリア
UPDATE public.cost_master 
SET unit_column = NULL;

-- 3. 新しいCSVアップロード時に正しく設定されることを確認
-- この後、新しいCSVファイルをアップロードしてください

-- 4. 結果を確認
SELECT ingredient_name, capacity, unit, unit_column 
FROM public.cost_master 
ORDER BY updated_at DESC 
LIMIT 10;
