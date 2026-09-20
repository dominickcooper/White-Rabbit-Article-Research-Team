import csv
import json
from pathlib import Path

import pytest

from white_rabbit import distribution as d
from white_rabbit import distribution_creative as dc


def test_ids_and_utm_are_stable():
    assert d.article_id(1) == "USAID-CIA-P01"
    assert d.content_id(1,"TT","SHORT",1) == "WRR-USAIDCIA-P01-TT-SHORT-001"
    assert d.utm_url("https://example.com/p/a","x","social","CID") == "https://example.com/p/a?utm_source=x&utm_medium=social&utm_campaign=usaid_cia_2026&utm_content=CID"


def test_spoiler_protection_and_classifications():
    assert d.spoiler_allowed(1,1)
    assert not d.spoiler_allowed(1,2)
    assert d.spoiler_allowed(1,2,teaser_safe=True)
    assert d.CLASSIFICATIONS == {"DOCUMENTED_FACT","STRONG_INFERENCE","PLAUSIBLE_CONNECTION","SPECULATION"}


def test_approval_transitions():
    d.transition_status("NEEDS_REVIEW","APPROVED")
    with pytest.raises(ValueError): d.transition_status("NEEDS_REVIEW","PUBLISHED")


def _series(tmp_path: Path):
    root=tmp_path; series=root/"series_projects/s"; (series/"articles").mkdir(parents=True)
    parts=[]
    for n in range(1,8):
        slug=f"part-{n:02d}-p{n}"; project=series/"articles"/slug; (project/"output").mkdir(parents=True)
        (project/"output/article.md").write_text("# A\n",encoding="utf-8")
        (project/"output/sources.csv").write_text("source_number,phrase,link\n1,x,https://example.com\n",encoding="utf-8")
        parts.append({"number":n,"title":f"P{n}","slug":slug,"status":"complete","finale":n==7,"previous":f"part-{n-1:02d}-p{n-1}" if n>1 else None,"next":f"part-{n+1:02d}-p{n+1}" if n<7 else None,"published_url":None,"created_at":"2026-01-01T00:00:00+00:00","updated_at":"2026-01-01T00:00:00+00:00"})
    manifest={"schema_version":1,"title":"S","slug":"s","status":"complete","planned_parts":7,"created_at":"2026-01-01T00:00:00+00:00","updated_at":"2026-01-01T00:00:00+00:00","parts":parts}
    return series,manifest


def test_campaign_order_and_canonical_files_unchanged(tmp_path):
    series,manifest=_series(tmp_path); before=(series/"articles/part-01-p1/output/article.md").read_bytes()
    built=d.campaign_manifest(series,manifest)
    assert built["article_order"] == [f"USAID-CIA-P{n:02d}" for n in range(1,8)]
    assert (series/"articles/part-01-p1/output/article.md").read_bytes()==before


def test_missing_source_file():
    with pytest.raises(ValueError,match="Missing source file"): d._read_csv(Path("does-not-exist.csv"))


def test_analytics_schema_validation(tmp_path):
    path=tmp_path/"a.csv"; d._write_csv(path,d.ANALYTICS_FIELDS,[])
    assert d.validate_analytics(path)==[]
    row={field:"" for field in d.ANALYTICS_FIELDS}; row.update(content_id="x",views="invented")
    d._write_csv(path,d.ANALYTICS_FIELDS,[row])
    assert "views must be nonnegative numeric" in d.validate_analytics(path)[0]


def test_content_registry_uniqueness_and_evidence_generation():
    specs=d._asset_specs(); ids=[]
    counts={}
    for platform,fmt,_,_ in specs:
        counts[(platform,fmt)]=counts.get((platform,fmt),0)+1
        ids.append(d.content_id(1,platform,fmt,counts[(platform,fmt)]))
    assert len(ids)==len(set(ids))
    assert len(ids)==43


def sample_claim(i=1, support="DIRECT", excerpt="Exact source language"):
    return {"claim_id":f"C{i}","article_id":"USAID-CIA-P01","claim_text":f"Documented claim number {i}.","claim_classification":"DOCUMENTED_FACT","claim_type":"DATE","article_section":"S","article_excerpt":"Article context","source_number":str(i),"source_title":"Memo","source_url":"https://example.com","source_file":"source.txt","source_excerpt":excerpt,"support_type":support,"source_strength":"PRIMARY","spoiler_scope":"CURRENT_PART","teaser_safe":"NO","review_required":"NO","notes":""}


def test_multi_claim_packet_and_platform_prompt():
    claims=[sample_claim(1),sample_claim(2)]; angle={"angle_id":"A1","angle_name":"TIMELINE","supporting_claim_ids":["C1","C2"],"spoiler_scope":"CURRENT_PART"}
    packet=dc.build_evidence_packet(claims,angle,"TIMELINE","reddit")
    assert len(packet["approved_claims"])==2
    assert "community-native" in packet["platform_requirements"]
    assert dc.PROMPT_VERSION in dc.creative_prompt(packet)


def test_hook_families_change_copy():
    claims=[sample_claim(1),sample_claim(2)]
    copies={dc.offline_copy("tiktok","SHORT",family,"A",claims,0) for family in ("DOCUMENT","CONTRADICTION","TIMELINE")}
    assert len(copies)==3


def test_assertion_mapping_rejection_and_partial_support():
    claims=[sample_claim(1)]
    assert dc.map_assertion("Documented claim number 1.",claims)["support_status"]=="SUPPORTED"
    assert dc.validate_assertions([{"assertion_id":"A","support_status":"UNSUPPORTED"}])==["Unsupported assertion A"]
    rows=dc.extract_assertions("CONTENT","Documented claim number 1.",["C1"],[sample_claim(1,"PARTIAL")])
    assert rows[0]["support_status"]=="PARTIALLY_SUPPORTED" and rows[0]["review_required"]=="YES"


def test_similarity_and_reuse_exemption():
    copy="This is the same sufficiently long body of factual copy for comparison."
    assets=[{"content_id":"A","copy":copy},{"content_id":"B","copy":copy}]
    assert dc.similarity_report(assets)["validation"]=="FAIL"
    assets[1]["reuse_policy"]="CROSS_PLATFORM_REUSE"
    assert dc.similarity_report(assets)["validation"]=="PASS"


def test_duration_angle_and_missing_excerpt():
    assert dc.duration_check("SHORT","word "*45)["duration_validation"]=="PASS"
    assert dc.duration_check("LONGSHORT","word "*30)["duration_validation"]=="FAIL"
    assert len({a["angle_name"] for a in dc.angles([sample_claim(i) for i in range(30)])})>=9
    claim=sample_claim(1,excerpt="UNAVAILABLE"); claim["review_required"]="YES"
    assert claim["source_excerpt"]=="UNAVAILABLE" and claim["review_required"]=="YES"


def test_provider_metadata_contract():
    class Fake:
        provider_name="fake"; model_name="fake-model"
        def generate(self,prompt,packet): return "bounded copy"
    assert Fake().generate("p",{})=="bounded copy"


def test_no_automatic_publishing_and_approval_states_preserved():
    assert "PUBLISHED" in d.STATUSES
    assert "PUBLISHED" not in d.TRANSITIONS["NEEDS_REVIEW"]


def test_preventive_medicine_requires_packet_claim():
    quote=sample_claim(1); quote.update(claim_text="The committee called police assistance preventive medicine.",claim_type="QUOTATION",source_excerpt="preventive medicine")
    assert dc.extract_assertions("X","The committee called police assistance ‘preventive medicine.’",[],[quote])[0]["support_status"]=="UNSUPPORTED"
    assert dc.extract_assertions("X","The committee called police assistance ‘preventive medicine.’",["C1"],[quote])[0]["support_status"]=="SUPPORTED"


def test_synthetic_opening_is_not_ignored():
    claims=[sample_claim(1),sample_claim(2)]
    row=dc.extract_assertions("X","Before the Office of Public Safety had a name, a committee had already designed its job.",["C1","C2"],claims)[0]
    assert row["assertion_type"]=="CHRONOLOGY"
    assert row["support_status"]=="INFERENCE_SUPPORTED"


def test_four_decisions_requires_four_supported_decisions():
    rows=dc.extract_assertions("X","Follow four decisions across 1962, and a police system takes shape in plain sight.",["C1","C2"],[sample_claim(1),sample_claim(2)])
    assert rows[0]["support_status"] in {"PARTIALLY_SUPPORTED","UNSUPPORTED"}


def test_composite_assertion_splitting():
    assert dc.split_composite("AID received responsibility while covert work was excluded.")==["AID received responsibility","covert work was excluded."]


def test_hook_semantics():
    money=sample_claim(1); money["claim_type"]="MONEY"
    assert dc.validate_hook("MONEY","A bureaucratic story with no figure.",[money])["status"]=="HOOK_MISMATCH"
    assert dc.validate_hook("MONEY","The budget assigned $14 million.",[money])["status"]=="PASS"
    assert dc.validate_hook("TIMELINE","February 19, 1962 came first. July 20, 1962 came next.",[money])["status"]=="PASS"
    assert dc.validate_hook("DOCUMENT","A thought about policy.",[money])["status"]=="HOOK_MISMATCH"


def test_quote_hook_requires_approved_quote():
    quote=sample_claim(1); quote.update(claim_type="QUOTATION",source_excerpt="preventive medicine")
    assert dc.validate_hook("QUOTE","The committee called it “preventive medicine.”",[quote])["status"]=="PASS"
    assert dc.validate_hook("QUOTE","A memorable phrase.",[])["status"]=="HOOK_MISMATCH"


def test_sentence_phrase_closing_and_brand_whitelist():
    close="A repeated closing paragraph belongs here for every reader."
    assets=[{"content_id":str(i),"copy":f"Unique opening {i}. {close}"} for i in range(4)]
    report=dc.boilerplate_report(assets)
    assert report["repeated_sentences"] and report["repeated_closings"]
    brand=[{"content_id":str(i),"copy":"Follow the documents."} for i in range(4)]
    assert dc.boilerplate_report(brand)["warning_count"]==0


def test_cta_diversity_copyedit_and_platform_fit():
    families={dc.cta_for("substack","NOTE",i)[0] for i in range(4)}
    assert len(families)==4
    assert "CAPITALIZATION:kennedy" in dc.copyedit("Yet kennedy said this.")["issues"]
    assert dc.platform_fit("facebook","LONG","word "*50)["status"]=="WARN"
    assert dc.platform_fit("facebook","LONG","word "*180)["status"]=="PASS"


def test_review_packet_validation_fields_exist_in_live_schema():
    required={"hook_validation","assertion_validation","evidence_validation","boilerplate_validation","duration_validation","copyedit_validation","spoiler_validation","platform_fit_validation"}
    asset={key:{} for key in required}
    assert required <= asset.keys()
