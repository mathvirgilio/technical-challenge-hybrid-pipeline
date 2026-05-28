from pathlib import Path

from hybrid_pipeline.pipeline.parsing import parse_procedure

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_fn_saldo_cliente():
    sql = (FIXTURES / "annex_b_fn_saldo_cliente.sql").read_text(encoding="utf-8")
    result = parse_procedure(sql)
    assert result["routine_name"] == "fn_saldo_cliente"
    assert result["routine_kind"] == "FUNCTION"
    assert any(p["name"] == "p_cliente_id" for p in result["parameters"])


def test_parse_detects_cursor_in_annex_e():
    sql = (FIXTURES / "annex_e_sp_processar_lote_taxas.sql").read_text(encoding="utf-8")
    result = parse_procedure(sql)
    assert result["routine_name"] == "sp_processar_lote_taxas"
    assert "CURSOR" in sql.upper()
    assert any(
        "CURSOR" in v.get("type", "").upper() for v in result.get("declare_variables", [])
    ) or any(s["kind"] in ("OPEN", "FETCH", "CLOSE") for s in result["statements"])
