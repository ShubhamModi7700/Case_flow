begin;

create table if not exists public.case_access (
    id bigserial primary key,
    case_id integer not null references public.cases(id) on delete cascade,
    user_id integer not null references public.users(id) on delete cascade,
    can_edit boolean not null default false,
    constraint uq_case_access_case_user unique (case_id, user_id)
);

create index if not exists ix_case_access_case_id
    on public.case_access(case_id);

create index if not exists ix_case_access_user_id
    on public.case_access(user_id);

commit;
