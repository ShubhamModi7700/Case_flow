"""Merge exact normalized duplicate topics and statements; retain valid sources."""

def consolidate_issues(issues, valid_ids):
    from app.schemas import AssistantCaseIssue, AssistantEvidenceStatement
    def key(value):
        return ' '.join(value.split()).casefold()
    merged = {}
    for issue in issues:
        title = key(issue.title)
        if not title:
            continue
        target = merged.setdefault(title, AssistantCaseIssue(title=issue.title.strip()))
        for field in ('facts', 'party_claims', 'counterevidence'):
            items = getattr(target, field)
            indexed = {key(item.text): item for item in items}
            for item in getattr(issue, field):
                ids = list(dict.fromkeys(s for s in item.source_ids if s in valid_ids))
                if not ids or not key(item.text):
                    continue
                existing = indexed.get(key(item.text))
                if existing is None:
                    existing = AssistantEvidenceStatement(text=item.text.strip(), source_ids=ids)
                    items.append(existing)
                    indexed[key(item.text)] = existing
                else:
                    existing.source_ids = list(dict.fromkeys(existing.source_ids + ids))
        seen = {key(g) for g in target.gaps}
        for gap in issue.gaps:
            if key(gap) and key(gap) not in seen:
                target.gaps.append(gap.strip())
                seen.add(key(gap))
    return [i for i in merged.values() if i.facts or i.party_claims or i.counterevidence or i.gaps]
