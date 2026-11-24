import unittest
from types import SimpleNamespace
from app.services.evidence_coverage import select_prompt_chunks, summarize_coverage

class CoverageTests(unittest.TestCase):
    def test_sizes(self):
        for count in (2, 20, 120):
            with self.subTest(count=count):
                docs = [SimpleNamespace(id=i, file_name=f'{i}.pdf', processing_status='Ready', embedding_status='Ready') for i in range(count)]
                rows = [dict(chunk_id=i*3+j, document_id=i, content='x'*3000) for i in range(count) for j in range(3)]
                for task, cap in [('question',18), ('brief_review',40)]:
                    selected = select_prompt_chunks(rows, task)
                    coverage = summarize_coverage(docs, selected)
                    self.assertEqual(coverage['supplied_documents'], min(count,cap))
                    self.assertEqual(len(coverage['omitted_documents']), max(0,count-cap))
                    self.assertLessEqual(len(selected),cap)
                    self.assertTrue(all(len(r['content']) <= 2400 for r in selected))
    def test_failed_partial_and_duplicate(self):
        docs = [SimpleNamespace(id=i, file_name=str(i), processing_status=s, embedding_status='Ready') for i,s in enumerate(['Ready','Failed','Partial'])]
        row = dict(chunk_id=1, document_id=0, content='text')
        c = summarize_coverage(docs, select_prompt_chunks([row,row], 'question'))
        self.assertEqual((c['ready_documents'],c['failed_documents'],c['other_documents'],c['supplied_chunks']), (1,1,1,1))
