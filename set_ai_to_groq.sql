-- AIプロバイダーをGroqに設定
UPDATE public.system_settings 
SET value = 'groq', updated_at = NOW()
WHERE key = 'ai_provider';

-- 設定が存在しない場合は挿入
INSERT INTO public.system_settings (key, value, created_at, updated_at)
VALUES ('ai_provider', 'groq', NOW(), NOW())
ON CONFLICT (key) DO UPDATE SET
    value = 'groq',
    updated_at = NOW();

-- 確認用クエリ
SELECT key, value, updated_at 
FROM public.system_settings 
WHERE key = 'ai_provider';
