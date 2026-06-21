import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const WEBHOOK_SECRET     = Deno.env.get('WEBHOOK_SECRET')!;
const SUPABASE_URL       = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const FIREBASE_PROJECT_ID  = Deno.env.get('FIREBASE_PROJECT_ID')!;
const FIREBASE_CLIENT_EMAIL = Deno.env.get('FIREBASE_CLIENT_EMAIL')!;
// Aceita base64 puro (sem headers PEM e sem newlines)
const FIREBASE_PRIVATE_KEY_B64 = Deno.env.get('FIREBASE_PRIVATE_KEY')!.replace(/\s/g, '');

// Gera um access token OAuth2 usando a service account do Firebase
async function getFCMAccessToken(): Promise<string> {
  const now = Math.floor(Date.now() / 1000);

  const encode = (obj: object) =>
    btoa(JSON.stringify(obj))
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');

  const header  = { alg: 'RS256', typ: 'JWT' };
  const payload = {
    iss:   FIREBASE_CLIENT_EMAIL,
    scope: 'https://www.googleapis.com/auth/firebase.messaging',
    aud:   'https://oauth2.googleapis.com/token',
    iat:   now,
    exp:   now + 3600,
  };

  const unsigned = `${encode(header)}.${encode(payload)}`;

  const keyData = Uint8Array.from(atob(FIREBASE_PRIVATE_KEY_B64), c => c.charCodeAt(0));

  const key = await crypto.subtle.importKey(
    'pkcs8',
    keyData,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );

  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    key,
    new TextEncoder().encode(unsigned),
  );

  const sig = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

  const jwt = `${unsigned}.${sig}`;

  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`,
  });

  const { access_token } = await tokenRes.json();
  return access_token;
}

// Envia uma mensagem FCM v1 para um token
async function sendFCM(
  accessToken: string,
  token: string,
  title: string,
  body: string,
  data: Record<string, string>,
): Promise<boolean> {
  const res = await fetch(
    `https://fcm.googleapis.com/v1/projects/${FIREBASE_PROJECT_ID}/messages:send`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: {
          token,
          notification: { title, body },
          data,
          android: {
            priority: 'high',
            notification: { sound: 'default' },
          },
        },
      }),
    },
  );
  return res.status === 200;
}

serve(async (req) => {
  // 1. Valida o segredo do webhook
  if (req.headers.get('x-webhook-secret') !== WEBHOOK_SECRET) {
    return new Response('Unauthorized', { status: 401 });
  }

  const payload = await req.json();
  const { person_id, person_name, location, timestamp, confidence, access_granted = true } = payload;

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  // 2. Busca o responsável pelo dependent_id
  const { data: dependent } = await supabase
    .from('dependents')
    .select('profile_id')
    .eq('id', person_id)
    .single();

  if (!dependent) {
    return new Response('Dependent not found', { status: 404 });
  }

  const userId = dependent.profile_id;

  // 3. Salva o evento
  const { data: event } = await supabase
    .from('recognition_events')
    .insert({
      user_id:      userId,
      dependent_id: person_id,
      person_name,
      camera_id:    location.camera_id,
      camera_label: location.camera_label,
      address:      location.address,
      city:         location.city,
      state:        location.state,
      confidence,
      timestamp,
    })
    .select('id')
    .single();

  // 4. Busca os FCM tokens do responsável
  const { data: tokenRows } = await supabase
    .from('fcm_tokens')
    .select('token')
    .eq('user_id', userId);

  const tokens = (tokenRows ?? []).map((r: any) => r.token);
  if (tokens.length === 0) {
    return new Response(JSON.stringify({ ok: true, push: 'no tokens' }), { status: 200 });
  }

  // 5. Envia push via FCM v1
  const accessToken = await getFCMAccessToken();
  const notifTitle  = access_granted ? '✅ Acesso liberado' : '⚠️ Acesso negado';
  const notifBody   = `${person_name} · ${location.camera_label} · ${location.city}, ${location.state}`;
  const notifData   = {
    event_id:       event?.id ?? '',
    person_name,
    camera_label:   location.camera_label,
    location:       JSON.stringify(location),
    timestamp,
    confidence:     String(confidence),
    access_granted: String(access_granted),
  };

  const results = await Promise.allSettled(
    tokens.map((token: string) =>
      sendFCM(accessToken, token, notifTitle, notifBody, notifData)
    ),
  );

  const sent = results.filter(r => r.status === 'fulfilled' && (r as any).value).length;

  return new Response(JSON.stringify({ ok: true, sent, total: tokens.length }), { status: 200 });
});
