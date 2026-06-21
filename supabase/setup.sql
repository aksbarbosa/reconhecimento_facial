-- setup.sql
-- Rodar no SQL Editor do Supabase Dashboard
-- https://supabase.com/dashboard/project/sktwaczihfsbossuguab/sql

-- ── 1. PROFILES ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
  id   uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL DEFAULT ''
);

-- ── 2. DEPENDENTS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.dependents (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       text NOT NULL
);

-- ── 3. EXPO PUSH TOKENS ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.expo_push_tokens (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  token      text NOT NULL UNIQUE,
  created_at timestamptz DEFAULT now()
);

-- ── 4. RECOGNITION EVENTS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.recognition_events (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  dependent_id uuid REFERENCES public.dependents(id),
  person_name  text NOT NULL,
  camera_id    text,
  camera_label text,
  address      text,
  city         text,
  state        text,
  confidence   float,
  timestamp    timestamptz DEFAULT now()
);

-- ── 5. RLS ───────────────────────────────────────────────────────────────────
ALTER TABLE public.recognition_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own events"
  ON public.recognition_events FOR SELECT
  USING (auth.uid() = user_id);

ALTER TABLE public.expo_push_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users manage own tokens"
  ON public.expo_push_tokens FOR ALL
  USING (auth.uid() = user_id);

ALTER TABLE public.dependents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users manage own dependents"
  ON public.dependents FOR ALL
  USING (auth.uid() = profile_id);

-- ── 6. REALTIME ──────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE public.recognition_events;
