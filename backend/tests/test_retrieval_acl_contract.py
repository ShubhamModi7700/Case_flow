"""Security contract tests for ACL-before-ranking retrieval.

These tests intentionally inspect the SQL contract because the critical manager
requirement is *where* authorization happens: inaccessible chunks must be
filtered before vector ranking/LIMIT, not removed from results afterwards.
"""

import inspect

from app.services import retrieval


def test_chunk_retrieval_embeds_acl_in_vector_query():
    source = inspect.getsource(retrieval.retrieve_chunks).casefold()

    assert "public.case_access" in source
    assert "ca.user_id = :requesting_user_id" in source
    assert "ca.case_id = d.case_id" in source
    assert "order by dc.embedding" in source
    assert "limit :match_count" in source

    assert "match_document_chunks(" not in source


def test_case_matching_embeds_acl_before_ranking():
    source = inspect.getsource(retrieval.match_cases).casefold()

    assert "public.case_access" in source
    assert "ca.user_id = :requesting_user_id" in source
    assert "ca.case_id = ce.case_id" in source
    assert "order by ce.embedding" in source
    assert "limit :match_count" in source
