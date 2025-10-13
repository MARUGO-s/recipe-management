-- システム設定テーブルを作成
CREATE TABLE IF NOT EXISTS public.system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックスを作成
CREATE INDEX IF NOT EXISTS idx_system_settings_key ON public.system_settings(key);

-- コメントを追加
COMMENT ON TABLE public.system_settings IS 'システム設定を保存するテーブル';
COMMENT ON COLUMN public.system_settings.key IS '設定キー（例: ai_provider）';
COMMENT ON COLUMN public.system_settings.value IS '設定値（例: groq, gpt）';
COMMENT ON COLUMN public.system_settings.created_at IS '作成日時';
COMMENT ON COLUMN public.system_settings.updated_at IS '更新日時';

-- 初期設定を挿入（AIプロバイダーをデフォルトでgroqに設定）
INSERT INTO public.system_settings (key, value) 
VALUES ('ai_provider', 'groq') 
ON CONFLICT (key) DO NOTHING;
