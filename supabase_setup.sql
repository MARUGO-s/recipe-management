-- レシピテーブル
CREATE TABLE IF NOT EXISTS recipes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recipe_name TEXT NOT NULL,
    servings INTEGER NOT NULL,
    total_cost DECIMAL(10, 2),
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 材料テーブル
CREATE TABLE IF NOT EXISTS ingredients (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recipe_id UUID REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    quantity DECIMAL(10, 2) NOT NULL,
    unit TEXT NOT NULL,
    cost DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 原価表テーブル（Supabaseストレージから読み込んだデータをキャッシュ）
CREATE TABLE IF NOT EXISTS cost_master (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ingredient_name TEXT NOT NULL UNIQUE,
    unit_price DECIMAL(10, 2) NOT NULL,
    reference_unit TEXT NOT NULL,
    reference_quantity DECIMAL(10, 2) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_ingredients_recipe_id ON ingredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_cost_master_ingredient_name ON cost_master(ingredient_name);

-- RLS（Row Level Security）の有効化
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_master ENABLE ROW LEVEL SECURITY;

-- 全てのユーザーが読み取り・書き込み可能なポリシー（認証なしの簡易版）
CREATE POLICY "Enable all access for recipes" ON recipes FOR ALL USING (true);
CREATE POLICY "Enable all access for ingredients" ON ingredients FOR ALL USING (true);
CREATE POLICY "Enable all access for cost_master" ON cost_master FOR ALL USING (true);

-- ストレージバケット作成（Supabase UIまたはAPIで実行）
-- バケット名: 'cost-data'
-- 公開設定: private
-- 原価表ファイル（CSV）をアップロード予定

