from pathlib import Path

from hybrid_pipeline.pipeline.analysis import analyze_semantics
from hybrid_pipeline.pipeline.parsing import parse_procedure

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_analysis_flags_recursive_cte():
    sql = (FIXTURES / "annex_f_sp_relatorio_mensal_cliente.sql").read_text(encoding="utf-8")
    parsed = parse_procedure(sql)
    analysis = analyze_semantics(sql, parsed)
    assert analysis["features"]["has_recursive_cte"]
    tags = {r["tag"] for r in analysis["risks"]}
    assert "recursive_cte" in tags
