"""Integration test: bootstrap curriculum rows into SQLite."""

from sqlalchemy import select

from insightsdsa.appinit import bootstrap
from insightsdsa.models import Concept, Question


def test_bootstrap_inserts_from_embedded_sql():
    cid = 880_001
    qid = 880_002
    sql = (
        f"INSERT INTO public.concepts VALUES ({cid}, 'TmpConcept', 'x') ON CONFLICT DO NOTHING;\n"
        f"INSERT INTO public.questions VALUES ({qid}, 'TmpQ', 'easy', NULL, false, {cid}, 'desc') "
        "ON CONFLICT DO NOTHING;\n"
    )
    bootstrap(curriculum_sql=sql)

    from insightsdsa.db import get_session

    with get_session() as s:
        c = s.get(Concept, cid)
        q = s.get(Question, qid)
        assert c is not None
        assert c.title == "TmpConcept"
        assert q is not None
        assert q.concept_id == cid
        assert (s.scalar(select(Question.description).where(Question.id == qid))) == "desc"
