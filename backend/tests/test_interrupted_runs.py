from app.models import ProcessingRun
from app.repositories import store
from app.services.pipeline import initial_stages


def test_runs_left_running_by_a_restart_are_failed(db, bank_id):
    run = ProcessingRun(bank_id=bank_id, mode="demo", question="Вопрос", answer_origin="user",
                        original_answer="Ответ", tone="neutral", stages=initial_stages(), execution_status="running")
    db.add(run)
    db.commit()

    assert store.fail_interrupted_runs(db) >= 1

    db.refresh(run)
    assert run.execution_status == "failed"
    assert run.result_status == "FAILED"
    assert run.final_answer is None
    assert run.error["code"] == "INTERRUPTED"
    assert all(s["status"] == "skipped" for s in run.stages)
