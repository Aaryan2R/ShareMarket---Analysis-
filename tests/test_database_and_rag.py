from core.database import IntelligenceDB
from core.rag_engine import RagEngine


def test_database_packet_roundtrip(tmp_path):
    db = IntelligenceDB(tmp_path / "assistant.db")
    company_id = db.add_company("Infosys", "INFY")
    db.save_packet(company_id, {"company": "Infosys", "composite_score": 55.5})

    assert db.list_companies() == ["Infosys"]
    assert db.get_nse_symbol("Infosys") == "INFY"
    assert db.get_packet(company_id)["composite_score"] == 55.5


def test_rag_retrieval_returns_packets(tmp_path):
    db = IntelligenceDB(tmp_path / "assistant.db")
    infy = db.add_company("Infosys", "INFY")
    tcs = db.add_company("Tata Consultancy Services", "TCS")
    db.save_packet(infy, {"company": "Infosys", "composite_score": 54.18})
    db.save_packet(tcs, {"company": "Tata Consultancy Services", "composite_score": 53.16})

    rag = RagEngine(db)
    context, packets = rag.context_for_question("rank companies")

    # Both companies should be in the retrieved context
    assert "Infosys" in context
    assert "Tata Consultancy Services" in context
    assert "54.18" in context
    assert "53.16" in context
    # Packets dict should have both
    assert "Infosys" in packets
    assert "Tata Consultancy Services" in packets


def test_tool_registry_list_companies(tmp_path):
    from core.tools import ToolRegistry
    from core.orchestrator import Orchestrator

    db = IntelligenceDB(tmp_path / "assistant.db")
    db.add_company("Infosys", "INFY")
    db.add_company("TCS", "TCS")
    orch = Orchestrator(db)
    rag = RagEngine(db)

    registry = ToolRegistry(db=db, orchestrator=orch, rag=rag)
    result = registry.execute("list_companies", {})

    assert result["count"] == 2
    names = [c["name"] for c in result["companies"]]
    assert "Infosys" in names
    assert "TCS" in names

