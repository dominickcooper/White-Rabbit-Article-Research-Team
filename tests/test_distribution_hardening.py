"""Regression tests for the two production copy/validation fixes."""
from copy import deepcopy

import pytest

from white_rabbit import distribution_creative as dc


def claim(text, number=5):
    return {"claim_id":f"CLM-USAIDCIA-P01-{number:03d}","claim_text":text,
            "claim_type":"AGENCY_ASSIGNMENT","support_type":"DIRECT",
            "claim_classification":"DOCUMENTED_FACT","source_number":str(number)}


KENNEDY="Kennedy asked AID to review support for local police forces used for internal security and counterinsurgency."
NSAM="NSAM 162 directed CIA and AID to maintain personnel with paramilitary skills for crisis areas."


@pytest.mark.parametrize("text,number",[(KENNEDY,5),(NSAM,8),
    ("The July committee included representatives from AID and CIA.",24),
    ("CIA and AID were directed to support police training.",8)])
def test_actor_action_is_factual_even_with_support_or_review(text,number):
    c=claim(text,number)
    row=dc.extract_assertions("CONTENT",text,[c["claim_id"]],[c])[0]
    assert row["assertion_type"]=="DIRECT_FACT"
    assert row["support_status"]=="SUPPORTED"
    assert row["claim_ids"]==c["claim_id"]


@pytest.mark.parametrize("text",[
    "The documents support a national-security architecture.",
    "They do not support collapsing every participating agency into one institution.",
    "Read the sequence slowly: the funding proposal, the agency boundaries, the training plan and the deadline are pieces of one administrative design."])
def test_substantive_synthesis_requires_claims(text):
    cs=[claim(NSAM,8),claim("The committee assigned AID operating and funding responsibility except for covert aspects and selected Defense programs.",16)]
    row=dc.extract_assertions("CONTENT",text,[c["claim_id"] for c in cs],cs)[0]
    assert row["assertion_type"]=="SYNTHESIS"
    assert row["support_status"]=="INFERENCE_SUPPORTED"
    assert row["claim_ids"] and row["review_required"]=="YES"
    assert row["classification"]!="DOCUMENTED_FACT"
    assert dc.extract_assertions("CONTENT",text,[],cs)[0]["support_status"]=="UNSUPPORTED"


@pytest.mark.parametrize("text",["Read Part 1 and examine the records yourself.",
    "Which boundary would you investigate next?","Read Part 1.",
    "What do you think?","Follow the documents.","Save this for later."])
def test_plain_invitations_remain_nonfactual(text):
    row=dc.extract_assertions("CONTENT",text,[],[])[0]
    assert row["assertion_type"]=="RHETORICAL_NONFACTUAL"
    assert row["support_status"]=="NONFACTUAL_FRAMING"


@pytest.mark.parametrize("sentence",[
    "Kennedy warned that police programs could be neglected because they were a small part of AID.",
    "The committee assigned AID operating and funding responsibility except for covert aspects and selected Department of Defense programs.",
    "The Agency for International Development reported $14 million on July 20, 1962.",
    'The committee called police assistance “preventive medicine.”',
    'The committee called police assistance "preventive medicine."',
    "The U.S. program cost $5.8 million.",
    "John F. Kennedy asked CIA and AID to review the report."])
def test_shortening_never_cuts_a_complete_unit(sentence):
    cta="Read Part 1."
    limit=dc.x_length(dc.render_copy(sentence,cta))+dc.X_URL_RESERVE
    long=sentence+" "+"Another complete but lower priority sentence. "*8
    body=dc.shorten_x(long,cta,limit=limit)
    assert body==sentence
    assert dc.complete_sentence(body)
    assert dc.render_copy(body,cta)==sentence+"\n\n"+cta
    assert dc.x_length(dc.render_copy(body,cta))+dc.X_URL_RESERVE<=limit


def test_legacy_partial_tail_is_removed_without_punctuation_repair():
    body="AID administered development assistance. The committee assigned funding responsibility e"
    assert dc.shorten_x(body,"Read Part 1.")=="AID administered development assistance."
    with pytest.raises(ValueError,match="no complete sentence"):
        dc.shorten_x("An incomplete named Agency for International", "Read Part 1.")
    with pytest.raises(ValueError,match="no complete sentence"):
        dc.shorten_x("Complete sentence.", "An intact CTA.",limit=10)


def test_assertions_parse_body_and_cta_separately_and_render_the_same_text():
    c=claim(KENNEDY)
    body=dc.shorten_x(KENNEDY+" Lower priority sentence that will be removed.","Read Part 1.",limit=150)
    rows=dc.extract_asset_assertions("CONTENT",body,"Read Part 1.",[c["claim_id"]],[c])
    assert len(rows)==2
    assert rows[0]["assertion_text"]==KENNEDY and rows[0]["text_section"]=="BODY"
    assert rows[1]["assertion_text"]=="Read Part 1." and rows[1]["text_section"]=="CTA"
    assert rows[0]["support_status"]=="SUPPORTED"
    asset={"content_id":"CONTENT","platform":"x","format":"POST","body_copy":body,
           "cta_text":"Read Part 1.","copy":dc.render_copy(body,"Read Part 1."),
           "validated_copy":dc.render_copy(body,"Read Part 1."),"supported_claim_ids":[c["claim_id"]],"assertions":rows}
    assert dc.validate_final_copy(asset,[c])==[]
    changed=deepcopy(asset); changed["copy"]+=" Smuggled extra statement."
    assert dc.validate_final_copy(changed,[c])


def test_thread_budget_includes_numbered_prefix_and_final_cta():
    body=f"1/ {NSAM}\n\n2/ {KENNEDY}"
    cta="Read Part 1."
    assert dc.prepare_x(body,cta,"THREAD")==body
    for i,post in enumerate(body.split("\n\n")):
        text=dc.render_copy(post,cta if i==1 else "")
        assert dc.x_length(text)+(dc.X_URL_RESERVE if i==1 else 0)<=dc.X_LENGTH_LIMIT


def test_four_decisions_warning_survives_shortening():
    sentence="Follow four decisions across 1962, and a police system takes shape in plain sight."
    cs=[claim("NSAM 132 was dated February 19, 1962.",1),claim("NSAM 162 was dated June 19, 1962.",6)]
    body=dc.shorten_x(sentence+" "+cs[0]["claim_text"]+" "+cs[1]["claim_text"],"Read Part 1.")
    rows=dc.extract_asset_assertions("CONTENT",body,"Read Part 1.",[c["claim_id"] for c in cs],cs)
    assert rows[0]["assertion_text"]==sentence
    assert rows[0]["support_status"]=="PARTIALLY_SUPPORTED"


def test_refresh_keeps_saved_non_x_copy_and_stable_assertion_ids():
    c=claim(KENNEDY)
    body=KENNEDY
    cta="Which boundary would you investigate next?"
    old=dc.extract_assertions("WRR-USAIDCIA-P01-TT-MEDIUM-002",dc.render_copy(body,cta),[c["claim_id"]],[c])
    # Simulate the old erroneous classification, retaining its original identity.
    old[0].update(assertion_type="RHETORICAL_NONFACTUAL",support_status="NONFACTUAL_FRAMING",claim_ids="")
    asset={"content_id":"WRR-USAIDCIA-P01-TT-MEDIUM-002","platform":"tiktok","format":"MEDIUM",
           "copy":dc.render_copy(body,cta),"assertions":old,"supported_claim_ids":[c["claim_id"]],
           "hook_validation":{"status":"PASS"},"duration_validation":"PASS",
           "boilerplate_validation":{"status":"WARN"},"status":"APPROVED",
           "evidence_packet":{"approved_claims":[c]}}
    fixed=dc.refresh_asset(asset,[c])
    assert fixed["copy"]==asset["copy"] and fixed["status"]=="APPROVED"
    assert fixed["evidence_packet"]==asset["evidence_packet"]
    assert fixed["assertions"][0]["assertion_id"]==old[0]["assertion_id"]
    assert fixed["assertions"][0]["claim_ids"]==c["claim_id"]
    assert fixed["assertions"][0]["support_status"]=="SUPPORTED"
    assert dc.refresh_asset(fixed,[c])==fixed
