from pathlib import Path

import pytest

from hybrid_pipeline.graph.build import graph

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.asyncio
async def test_graph_end_to_end_annex_b():
    sql = (FIXTURES / "annex_b_fn_saldo_cliente.sql").read_text(encoding="utf-8")
    result = await graph.ainvoke({"source_code": sql, "schema_context": None})
    assert result["status"] == "success"
    assert "def fn_saldo_cliente" in result["generated_code"]
    assert result["report"]["parsing"]["routine_name"] == "fn_saldo_cliente"


@pytest.mark.asyncio
async def test_graph_all_annexes_produce_code():
    for name in "bcdef":
        path = next(FIXTURES.glob(f"annex_{name}*.sql"))
        sql = path.read_text(encoding="utf-8")
        result = await graph.ainvoke({"source_code": sql, "schema_context": None})
        assert result.get("generated_code")
        assert result["validation_result"]["ast_parse_ok"]
