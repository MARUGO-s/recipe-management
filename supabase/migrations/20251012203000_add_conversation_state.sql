-- 会話状態を保存するテーブル
CREATE TABLE public.conversation_state (
    user_id TEXT NOT NULL PRIMARY KEY,
    state JSONB,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- updated_atを自動更新するトリガー関数
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- conversation_stateテーブルにトリガーを設定
CREATE TRIGGER on_conversation_state_update
BEFORE UPDATE ON public.conversation_state
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();
