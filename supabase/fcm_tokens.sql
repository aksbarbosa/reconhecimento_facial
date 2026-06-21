-- Rodar no SQL Editor do Supabase Dashboard
-- https://supabase.com/dashboard/project/sktwaczihfsbossuguab/sql/new

CREATE TABLE IF NOT EXISTS public.fcm_tokens (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  token      text NOT NULL,
  created_at timestamptz DEFAULT now(),
  UNIQUE (user_id, token)
);

ALTER TABLE public.fcm_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users manage own fcm tokens"
  ON public.fcm_tokens FOR ALL
  USING (auth.uid() = user_id);
