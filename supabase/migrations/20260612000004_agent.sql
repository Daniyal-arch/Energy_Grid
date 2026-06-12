-- Agent chat history. Messages carry a structured sources array (cited evidence/detection IDs).

create table agent_conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users (id) on delete set null,
  title      text,
  created_at timestamptz not null default now()
);

create table agent_messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references agent_conversations (id) on delete cascade,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null,
  sources         jsonb not null default '[]'::jsonb,  -- [{type, id, scene_id?, date?, confidence?}]
  created_at      timestamptz not null default now()
);

create index agent_messages_conversation_idx on agent_messages (conversation_id, created_at);

alter table agent_conversations enable row level security;
alter table agent_messages enable row level security;

create policy "own conversations" on agent_conversations
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "own messages" on agent_messages
  for all to authenticated
  using (exists (select 1 from agent_conversations c
                 where c.id = conversation_id and c.user_id = auth.uid()))
  with check (exists (select 1 from agent_conversations c
                      where c.id = conversation_id and c.user_id = auth.uid()));
