"""Bounded prompt evidence and request-time coverage (not legal review completeness)."""

def select_prompt_chunks(chunks, task_type):
    unique = {}
    for row in chunks:
        unique.setdefault(row['chunk_id'], row)
    first, rest, seen = [], [], set()
    for row in unique.values():
        doc = row['document_id']
        (rest if doc in seen else first).append(row)
        seen.add(doc)
    cap = 18 if task_type == 'question' else 40
    return [{**row, 'content': row['content'][:2400]} for row in (first + rest)[:cap] if row.get('content', '').strip()]


def summarize_coverage(documents, chunks):
    supplied = {row['document_id'] for row in chunks}
    ids = {doc.id for doc in documents}
    ready = {doc.id for doc in documents if doc.processing_status == 'Ready' and doc.embedding_status == 'Ready'}
    failed = {doc.id for doc in documents if 'Failed' in (doc.processing_status, doc.embedding_status)}
    return dict(total_documents=len(ids), ready_documents=len(ready), failed_documents=len(failed),
                other_documents=len(ids-ready-failed), supplied_documents=len(ids & supplied),
                supplied_chunks=len(chunks), omitted_documents=[dict(document_id=doc.id, filename=doc.file_name) for doc in documents if doc.id not in supplied])
