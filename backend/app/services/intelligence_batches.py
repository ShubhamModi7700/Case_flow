from app import models, schemas
from app.services.case_access import require_case_view
from app.services.case_qa import answer_case_question, validate_answer_sources
from app.services.issue_consolidation import consolidate_issues


def load_case_chunks(db, user, case_id):
    require_case_view(db, user, case_id)
    c, d = models.DocumentChunk, models.Document
    rows = (db.query(c.id, c.document_id, d.file_name, c.content, c.page_number,
                     c.sheet_name, c.email_section, c.metadata_json)
            .join(d, d.id == c.document_id)
            .filter(d.case_id == case_id, c.case_id == case_id,
                    d.processing_status == 'Ready')
            .order_by(c.document_id, c.chunk_index, c.id).all())
    return [dict(chunk_id=r[0], document_id=r[1], file_name=r[2], content=r[3],
                 page_number=r[4], sheet_name=r[5], email_section=r[6], metadata=r[7])
            for r in rows if r[3] and r[3].strip()]


def batches(sources, max_chars=24000, max_sources=12):
    batch, size = [], 0
    for source in sources:
        content = source['content']
        # Preserve every character; split unusually long chunks under the same source ID.
        for start in range(0, len(content), max_chars):
            part = {**source, 'content': content[start:start + max_chars]}
            cost = len(part['content'])
            if batch and (size + cost > max_chars or len(batch) >= max_sources):
                yield batch
                batch, size = [], 0
            batch.append(part)
            size += cost
    if batch:
        yield batch


def merge_intelligence(parts, sources):
    valid = {s['source_id'] for s in sources}
    merged = schemas.AssistantCaseIntelligence()
    merged.issues = consolidate_issues([i for p in parts for i in p.issues], valid)
    for field in ('executive_summary', 'key_facts', 'documented_obligations',
                  'key_events', 'key_entities', 'evidence_map', 'contradictions'):
        seen = {}
        for part in parts:
            for item in getattr(part, field):
                ids = [s for s in item.source_ids if s in valid]
                if not ids:
                    continue
                # Include all non-source fields: do not merge conflicting roles/statuses.
                key = item.model_dump_json(exclude={'source_ids'}).casefold()
                if key not in seen:
                    seen[key] = item.model_copy(deep=True, update={'source_ids': list(dict.fromkeys(ids))})
                else:
                    seen[key].source_ids = list(dict.fromkeys(seen[key].source_ids + ids))
        setattr(merged, field, list(seen.values()))
    for field in ('information_gaps', 'unresolved_issues'):
        setattr(merged, field, list(dict.fromkeys(x for p in parts for x in getattr(p, field))))
    return merged


def analyze_batches(question, sources, documents, analyze=answer_case_question):
    parts = []
    for batch in batches(sources):
        result = analyze(question=question + '\nAnalysiere diesen Teilbestand. Lücken gelten nur für diesen Teilbestand; keine abschließende Fallbewertung.', sources=batch, task_type='intelligence')
        result = validate_answer_sources(result, batch)
        if result.intelligence is None:
            raise RuntimeError('Teilbestand konnte nicht strukturiert analysiert werden.')
        parts.append(result.intelligence)
    merged = merge_intelligence(parts, sources)
    supplied = {s['document_id'] for s in sources}
    merged.information_gaps.insert(0, f'Analyseumfang: {len(supplied)} von {len(documents)} Dokumenten, {len(sources)} Textabschnitte, {len(parts)} Teilanalysen. Keine vollständige Rechtsprüfung; teilbestandsübergreifende Widersprüche sind nicht abschließend geprüft.')
    missing = [d.file_name for d in documents if d.id not in supplied]
    if missing:
        merged.information_gaps.insert(1, 'Nicht analysierte Dokumente: ' + '; '.join(missing))
    return schemas.CaseAssistantModelAnswer(answer='Fallwissen aus Teilanalysen zusammengeführt.', intelligence=merged)
