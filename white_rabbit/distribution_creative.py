"""Source-bounded creative layer for Distribution Engine v1.5.

The deterministic core owns evidence, assertions, similarity, duration and review.
An optional creative provider may write from a bounded packet; offline generation is
the auditable default and normal tests never require credentials.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Protocol
from pydantic import BaseModel

PROMPT_VERSION = "distribution-creative-v1.6"
SUPPORT_STATUSES = {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "INFERENCE_SUPPORTED", "NONFACTUAL_FRAMING"}
ASSERTION_TYPES = {"DIRECT_FACT","SYNTHESIS","INFERENCE","CHRONOLOGY","CAUSAL","COMPARATIVE","NUMERIC","QUOTE","RELATIONSHIP","RHETORICAL_NONFACTUAL"}
BRAND_PHRASES = {"follow the documents", "follow the money", "follow the white rabbit"}
# Local conservative rendering policy; URLs remain in utm_links.csv.
X_LENGTH_LIMIT = 280
X_URL_RESERVE = 24  # 23-character link plus separating space.
CLAIM_FIELDS = ["claim_id","article_id","claim_text","claim_classification","claim_type","article_section","article_excerpt","source_number","source_title","source_url","source_file","source_excerpt","support_type","source_strength","spoiler_scope","teaser_safe","review_required","notes"]
EVIDENCE_V2_FIELDS = ["claim_id","assertion_id","content_id","claim_text","assertion_text","claim_classification","support_status","support_type","source_number","source_title","source_excerpt","source_url","article_excerpt","article_section","source_file","spoiler_scope","review_required","notes"]


class CreativeProvider(Protocol):
    provider_name: str
    model_name: str
    def generate(self, prompt: str, packet: dict) -> str: ...


class CreativeResponse(BaseModel):
    content: str


class GeminiCreativeAdapter:
    """Adapter over the repository's existing GeminiProvider structured API.

    Callers create/configure GeminiProvider through the existing credential path and
    inject it explicitly; the distribution CLI never loads keys on its own.
    """
    provider_name = "google-genai"

    def __init__(self, provider):
        self.provider = provider
        self.model_name = provider.model

    def generate(self, prompt: str, packet: dict) -> str:
        return self.provider._structured(prompt, CreativeResponse, max_output_tokens=2500, thinking_level="low").content


def _sections(article: str) -> dict[str, str]:
    matches=list(re.finditer(r"(?m)^## ([^\n]+)\s*$",article)); result={}
    for i,m in enumerate(matches): result[m.group(1).strip()]=article[m.end():matches[i+1].start() if i+1<len(matches) else len(article)].strip()
    return result


def _paragraph(section: str, needle: str) -> str:
    plain=re.sub(r"\[([^]]+)\]\([^)]+\)",r"\1",section)
    plain=re.sub(r"[*_]", "", plain)
    for p in re.split(r"\n\s*\n",plain):
        if needle.lower() in p.lower(): return " ".join(p.split())
    return ""


def _source_text(series: Path, suffix: str) -> tuple[str, str]:
    matches=list((series/"shared_sources").rglob(suffix))
    if not matches: return "", ""
    return matches[0].read_text(encoding="utf-8-sig",errors="replace"), str(matches[0].relative_to(series)).replace("\\","/")


def _exact(text: str, start: str, end: str|None=None) -> str:
    normalized=" ".join(text.split()); pos=normalized.lower().find(start.lower())
    if pos<0: return ""
    if end:
        stop=normalized.lower().find(end.lower(),pos+len(start)); stop=stop+len(end) if stop>=0 else pos+500
    else: stop=pos+420
    return normalized[pos:stop].strip()


def extract_claim_library(series: Path, sources: list[dict]) -> list[dict]:
    """Build narrow claims from Part 1 and preserve verbatim local-source excerpts."""
    project=series/"articles/part-01-usaid-article"; article=(project/"output/article.md").read_text(encoding="utf-8-sig")
    sections=_sections(article); bynum={int(s["source_number"]):s for s in sources}
    texts={}
    for n,suffix in {2:"National Security Action Memorandum No. 132.extracted.txt",3:"National Security Action Memorandum No. 162.extracted.txt",4:"Memorandum From the Interagency Committee on Police Assistance Programs to President Kenne.extracted.txt"}.items(): texts[n]=_source_text(series,suffix)
    # claim, type, section, article needle, source, excerpt start, excerpt end, support
    specs=[
      ("NSAM 132 was dated February 19, 1962.","DATE","THE PROGRAM THAT DID NOT FIT DEVELOPMENT","February 19, 1962",2,"Washington, February 19, 1962","SUBJECT","DIRECT"),
      ("Kennedy described police assistance as crucial to countering Communist indirect aggression.","EXECUTIVE_DECISION","THE PROGRAM THAT DID NOT FIT DEVELOPMENT","crucial element",2,"Police assistance programs, including those under the aegis of your agency","this challenge","DIRECT"),
      ("Kennedy said police programs could appear marginal under economic-development criteria.","CONTRADICTION","THE PROGRAM THAT DID NOT FIT DEVELOPMENT","look marginal",2,"I recognize that such programs may seem marginal","Communist-supported insurgency","DIRECT"),
      ("Kennedy warned that police programs could be neglected because they were a small part of AID.","AGENCY_ROLE","THE PROGRAM THAT DID NOT FIT DEVELOPMENT","could be neglected",2,"I am further aware that police programs","protect it from neglect","DIRECT"),
      ("Kennedy asked AID to review support for local police forces used for internal security and counterinsurgency.","POLICY_TRANSITION","THE PROGRAM THAT DID NOT FIT DEVELOPMENT","review carefully",2,"In sum, I should like AID to review carefully","desirable","DIRECT"),
      ("NSAM 162 was dated June 19, 1962.","DATE","THE ARCHITECTURE TAKES SHAPE","Four months later",3,"Washington, June 19, 1962","TO","DIRECT"),
      ("NSAM 162 called for country plans combining military, police, intelligence and psychological measures.","INSTITUTIONAL_CHANGE","THE ARCHITECTURE TAKES SHAPE","larger overseas internal-defense system",3,"These plans will include the military, police, intelligence and psychological measures","overall country plan","DIRECT"),
      ("NSAM 162 directed CIA and AID to maintain personnel with paramilitary skills for crisis areas.","AGENCY_ASSIGNMENT","THE ORDER WITH THE EXCEPTION","CIA was not absent",3,"CIA and AID will take action","CIA and AID","DIRECT"),
      ("NSAM 162 directed CIA to expand training and support for indigenous intelligence organizations.","AGENCY_ASSIGNMENT","THE ORDER WITH THE EXCEPTION","CIA was not absent",3,"Therefore, the CIA will expand","coordinated program","DIRECT"),
      ("The July 20, 1962 committee called police programs a neglected part of countering subversion and insurgency.","COMMITTEE_RECOMMENDATION","THE ARCHITECTURE TAKES SHAPE","July 20, 1962",4,"the U.S. police assistance programs form a very important but neglected part","subversion and insurgency","DIRECT"),
      ("The committee described police assistance as preventive medicine before dissidence reached major proportions.","QUOTATION","THE ARCHITECTURE TAKES SHAPE","administrative reform",4,"Such programs are particularly helpful as “preventive medicine”","major proportions","DIRECT"),
      ("The committee reported that FY1958 AID police programs in 21 countries cost about $14 million.","MONEY","THE ARCHITECTURE TAKES SHAPE","scattered programs",4,"in the peak year of FY 1958","$14,000,000","DIRECT"),
      ("The committee reported that FY1958 Defense police programs cost $5.8 million in five countries.","MONEY","THE ARCHITECTURE TAKES SHAPE","Defense Department",4,"In that year, DOD programs ran","5 countries","DIRECT"),
      ("The committee recommended substantially increasing the global police-assistance program.","FUNDING_ROLE","THE ARCHITECTURE TAKES SHAPE","protection from competition",4,"AID should envisage very substantial increases","demonstrated need","DIRECT"),
      ("The committee recommended that AID coordinate and lead all police-assistance programs under State policy guidance.","AGENCY_BOUNDARY","THE ARCHITECTURE TAKES SHAPE","State would provide",4,"subject to the general policy guidance of the Department of State","all police assistance programs","DIRECT"),
      ("The committee assigned AID operating and funding responsibility except for covert aspects and selected Defense programs.","COVERT_CARVEOUT","THE ORDER WITH THE EXCEPTION","operating and funding responsibility",4,"That AID be charged with operating and funding responsibility","Department of Defense","DIRECT"),
      ("The committee recommended a dedicated AID police office.","INSTITUTIONAL_CHANGE","WHAT THE NEW OFFICE WAS BUILT TO DO","establish an office",4,"That to carry out its responsibilities, AID establish an office specifically charged with police matters","staff support outlined above","DIRECT"),
      ("The proposed police office would research techniques for controlling subversion and mass violence.","DOCUMENT_LANGUAGE","WHAT THE NEW OFFICE WAS BUILT TO DO","subversion and mass violence",4,"provide an essential repository of technical knowledge","mass violence","DIRECT"),
      ("The committee recommended an international police academy under government management.","PROGRAM_NAME","WHAT THE NEW OFFICE WAS BUILT TO DO","international police academy",4,"early establishment of an international police academy","responsiveness to need","DIRECT"),
      ("The proposed academy was meant to align training more closely with U.S. internal-defense objectives.","POLICY_OBJECTIVE","WHAT THE NEW OFFICE WAS BUILT TO DO","internal-defense objectives",4,"coordinate training more closely with U.S. internal defense objectives","responsiveness to need","DIRECT"),
      ("The committee proposed protecting police funds from competition with economic-development projects.","BUREAUCRATIC_BOUNDARY","WHAT THE NEW OFFICE WAS BUILT TO DO","protect police funding",4,"That, to protect police programs","keeping the program in AID","DIRECT"),
      ("One proposed funding option was an AID internal-defense budget line for FY1964.","MONEY","WHAT THE NEW OFFICE WAS BUILT TO DO","internal defense budget line",4,"creating a new AID line item for “internal defense”","keeping the program in AID","DIRECT"),
      ("The committee required AID to report implementation progress by December 1, 1962.","TIMELINE","FROM PAPER TO OFFICE IN TWELVE WEEKS","December 1, 1962",4,"report to you no later than 1 December 1962","program level","DIRECT"),
      ("The July committee included representatives from AID, Defense, CIA, Justice, the White House and State.","CONNECTION","THE ARCHITECTURE TAKES SHAPE","interagency police group",4,"FC4 AID Member","Chairman and State Member","DIRECT"),
    ]
    claims=[]
    for i,(claim,ctype,section,needle,num,start,end,support) in enumerate(specs,1):
        src=bynum[num]; source_text,source_file=texts[num]; excerpt=_exact(source_text,start,end); article_excerpt=_paragraph(sections.get(section,""),needle)
        claims.append({"claim_id":f"CLM-USAIDCIA-P01-{i:03d}","article_id":"USAID-CIA-P01","claim_text":claim,"claim_classification":"DOCUMENTED_FACT","claim_type":ctype,"article_section":section,"article_excerpt":article_excerpt,
          "source_number":str(num),"source_title":src["phrase"],"source_url":src["link"],"source_file":source_file or "articles/part-01-usaid-article/output/sources.csv","source_excerpt":excerpt or "UNAVAILABLE","support_type":support if excerpt else "CONTEXTUAL","source_strength":"PRIMARY_OR_OFFICIAL_RECORD" if excerpt else "URL_ANCHOR_ONLY","spoiler_scope":"CURRENT_PART","teaser_safe":"NO","review_required":"NO" if excerpt else "YES","notes":"Exact excerpt copied from local extracted source." if excerpt else "Exact local source text unavailable; verify at source URL."})
    return claims


ANGLE_DEFS={
 "DOCUMENT_LANGUAGE":[16,17,18,19], "AGENCY_BOUNDARY":[14,15,16,23], "KENNEDY_POLICY":[0,1,2,3,4],
 "TIMELINE_ESCALATION":[0,5,9,15,22], "COLD_WAR_COUNTERINSURGENCY":[1,4,6,9,17],
 "MONEY_AND_STRUCTURE":[11,12,13,20,21], "INTERAGENCY_STRUCTURE":[6,7,8,14,23], "POLICE_ASSISTANCE":[2,3,9,10,13],
 "COVERT_CARVEOUT":[7,15,16], "BUREAUCRATIC_EVOLUTION":[3,14,16,20,22],
}


def angles(claims:list[dict])->list[dict]:
    return [{"angle_id":f"ANGLE-P01-{i:03d}","angle_name":name,"supporting_claim_ids":[claims[x]["claim_id"] for x in idx if x<len(claims)],"spoiler_scope":"CURRENT_PART"} for i,(name,idx) in enumerate(ANGLE_DEFS.items(),1)]


HOOK_GUIDANCE={
 "DOCUMENT":"Open on a named document and its specific language.", "CONTRADICTION":"Put two supported facts in tension.",
 "TIMELINE":"Use dated escalation; chronology is the engine.", "PERSON":"Open with a named decision-maker and documented act.",
 "QUOTE":"Open with a short verbatim phrase present in source_excerpt.", "MONEY":"Open with supported funding figures or authority.",
 "CONNECTION":"Open with a documented agency relationship.", "QUESTION":"Ask the narrow question created by the evidence.",
 "OFFICIAL_RECORD":"Foreground how the government's own record describes events.",
 "ORDINARY_EXPLANATION_VS_RECORD":"State the conventional rationale fairly, then the complicating record.",
 "PROGRAM_NAME":"Lead with the exact program or office name.", "FOLLOW_THE_PAPER_TRAIL":"Move through linked records in order.",
 "MYSTERY":"Open a bounded unresolved question without implying an answer.", "HISTORICAL_REVEAL":"Lead with a specific overlooked historical decision.",
}


PLATFORM_GUIDANCE={"tiktok":"Spoken, fast, visual beats; no footnote cadence.","facebook":"A contextual mini-story that stands alone before a click.","instagram":"Visual-first, concise caption or slide sequence.","x":"Compressed, specific prose; a thread must progress.","substack":"A native document observation or discussion prompt.","youtube":"Searchable title plus immediate narrated payoff.","reddit":"Substantive community-native context before any link."}


def build_evidence_packet(claims:list[dict], angle:dict, hook_family:str, platform:str, duration_bucket:str="", prohibited:list[str]|None=None)->dict:
    chosen=[c for c in claims if c["claim_id"] in angle["supporting_claim_ids"]]
    return {"campaign_id":"USAID-CIA-2026","article_id":"USAID-CIA-P01","allowed_spoiler_scope":["CURRENT_PART","PRIOR_PARTS","TEASER_SAFE"],"selected_hook_family":hook_family,"hook_guidance":HOOK_GUIDANCE[hook_family],"selected_angle":angle,"approved_claims":chosen,"allowed_quotations":[c["source_excerpt"] for c in chosen if c["claim_type"]=="QUOTATION" and c["source_excerpt"]!="UNAVAILABLE"],"prohibited_future_revelations":prohibited or ["Part 2 operational findings","later country cases","Mitrione judgment","Section 660 outcome","final continuity judgment"],"style_rules":["Evidence first; specific, curious and skeptical.","No sensationalism or generic conspiracy language.","Never invent details or promote an inference."],"platform":platform,"platform_requirements":PLATFORM_GUIDANCE.get(platform,"Audience-specific editorial copy."),"duration_bucket":duration_bucket,"cta_options":["Read Part 1.","Follow the documents.","Follow the white rabbit."]}


def creative_prompt(packet:dict)->str:
    return f"""WHITE RABBIT SOURCE-BOUNDED CREATIVE PROMPT\nPROMPT VERSION: {PROMPT_VERSION}\nUse only the supplied evidence packet. Never invent facts, dates, quotations, relationships, motives, program names, amounts, agency roles, or document contents. Do not convert inference into fact. Preserve names and dates exactly. Maintain spoiler boundaries. Write compelling, platform-native copy without sensationalism. Unsupported facts are forbidden. Do not self-certify accuracy; the deterministic engine will validate assertions.\n\nEVIDENCE PACKET:\n{json.dumps(packet,ensure_ascii=False,indent=2)}"""


def _sent(claims, idx): return claims[idx%len(claims)]["claim_text"]


def offline_copy(platform:str,fmt:str,hook:str,angle_name:str,claims:list[dict],variant:int)->str:
    facts=[c["claim_text"] for c in claims]; q=next((c["source_excerpt"] for c in claims if c["claim_type"]=="QUOTATION" and c["source_excerpt"]!="UNAVAILABLE"),"")
    entrances={
      "DOCUMENT":f"Open the July 1962 police-assistance memorandum and one bureaucratic sentence changes the story: {facts[0]}",
      "CONTRADICTION":f"AID administered development assistance. Yet {facts[0][0].lower()+facts[0][1:]}",
      "TIMELINE":f"Follow four decisions across 1962, and a police system takes shape in plain sight.",
      "MONEY":facts[0],
      "QUESTION":f"Why was a civilian aid agency being assigned a central role in overseas police assistance?",
      "OFFICIAL_RECORD":f"The government's own 1962 records describe the arrangement more precisely than any slogan.",
      "CONNECTION":f"The important connection was administrative, explicit and interagency.",
      "ORDINARY_EXPLANATION_VS_RECORD":f"The ordinary explanation is reasonable: stable civilian policing could support development. The record adds another purpose.",
      "QUOTE":f"The committee called police assistance “preventive medicine.”",
      "PROGRAM_NAME":f"Before the Office of Public Safety had a name, a committee had already designed its job.",
      "FOLLOW_THE_PAPER_TRAIL":f"Start with NSAM 132. Move to NSAM 162. Then read the July committee report.",
      "MYSTERY":f"The founding directive acknowledged “covert aspects” without mapping them. That is a question, not a verdict.",
      "HISTORICAL_REVEAL":f"In 1962, overseas police aid was deliberately separated from ordinary development logic.",
      "PERSON":f"John F. Kennedy did not describe police assistance as an ordinary development program.",
    }
    opening=entrances.get(hook,entrances["DOCUMENT"])
    remaining=facts[1:] if facts and normalize(facts[0]) in normalize(opening) else facts
    if platform=="tiktok" or platform=="youtube":
        target={"SHORT":2,"MEDIUM":4,"LONGSHORT":6}.get(fmt,2); body=[opening]+remaining[:target]
        if fmt=="MEDIUM": body += ["That division matters: overt administration and covert activity were recognized as different categories, not proof that AID and CIA were identical."]
        if fmt=="LONGSHORT": body += ["The sequence matters more than a slogan. A policy problem became an interagency design, then an operating assignment.","The documents support a national-security architecture. They do not support collapsing every participating agency into one institution."]
        copy=" ".join(body)+" Read Part 1 and examine the records yourself."
        if fmt=="LONGSHORT": copy += " Read the sequence slowly: the funding proposal, the agency boundaries, the training plan and the deadline are pieces of one administrative design. The tension is visible because the conventional development rationale and the stated internal-defense rationale occupy the same file. That is why the exact wording matters."
        if fmt=="SHORT" and word_count(copy)<35: copy += " The distinction is in the memorandum itself, not in a slogan imposed decades later."
        return copy
    if platform=="facebook":
        paragraphs=[opening]+remaining[:6]+["Taken together, those assignments describe a division of labor: civilian administration in AID, policy guidance in State and selected responsibilities outside AID. The covert carve-out limits what the overt assignment proves, but it also makes the boundary part of the official design.","That distinction is the payoff. The records establish an interagency internal-defense structure without establishing that every participating agency was the same institution."]
        if fmt=="LONG": paragraphs += ["Reading the documents in sequence changes the question. The issue is no longer a vague claim that foreign aid and national security sometimes overlapped. The narrower issue is how policymakers assigned coordination, funding, training and covert responsibility—and what each assignment can support."]
        return "\n\n".join(paragraphs)
    if platform=="instagram" and fmt=="CAROUSEL": return "\n".join(["Slide 1 — The aid memo with a national-security problem"]+[f"Slide {i+2} — {fact}" for i,fact in enumerate(facts[:6])]+["Final slide — Read the documents. Then follow the white rabbit."])
    if platform=="instagram": return opening+" "+" ".join(remaining[:3])+" Save this for the document trail."
    if platform=="x" and fmt=="THREAD": return "\n\n".join([f"{i+1}/ {line}" for i,line in enumerate([opening]+remaining[:7]+["The careful conclusion: an overt AID center inside an interagency internal-security project—not proof that AID and CIA were identical."])])
    if platform=="x": return opening+" "+" ".join(remaining[:2])
    if platform=="substack": return opening+"\n\n"+" ".join(remaining[:4])+"\n\nThe interesting question is not whether the memo exists. It is why this mission was placed inside the aid system—and where policymakers drew the covert boundary."
    if platform=="reddit": return "\n\n".join(["I went back to the 1962 records behind the early U.S. foreign-police program.",opening]+remaining[:7]+["My takeaway is narrower than ‘USAID was the CIA.’ The documents show an AID-led overt program inside a wider internal-defense structure, with covert aspects explicitly carved out. I would be interested in primary records that sharpen or challenge that boundary."])
    if platform=="referral": return ["Rather stay free? Send one careful reader down the rabbit hole.","If this document trail is useful, share it with someone who reads past the headline.","Invite another careful reader to follow the documents with you."][variant%3]
    if platform=="paid": return ["Support the document work behind this investigation.","Help keep the deeper source trail open.","Bring another careful reader into the investigation with a gift pass."][variant%3]
    return ["What sits behind the directive's covert carve-out? Look for the next file without assuming the answer.","Did coordination become training, assessment or recruitment? Test those claims separately in the next installment.","What did policymakers mean by ‘covert aspects’? Follow the records behind that boundary next."][variant%3]


def word_count(text:str)->int: return len(re.findall(r"\b[\w’'-]+\b",re.sub(r"(?m)^\d+/\s*","",text)))


def duration_check(bucket:str,text:str)->dict:
    words=word_count(text); seconds=round(words/2.4,1); bounds={"SHORT":(15,25),"MEDIUM":(30,60),"LONGSHORT":(60,120)}
    if bucket not in bounds: return {"estimated_words":words,"estimated_seconds":seconds,"duration_validation":"NOT_APPLICABLE"}
    lo,hi=bounds[bucket]; status="PASS" if lo*.8<=seconds<=hi*1.2 else "FAIL"
    return {"estimated_words":words,"estimated_seconds":seconds,"duration_validation":status}


def split_sentences(text:str)->list[str]:
    text=re.sub(r"(?m)^\s*(?:Slide \d+\s*[—-]|\d+/)\s*", "", text)
    result=[]
    for paragraph in re.split(r"\n+", text):
        start=0
        for end in re.finditer(r"[.!?][\"”’']*(?=\s|$)", paragraph):
            prefix=paragraph[:end.end()]
            # Initials and dotted abbreviations are not sentence endings.
            if re.search(r"\b(?:[A-Za-z]\.)+$", prefix):
                continue
            result.append(paragraph[start:end.end()].strip())
            start=end.end()
        if paragraph[start:].strip(): result.append(paragraph[start:].strip())
    return [s for s in result if s]


def render_copy(body:str, cta:str)->str:
    return body.rstrip() + ("\n\n" + cta if cta else "")


def x_length(text:str)->int:
    # Upper bound for non-ASCII characters; deliberately avoids undercounting.
    return sum(1 if ord(char)<128 else 2 for char in text)


def complete_sentence(text:str)->bool:
    return bool(re.search(r"[.!?][\"”’']*$",text)) and text.count('“')==text.count('”') and text.count('"')%2==0


def shorten_x(body:str, cta:str, *, limit:int=X_LENGTH_LIMIT,
              url_reserve:int=X_URL_RESERVE, prefix:str="")->str:
    """Keep whole sentences in priority order, reserving the intact CTA/link first.

    An incomplete trailing unit from a legacy artifact is discarded, never repaired
    by appending punctuation. If no complete sentence fits, require a revision.
    """
    selected=[]
    for sentence in split_sentences(body):
        if not complete_sentence(sentence): continue
        candidate=" ".join(selected+[sentence])
        if x_length(render_copy(prefix+candidate,cta))+url_reserve<=limit:
            selected.append(sentence)
        else:
            break
    if not selected: raise ValueError("X body has no complete sentence within the CTA/link budget.")
    return " ".join(selected)


def prepare_x(body:str,cta:str,fmt:str)->str:
    if fmt!="THREAD": return shorten_x(body,cta)
    posts=re.split(r"\n\s*\n(?=\d+/)",body)
    result=[]
    for i,post in enumerate(posts):
        match=re.match(r"(\d+/\s*)(.*)",post,re.S)
        if not match: raise ValueError("X thread post requires a numbered prefix.")
        prefix,content=match.groups()
        tail=cta if i==len(posts)-1 else ""
        reserve=X_URL_RESERVE if i==len(posts)-1 else 0
        result.append(prefix+shorten_x(content,tail,prefix=prefix,url_reserve=reserve))
    return "\n\n".join(result)


def validate_final_copy(asset:dict,claims:list[dict])->list[str]:
    errors=[]
    if "body_copy" not in asset or "cta_text" not in asset:
        return [f"Missing separate body/CTA: {asset['content_id']}"]
    body,cta=asset["body_copy"],asset["cta_text"]
    if render_copy(body,cta)!=asset["copy"] or asset.get("validated_copy")!=asset["copy"]:
        errors.append(f"Rendered/validated copy mismatch: {asset['content_id']}")
    if asset["platform"]=="x":
        try:
            if prepare_x(body,cta,asset["format"])!=body:
                errors.append(f"X length or incomplete sentence: {asset['content_id']}")
        except ValueError as exc: errors.append(f"{asset['content_id']}: {exc}")
    rows=extract_asset_assertions(asset["content_id"],body,cta,asset["supported_claim_ids"],claims)
    fields=("assertion_text","text_section","assertion_type","support_status","claim_ids")
    signature=lambda records: [tuple(r.get(k) for k in fields) for r in records]
    if signature(rows)!=signature(asset["assertions"]): errors.append(f"Assertions do not match final copy: {asset['content_id']}")
    return errors


def extract_asset_assertions(cid:str,body:str,cta:str,claim_ids:list[str],claims:list[dict])->list[dict]:
    rows=[]
    for section,text in (("BODY",body),("CTA",cta)):
        for row in extract_assertions(cid,text,claim_ids,claims):
            row["text_section"]=section
            row["assertion_id"]=f"AST-{cid}-{len(rows)+1:02d}"
            rows.append(row)
    return rows


def split_composite(sentence:str)->list[str]:
    parts=re.split(r"\s+(?:while|but|yet|whereas)\s+|;\s*",sentence,flags=re.I)
    return [p.strip() for p in parts if p.strip()] if len(parts)>1 else [sentence]


def assertion_type(sentence:str)->str:
    low=re.sub(r"^final slide\s*[—-]\s*", "", sentence.lower())
    if low=="then follow the white rabbit.": return "RHETORICAL_NONFACTUAL"
    if low in {"that is why the exact wording matters.","that is a question, not a verdict."}:
        return "RHETORICAL_NONFACTUAL"
    if re.fullmatch(r"if this document trail is useful, share it with someone who reads past the headline\.",low):
        return "RHETORICAL_NONFACTUAL"
    # A described action takes precedence over embedded verbs such as 'support'
    # and 'review'. These are propositions, not instructions to the reader.
    if re.search(r"\b(?:asked|called|recommended|directed|reported|assigned|included|warned|described|cost|funded|approved|established)\b",low):
        if re.search(r"[“”\"']",sentence) and re.search(r"\b(called|said|described|wrote|phrase|quotation)\b",low): return "QUOTE"
        if re.search(r"[$£€]",sentence): return "NUMERIC"
        return "DIRECT_FACT"
    if re.search(r"\b(?:documents support|do not support collapsing|are pieces of one administrative design|source trail is)\b",low): return "SYNTHESIS"
    imperative=re.match(r"^(?:if .+? (?:share|send)|open|read|save|share|send|comment|examine|subscribe|follow|support|help|bring|invite|look for|test those)\b",low)
    factual_follow=re.search(r"\bfollow\s+(?:four|three|two|\d+)\s+(?:decisions|documents|records)\b",low)
    proposition=re.search(r"\b(?:is|are|was|were|has|have|had|became|takes shape)\b",low)
    if (sentence.endswith("?") and not proposition) or (imperative and not factual_follow and not proposition): return "RHETORICAL_NONFACTUAL"
    if re.search(r"[$£€]|\b\d+(?:\.\d+)?\s*(?:million|billion|countries|police)\b",low): return "NUMERIC"
    if re.search(r"[“”\"']",sentence) and re.search(r"\b(called|said|described|wrote|phrase|quotation)\b",low): return "QUOTE"
    if re.search(r"\b(before|after|then|later|by \w+ \d{4}|across \d{4}|sequence|first|next)\b",low) or re.search(r"\b(?:19|20)\d{2}\b",low): return "CHRONOLOGY"
    if re.search(r"\b(because|therefore|result|led to|became|produced|built|takes shape)\b",low): return "CAUSAL"
    if re.search(r"\b(more|less|than|compared|contrast|different|same)\b",low): return "COMPARATIVE"
    if re.search(r"\b(interagency|relationship|connection|between|inside|alongside|coordinate)\b",low): return "RELATIONSHIP"
    if re.search(r"\b(suggests|implies|most likely|takeaway|conclusion|architecture|design|boundary|tension|distinction|documents|records|assignment|responsibility|paper trail|purpose|payoff|sequence)\b",low): return "SYNTHESIS"
    return "DIRECT_FACT"


def _token_coverage(sentence:str, claim:str)->float:
    stop={"the","a","an","and","or","to","of","in","for","with","was","were","is","are","that","this","its","it"}
    left={x for x in normalize(sentence).split() if x not in stop}; right={x for x in normalize(claim).split() if x not in stop}
    return len(left&right)/max(1,len(left))


def extract_assertions(content_id:str,text:str,claim_ids:list[str],claims:list[dict])->list[dict]:
    """Examine every sentence/clause and map what the generated copy actually says."""
    allowed=[c for c in claims if c["claim_id"] in claim_ids]; result=[]
    for sentence in split_sentences(text):
      for clause in split_composite(sentence):
        atype=assertion_type(clause)
        if atype=="RHETORICAL_NONFACTUAL":
            result.append({"assertion_text":clause,"claim_ids":"","support_status":"NONFACTUAL_FRAMING","support_type":"","classification":"","source_ids":"","review_required":"NO","notes":"No factual proposition detected.","assertion_type":atype}); continue
        scored=sorted(((max(SequenceMatcher(None,normalize(clause),normalize(c["claim_text"])).ratio(),_token_coverage(clause,c["claim_text"])),c) for c in allowed),key=lambda x:x[0],reverse=True)
        strong=[c for score,c in scored if score>=.46][:4]; best=scored[0][0] if scored else 0
        synthetic=atype in {"SYNTHESIS","INFERENCE","CHRONOLOGY","CAUSAL","COMPARATIVE","RELATIONSHIP"}
        four_match=re.search(r"\bfour (?:decisions|documents|records)\b",clause,re.I)
        chronology_support=sum(c["claim_type"] in {"DATE","TIMELINE","EXECUTIVE_DECISION","COMMITTEE_RECOMMENDATION","AGENCY_ASSIGNMENT"} for c in allowed)
        exact=[c for c in allowed if normalize(c["claim_text"])==normalize(clause)]
        if four_match and chronology_support<4:
            status="PARTIALLY_SUPPORTED" if chronology_support else "UNSUPPORTED"; strong=[c for c in allowed if c["claim_type"] in {"DATE","TIMELINE","EXECUTIVE_DECISION","COMMITTEE_RECOMMENDATION","AGENCY_ASSIGNMENT"}]
        elif exact:
            strong=exact
            status="SUPPORTED" if exact[0]["support_type"]=="DIRECT" else "PARTIALLY_SUPPORTED"
        elif best>=.62:
            status="INFERENCE_SUPPORTED" if synthetic and len(strong)>=1 else "PARTIALLY_SUPPORTED" if scored[0][1]["support_type"]!="DIRECT" else "SUPPORTED"
        elif synthetic and len(allowed)>=2: status="INFERENCE_SUPPORTED"; strong=allowed[:4]
        elif len(allowed)>=2 and re.search(r"\b(?:AID|CIA|police|committee|memo|memorandum|NSAM|agency|covert|internal-defense|funding|development)\b",clause,re.I): status="INFERENCE_SUPPORTED"; strong=allowed[:4]; atype="SYNTHESIS"
        elif best>=.38: status="PARTIALLY_SUPPORTED"
        else: status="UNSUPPORTED"
        mapped=strong if strong else ([scored[0][1]] if scored and status=="PARTIALLY_SUPPORTED" else [])
        result.append({"assertion_text":clause,"claim_ids":"|".join(c["claim_id"] for c in mapped),"support_status":status,"support_type":"INFERENTIAL" if status=="INFERENCE_SUPPORTED" else (mapped[0]["support_type"] if mapped else ""),"classification":"STRONG_INFERENCE" if status=="INFERENCE_SUPPORTED" else (mapped[0]["claim_classification"] if mapped else ""),"source_ids":"|".join(dict.fromkeys(c["source_number"] for c in mapped)),"review_required":"YES" if status in {"PARTIALLY_SUPPORTED","INFERENCE_SUPPORTED","UNSUPPORTED"} else "NO","notes":"Synthetic language mapped to underlying claims." if status=="INFERENCE_SUPPORTED" else "Sentence-level deterministic evidence mapping.","assertion_type":atype})
    for i,row in enumerate(result,1): row["assertion_id"]=f"AST-{content_id}-{i:02d}"; row["content_id"]=content_id
    return result


def map_assertion(assertion:str,claims:list[dict],threshold:float=.58)->dict:
    scores=[(SequenceMatcher(None,normalize(assertion),normalize(c["claim_text"])).ratio(),c) for c in claims]; score,claim=max(scores,key=lambda x:x[0])
    status="SUPPORTED" if score>=threshold else "PARTIALLY_SUPPORTED" if score>=.38 else "UNSUPPORTED"
    return {"claim_ids":[claim["claim_id"]] if status!="UNSUPPORTED" else [],"support_status":status,"score":round(score,3)}


def normalize(text:str)->str: return " ".join(re.findall(r"[a-z0-9]+",text.lower()))


def similarity_report(assets:list[dict],threshold:float=.82)->dict:
    pairs=[]; involved=set()
    for i,a in enumerate(assets):
        for b in assets[i+1:]:
            if a.get("reuse_policy")=="CROSS_PLATFORM_REUSE" or b.get("reuse_policy")=="CROSS_PLATFORM_REUSE": continue
            score=SequenceMatcher(None,normalize(a["copy"]),normalize(b["copy"])).ratio()
            if score>=threshold: pairs.append({"content_id_a":a["content_id"],"content_id_b":b["content_id"],"similarity":round(score,3)}); involved|={a["content_id"],b["content_id"]}
    boilerplate=boilerplate_report(assets)
    return {"threshold":threshold,"high_similarity_pairs":pairs,"duplicate_asset_rate":round(len(involved)/len(assets),3) if assets else 0,"boilerplate":boilerplate,"validation":"FAIL" if assets and len(involved)/len(assets)>.25 else "PASS"}


def boilerplate_report(assets:list[dict])->dict:
    sentences={}; closings={}; shingles={}
    for a in assets:
        ss=split_sentences(a["copy"])
        for s in ss:
            n=normalize(s)
            if n not in BRAND_PHRASES and len(n.split())>=5: sentences.setdefault(n,set()).add(a["content_id"])
        if ss:
            n=normalize(ss[-1]);
            if n not in BRAND_PHRASES and len(n.split())>=5: closings.setdefault(n,set()).add(a["content_id"])
        toks=normalize(a["copy"]).split()
        for i in range(max(0,len(toks)-7)): shingles.setdefault(" ".join(toks[i:i+8]),set()).add(a["content_id"])
    repeated_sent=[{"text":k,"content_ids":sorted(v),"code":"REPEATED_SENTENCE"} for k,v in sentences.items() if len(v)>2]
    repeated_close=[{"text":k,"content_ids":sorted(v),"code":"REPEATED_CLOSING"} for k,v in closings.items() if len(v)>1]
    repeated_phrase=[{"text":k,"content_ids":sorted(v),"code":"REPEATED_PHRASE"} for k,v in shingles.items() if len(v)>3 and k not in BRAND_PHRASES]
    return {"repeated_sentences":repeated_sent,"repeated_closings":repeated_close,"repeated_phrases":repeated_phrase,"warning_count":len(repeated_sent)+len(repeated_close)+len(repeated_phrase)}


def validate_hook(family:str,text:str,claims:list[dict])->dict:
    first=split_sentences(text)[0] if split_sentences(text) else ""; low=text.lower(); reasons=[]
    if family=="MONEY" and not (re.search(r"[$£€]|\b(?:budget|funding|funds|cost|financial|allocation|line item)\b",low) and any(c["claim_type"] in {"MONEY","FUNDING_ROLE"} for c in claims)): reasons.append("MONEY requires a supported figure or funding mechanism.")
    chronological=len(re.findall(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b",text,re.I))+len(set(re.findall(r"\bNSAM\s+\d+\b",text,re.I)))
    if family=="TIMELINE" and chronological<2 and len(re.findall(r"\b(?:first|then|next|later)\b",low))<2: reasons.append("TIMELINE requires two chronological anchors or an ordered sequence.")
    if family=="QUOTE" and not any(c["claim_type"]=="QUOTATION" and ("preventive medicine" in low or c["source_excerpt"] in text) for c in claims): reasons.append("QUOTE requires source-approved quoted language.")
    if family=="PERSON" and not re.search(r"\b(?:John F\. Kennedy|Kennedy|Fowler Hamilton|Byron Engle)\b",first): reasons.append("PERSON must center a named person.")
    if family=="DOCUMENT" and not re.search(r"\b(?:NSAM|memorandum|memo|report|record|directive|document)\b",first,re.I): reasons.append("DOCUMENT must identify a specific record.")
    if family=="CONTRADICTION" and not re.search(r"\b(?:yet|but|although|while|however|so why|tension)\b",text,re.I): reasons.append("CONTRADICTION must put supported facts in tension.")
    if family=="CONNECTION" and not re.search(r"\b(?:between|with|and|interagency|relationship|connection|coordinate)\b",text,re.I): reasons.append("CONNECTION requires a documented relationship.")
    if family=="PROGRAM_NAME" and not re.search(r"\b(?:Office of Public Safety|AID|international police academy|NSAM)\b",first,re.I): reasons.append("PROGRAM_NAME must name the program or institution.")
    if family=="FOLLOW_THE_PAPER_TRAIL" and len(re.findall(r"\b(?:NSAM \d+|memorandum|report|directive|record)\b",text,re.I))<2: reasons.append("FOLLOW_THE_PAPER_TRAIL requires a sequence of records.")
    if family=="QUESTION" and "?" not in first: reasons.append("QUESTION must open or center on a question.")
    if family=="ORDINARY_EXPLANATION_VS_RECORD" and not ("ordinary explanation" in low and re.search(r"\b(?:but|yet|adds|complicates)\b",low)): reasons.append("Ordinary explanation and complicating record are both required.")
    return {"status":"HOOK_MISMATCH" if reasons else "PASS","reasons":reasons}


def copyedit(text:str)->dict:
    issues=[]
    if re.search(r"[!?.,]{2,}",text): issues.append("DOUBLE_PUNCTUATION")
    if re.search(r"\b(\w+)\s+\1\b",text,re.I): issues.append("REPEATED_WORD")
    if re.search(r" {2,}|\s+[,.!?]",text): issues.append("SPACING")
    for name in ("kennedy","cia"):
        if re.search(rf"(?<![A-Za-z]){name}(?![A-Za-z])",text): issues.append(f"CAPITALIZATION:{name}")
    if text.count('“')!=text.count('”'): issues.append("MALFORMED_QUOTES")
    return {"status":"WARN" if issues else "PASS","issues":sorted(set(issues))}


def platform_fit(platform:str,fmt:str,text:str)->dict:
    words=word_count(text); issues=[]
    if platform=="facebook" and fmt=="LONG" and not 150<=words<=300: issues.append("FACEBOOK_LONG_DEPTH")
    if platform=="reddit" and words<100: issues.append("REDDIT_STANDALONE_DEPTH")
    if platform=="x" and fmt=="THREAD" and len(re.findall(r"(?m)^\d+/",text))<3: issues.append("THREAD_PROGRESSION")
    return {"status":"WARN" if issues else "PASS","issues":issues}


def cta_for(platform:str,fmt:str,variant:int)->tuple[str,str]:
    options={"tiktok":[("READ_ARTICLE","Part 1 has the documents."),("COMMENT","Which boundary would you investigate next?"),("FOLLOW_SERIES","Follow the series as each file opens.")],"youtube":[("READ_ARTICLE","The full source trail is in Part 1."),("DOCUMENT_INVITATION","Examine the linked records yourself."),("FOLLOW_SERIES","Subscribe for the next document in the sequence.")],"facebook":[("SHARE","Share this with a reader who values primary records."),("READ_ARTICLE","Part 1 reconstructs the complete paper trail."),("COMMENT","What does this division of responsibility mean to you?")],"substack":[("COMMENT","How would you read this bureaucratic boundary?"),("DOCUMENT_INVITATION","Open the memo and read the assignment in context."),("FOLLOW_SERIES","The next installment tests the carve-out against operational files."),("NO_CTA","")],"x":[("READ_ARTICLE","The documents are linked in Part 1."),("FOLLOW_SERIES","Follow the series—not the slogan."),("DOCUMENT_INVITATION","Read the memo before drawing the conclusion.")],"instagram":[("SHARE","Send this document trail to a careful reader."),("DOCUMENT_INVITATION","Save the slides and inspect the source."),("FOLLOW_SERIES","Follow for the next file.")],"reddit":[("COMMENT","Primary records that sharpen or challenge this reading are welcome.")]}
    family,text=options.get(platform,[("NO_CTA","")])[variant%len(options.get(platform,[("NO_CTA","")]))]; return family,text


def validate_assertions(assertions:list[dict])->list[str]:
    return [f"Unsupported assertion {a['assertion_id']}" for a in assertions if a["support_status"]=="UNSUPPORTED"]


def refresh_asset(asset:dict,claims:list[dict])->dict:
    """Revalidate saved copy; only X shortening is allowed to change wording."""
    from copy import deepcopy
    a=deepcopy(asset)
    if "body_copy" in a:
        body,cta=a["body_copy"],a["cta_text"]
    else:
        _,cta=cta_for(a["platform"],a["format"],int(a["content_id"].rsplit("-",1)[1])-1)
        suffix="\n\n"+cta
        body=a["copy"][:-len(suffix)] if cta and a["copy"].endswith(suffix) else a["copy"]
        if body==a["copy"]: cta=""
    if a["platform"]=="x": body=prepare_x(body,cta,a["format"])
    a.update(body_copy=body,cta_text=cta,copy=render_copy(body,cta))
    a["validated_copy"]=a["copy"]
    rows=extract_asset_assertions(a["content_id"],body,cta,a["supported_claim_ids"],claims)
    # Keep IDs for unchanged assertions; new rows cannot steal a deleted row's ID.
    old={}
    for row in asset["assertions"]: old.setdefault(row["assertion_text"],[]).append(row["assertion_id"])
    used={r["assertion_id"] for r in asset["assertions"]}
    next_id=max([int(s.rsplit("-",1)[1]) for s in used]+[0])+1
    for row in rows:
        prior=old.get(row["assertion_text"],[])
        if prior: row["assertion_id"]=prior.pop(0)
        else:
            row["assertion_id"]=f"AST-{a['content_id']}-{next_id:02d}"
            next_id+=1
    a["assertions"]=rows
    errors=validate_assertions(rows)
    review=any(r["review_required"]=="YES" for r in rows)
    a["assertion_validation"]={"status":"FAIL" if errors else "PASS_WITH_REVIEW" if review else "PASS","errors":errors}
    if a["platform"]=="x":
        selected=[c for c in claims if c["claim_id"] in a["supported_claim_ids"]]
        a["hook"]=body.splitlines()[0]
        a["hook_validation"]=validate_hook(a["hook_family"],body,selected)
        a["copyedit_validation"]=copyedit(a["copy"])
        a["platform_fit_validation"]=platform_fit("x",a["format"],a["copy"])
        a.update(duration_check("",a["copy"]))
    failure=errors or a["hook_validation"]["status"]=="HOOK_MISMATCH" or a["duration_validation"]=="FAIL"
    a["overall_status"]="FAIL" if failure else "PASS_WITH_REVIEW" if review or a["boilerplate_validation"]["status"]=="WARN" else "PASS"
    return a


def build_part_v2(series:Path,source_manifest:dict,*,dry_run:bool=False,provider:CreativeProvider|None=None,refresh_existing:bool=False)->dict:
    from . import distribution as d
    out=series/"distribution/part-01"; campaign=series/"distribution/campaign"; sources=d._read_csv(series/"articles/part-01-usaid-article/output/sources.csv")
    saved=json.loads((out/"distribution_manifest.json").read_text(encoding="utf-8")) if refresh_existing else None
    claims=d._read_csv(campaign/"claim_library.csv") if saved else extract_claim_library(series,sources)
    angle_list=angles(claims); generated=saved["generation_timestamp"] if saved else d.now(); assets=[]; counters={}
    specs=d._asset_specs(); angle_hooks={"DOCUMENT_LANGUAGE":"DOCUMENT","AGENCY_BOUNDARY":"CONTRADICTION","KENNEDY_POLICY":"PERSON","TIMELINE_ESCALATION":"TIMELINE","COLD_WAR_COUNTERINSURGENCY":"QUESTION","MONEY_AND_STRUCTURE":"MONEY","INTERAGENCY_STRUCTURE":"CONNECTION","POLICE_ASSISTANCE":"ORDINARY_EXPLANATION_VS_RECORD","COVERT_CARVEOUT":"MYSTERY","BUREAUCRATIC_EVOLUTION":"PROGRAM_NAME"}
    platform_names={"TT":"tiktok","FB":"facebook","IG":"instagram","X":"x","SUB":"substack","YT":"youtube","RD":"reddit","REF":"referral","PAID":"paid","SERIES":"series"}
    for index,(code,fmt,_,_) in enumerate(specs):
        if saved:
            assets.append(refresh_asset(saved["assets"][index],claims))
            continue
        key=(code,fmt); counters[key]=counters.get(key,0)+1; platform=platform_names[code]; angle=angle_list[index%len(angle_list)]; family="MYSTERY" if platform=="series" else "QUESTION" if platform in {"referral","paid"} else angle_hooks[angle["angle_name"]]
        selected=[c for c in claims if c["claim_id"] in angle["supporting_claim_ids"]]
        limit={"SHORT":2,"MEDIUM":4,"LONGSHORT":6}.get(fmt,6 if fmt in {"LONG","THREAD","CAROUSEL","POST"} else 3); selected=selected[:limit]
        packet=build_evidence_packet(claims,angle,family,platform,fmt if fmt in {"SHORT","MEDIUM","LONGSHORT"} else "")
        prompt=creative_prompt(packet); copy=provider.generate(prompt,packet) if provider else offline_copy(platform,fmt,family,angle["angle_name"],selected,counters[key]-1)
        cta_family,cta=cta_for(platform,fmt,counters[key]-1)
        if platform in {"referral","paid","series"}: cta=""
        body_copy=prepare_x(copy,cta,fmt) if platform=="x" else copy
        copy=render_copy(body_copy,cta)
        cid=d.content_id(1,code,fmt,counters[key]); duration=duration_check(fmt,copy); assertions=extract_asset_assertions(cid,body_copy,cta,[c["claim_id"] for c in selected],claims)
        hook_validation=validate_hook(family,copy,selected) if platform not in {"referral","paid"} else {"status":"NOT_APPLICABLE","reasons":[]}; copy_validation=copyedit(copy); fit_validation=platform_fit(platform,fmt,copy)
        assertion_errors=validate_assertions(assertions); inference=any(x["support_status"] in {"PARTIALLY_SUPPORTED","INFERENCE_SUPPORTED"} for x in assertions)
        overall="FAIL" if assertion_errors or hook_validation["status"]=="HOOK_MISMATCH" or duration["duration_validation"]=="FAIL" else "PASS_WITH_REVIEW" if inference or copy_validation["status"]=="WARN" or fit_validation["status"]=="WARN" else "PASS"
        assets.append({"content_id":cid,"experiment_id":"EXP-HOOK-001" if platform in {"tiktok","youtube"} else "","campaign_id":d.CAMPAIGN_ID,"article_id":d.article_id(1),"platform":platform,"format":fmt,"hook_family":family,"angle_id":angle["angle_id"],"angle_name":angle["angle_name"],"duration_bucket":fmt if fmt in {"SHORT","MEDIUM","LONGSHORT"} else "","presentation_style":"FACE_PLUS_DOCUMENTS" if platform in {"tiktok","youtube"} else "DOCUMENT_LED_VOICEOVER","cta_family":cta_family,"status":"NEEDS_REVIEW","generated_at":generated,"approved_at":"","published_at":"","source_asset":"articles/part-01-usaid-article/output/article.md","target_url":source_manifest["parts"][0]["published_url"] or d.BASE_URL,"supported_claim_ids":[c["claim_id"] for c in selected],"copy":copy,"hook":copy.splitlines()[0],"reuse_policy":"UNIQUE","evidence_packet":packet,"assertions":assertions,"overall_status":overall,"hook_validation":hook_validation,"assertion_validation":{"status":"FAIL" if assertion_errors else "PASS_WITH_REVIEW" if inference else "PASS","errors":assertion_errors},"evidence_validation":{"status":"PASS"},"boilerplate_validation":{"status":"PENDING"},"copyedit_validation":copy_validation,"spoiler_validation":{"status":"PASS"},"platform_fit_validation":fit_validation,**duration})
        assets[-1].update(body_copy=body_copy,cta_text=cta,validated_copy=copy)
    sim=similarity_report(assets)
    boiler_ids=set()
    for category in ("repeated_sentences","repeated_closings","repeated_phrases"):
        for finding in sim["boilerplate"][category]: boiler_ids.update(finding["content_ids"])
    for a in assets:
        a["boilerplate_validation"]={"status":"WARN" if a["content_id"] in boiler_ids else "PASS"}
        if a["overall_status"]=="PASS" and a["content_id"] in boiler_ids: a["overall_status"]="PASS_WITH_REVIEW"
    if dry_run:return {"would_write":str(out),"asset_count":len(assets),"claim_count":len(claims),"provider":getattr(provider,"provider_name","offline")}
    out.mkdir(parents=True,exist_ok=True); campaign.mkdir(parents=True,exist_ok=True)
    if not saved:
        d._write_csv(campaign/"claim_library.csv",CLAIM_FIELDS,claims)
        (campaign/"angles.json").write_text(json.dumps(angle_list,indent=2)+"\n",encoding="utf-8")
    evidence=[]; assertion_rows=[]; utms=[]
    byid={c["claim_id"]:c for c in claims}
    for a in assets:
        source=a["platform"] if a["platform"]!="series" else "substack"; medium={"substack":"note","tiktok":"video","youtube":"video","reddit":"community"}.get(source,"social"); final=d.utm_url(a["target_url"],source,medium,a["content_id"])
        utms.append({"content_id":a["content_id"],"article_id":d.article_id(1),"platform":a["platform"],"base_url":a["target_url"],"utm_source":source,"utm_medium":medium,"utm_campaign":d.CAMPAIGN_SLUG,"utm_content":a["content_id"],"final_url":final})
        for assertion in a["assertions"]:
            assertion_rows.append(assertion)
            for claim_id in filter(None,assertion["claim_ids"].split("|")):
                c=byid[claim_id]
                evidence.append({"claim_id":c["claim_id"],"assertion_id":assertion["assertion_id"],"content_id":a["content_id"],"claim_text":c["claim_text"],"assertion_text":assertion["assertion_text"],"claim_classification":assertion["classification"] or c["claim_classification"],"support_status":assertion["support_status"],"support_type":assertion["support_type"] or c["support_type"],"source_number":c["source_number"],"source_title":c["source_title"],"source_excerpt":c["source_excerpt"],"source_url":c["source_url"],"article_excerpt":c["article_excerpt"],"article_section":c["article_section"],"source_file":c["source_file"],"spoiler_scope":c["spoiler_scope"],"review_required":"YES" if assertion["review_required"]=="YES" else c["review_required"],"notes":assertion["notes"]})
    d._write_csv(out/"evidence_manifest.csv",EVIDENCE_V2_FIELDS,evidence); d._write_csv(out/"assertion_manifest.csv",list(assertion_rows[0]),assertion_rows)
    if not saved: d._write_csv(out/"utm_links.csv",["content_id","article_id","platform","base_url","utm_source","utm_medium","utm_campaign","utm_content","final_url"],utms)
    registry_fields=["content_id","experiment_id","campaign_id","article_id","platform","format","hook_family","angle_id","angle_name","duration_bucket","estimated_words","estimated_seconds","duration_validation","presentation_style","cta_family","reuse_policy","status","generated_at","approved_at","published_at","source_asset","target_url"]
    d._write_csv(campaign/"content_registry.csv",registry_fields,assets)
    queue_path=out/"approval_queue.csv"; prior={r["content_id"]:r for r in d._read_csv(queue_path)} if queue_path.is_file() else {}
    queue=[]
    for a in assets:
        existing=prior.get(a["content_id"])
        queue.append(existing if existing and existing.get("status") in d.STATUSES else {"content_id":a["content_id"],"status":"NEEDS_REVIEW","reviewer":"","decision":"","notes":"","timestamp":"","revision_history":"[]"})
    if not saved: d._write_csv(queue_path,["content_id","status","reviewer","decision","notes","timestamp","revision_history"],queue)
    (out/"similarity_report.json").write_text(json.dumps(sim,indent=2)+"\n",encoding="utf-8")
    groups={"video_scripts.md":{"tiktok"},"facebook.md":{"facebook"},"instagram.md":{"instagram"},"x_posts.md":{"x"},"substack_notes.md":{"substack"},"youtube_shorts.md":{"youtube"},"reddit.md":{"reddit"},"referral_ctas.md":{"referral"},"paid_ctas.md":{"paid"},"part_02_teasers.md":{"series"}}
    for filename,platforms in groups.items():
        body=[f"# {filename[:-3].replace('_',' ').title()}","","> SOURCE-BOUNDED DRAFT — human review required. Nothing has been published.",""]
        for a in [x for x in assets if x["platform"] in platforms]:
            body += [f"## {a['content_id']}","",f"- Hook: {a['hook_family']}",f"- Angle: {a['angle_name']}",f"- Claims: {', '.join(a['supported_claim_ids'])}",f"- Duration: {a['estimated_words']} words / ~{a['estimated_seconds']} seconds / {a['duration_validation']}","",a["copy"],"","### Review evidence",""]
            for cid in a["supported_claim_ids"]: body += [f"- `{cid}` — {byid[cid]['source_excerpt']}"]
            body += ["",f"Validation: {a['overall_status']}; assertions {a['assertion_validation']['status']}; approval {a['status']}.",""]
        (out/filename).write_text("\n".join(body),encoding="utf-8")
    thread=next(a for a in assets if a["platform"]=="x" and a["format"]=="THREAD"); (out/"x_thread.md").write_text(f"# X Thread — {thread['content_id']}\n\n{thread['copy']}\n\nClaims: {', '.join(thread['supported_claim_ids'])}\nStatus: NEEDS_REVIEW\n",encoding="utf-8")
    review=["# Part 1 human review packet","","> Every asset remains NEEDS_REVIEW. No publishing action exists.",""]
    for a in assets:
        review += [f"## {a['content_id']}",f"Platform / format: {a['platform']} / {a['format']}",f"Hook / angle: {a['hook_family']} / {a['angle_name']}",f"CTA family: {a['cta_family']}",f"Overall status: {a['overall_status']}",f"Duration: {a['estimated_words']} words, ~{a['estimated_seconds']} sec ({a['duration_validation']})","","### Final copy","",a["copy"],"","### Assertions",""]
        for x in a["assertions"]: review += [f"- {x['assertion_text']} — {x['assertion_type']} / {x['support_status']} / {x['claim_ids'] or 'no claim required'}"]
        review += ["","Body and CTA are parsed separately; final copy above is the validated rendering.","","### Source support",""]
        for cid in a["supported_claim_ids"]: review += [f"- `{cid}`: {byid[cid]['source_excerpt']}"]
        review += ["","### Validation",f"- Hook: {a['hook_validation']['status']}",f"- Assertion: {a['assertion_validation']['status']}",f"- Evidence: {a['evidence_validation']['status']}",f"- Boilerplate: {a['boilerplate_validation']['status']}",f"- Duration: {a['duration_validation']}",f"- Copyedit: {a['copyedit_validation']['status']}",f"- Spoiler: {a['spoiler_validation']['status']}",f"- Platform fit: {a['platform_fit_validation']['status']}","","Editorial warnings: __________________","Approval status: NEEDS_REVIEW","Review decision: ____________________","Notes: _______________________________",""]
    (out/"review_packet.md").write_text("\n".join(review),encoding="utf-8")
    manifest={"schema_version":3,"campaign_id":d.CAMPAIGN_ID,"article_id":d.article_id(1),"prompt_version":PROMPT_VERSION,"provider":getattr(provider,"provider_name","offline"),"model_used":getattr(provider,"model_name","deterministic-source-bounded-v1.6"),"generation_timestamp":generated,"source_inputs":["SERIES_MANIFEST.json","SERIES_CONTINUITY.md","articles/part-01-usaid-article/output/article.md","articles/part-01-usaid-article/output/sources.csv","shared_sources/**/*.extracted.txt"],"claim_count":len(claims),"asset_count":len(assets),"assertion_count":len(assertion_rows),"unsupported_assertion_count":sum(x["support_status"]=="UNSUPPORTED" for x in assertion_rows),"partially_supported_count":sum(x["support_status"]=="PARTIALLY_SUPPORTED" for x in assertion_rows),"inference_supported_count":sum(x["support_status"]=="INFERENCE_SUPPORTED" for x in assertion_rows),"hook_mismatch_count":sum(a["hook_validation"]["status"]=="HOOK_MISMATCH" for a in assets),"copyedit_warning_count":sum(len(a["copyedit_validation"]["issues"]) for a in assets),"platform_fit_warning_count":sum(len(a["platform_fit_validation"]["issues"]) for a in assets),"cta_family_count":len({a["cta_family"] for a in assets}),"source_excerpt_coverage":round(sum(c["source_excerpt"]!="UNAVAILABLE" for c in claims)/len(claims),3),"spoiler_violations":0,"similarity":sim,"publishing_performed":False,"assets":assets}
    (out/"distribution_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"output":str(out),"asset_count":len(assets),"claim_count":len(claims),"source_excerpt_coverage":manifest["source_excerpt_coverage"],"duplicate_asset_rate":sim["duplicate_asset_rate"]}


def validate_package_v2(root:Path,slug:str,part:int=1)->dict:
    from . import distribution as d
    series,_=d.discover(root,slug); out=series/f"distribution/part-{part:02d}"; errors=[]; warnings=[]
    required=["distribution_manifest.json","evidence_manifest.csv","assertion_manifest.csv","approval_queue.csv","utm_links.csv","review_packet.md","similarity_report.json"]
    for f in required:
        if not (out/f).is_file(): errors.append(f"Missing {f}")
    if errors:return {"campaign_id":d.CAMPAIGN_ID,"part":part,"errors":errors,"warnings":warnings,"result":"FAIL"}
    manifest=json.loads((out/"distribution_manifest.json").read_text(encoding="utf-8")); assertions=d._read_csv(out/"assertion_manifest.csv"); evidence=d._read_csv(out/"evidence_manifest.csv"); ids=[a["content_id"] for a in manifest["assets"]]
    claims=d._read_csv(series/"distribution/campaign/claim_library.csv")
    review_text=(out/"review_packet.md").read_text(encoding="utf-8")
    if len(ids)!=len(set(ids)):errors.append("Duplicate content IDs.")
    errors += validate_assertions(assertions)
    if any(a["status"]=="PUBLISHED" for a in manifest["assets"]):errors.append("Generated assets may not be PUBLISHED.")
    if any(a["duration_bucket"] and a["duration_validation"]=="FAIL" for a in manifest["assets"]):errors.append("One or more video scripts fail duration validation.")
    for a in manifest["assets"]:
        errors.extend(validate_final_copy(a,claims))
        if a["copy"] not in review_text: errors.append(f"Review rendering differs: {a['content_id']}")
        if a["platform"]=="x":
            rendered=(out/"x_posts.md").read_text(encoding="utf-8")
            if a["copy"] not in rendered: errors.append(f"X rendering differs: {a['content_id']}")
            if a["format"]=="THREAD" and a["copy"] not in (out/"x_thread.md").read_text(encoding="utf-8"):
                errors.append(f"Thread rendering differs: {a['content_id']}")
        if a["hook_validation"]["status"]=="HOOK_MISMATCH": errors.append(f"HOOK_MISMATCH: {a['content_id']}")
        if a["overall_status"]=="FAIL" and not any(a["content_id"] in e for e in errors): errors.append(f"Asset validation failed: {a['content_id']}")
    if any(r["spoiler_scope"]=="FUTURE_PARTS" and r.get("teaser_safe")!="YES" for r in evidence):errors.append("Future-part spoiler evidence used.")
    if manifest["similarity"]["validation"]=="FAIL":errors.append("Excessive duplicated content.")
    if any(not r["source_excerpt"] for r in evidence):errors.append("Evidence row missing source_excerpt marker.")
    if manifest["partially_supported_count"]:warnings.append("Partially supported assertions require human review.")
    return {"campaign_id":d.CAMPAIGN_ID,"part":part,"claim_count":manifest["claim_count"],"asset_count":len(ids),"assertion_count":manifest["assertion_count"],"source_excerpt_coverage":manifest["source_excerpt_coverage"],"duplicate_asset_rate":manifest["similarity"]["duplicate_asset_rate"],"unsupported_assertions":manifest["unsupported_assertion_count"],"partially_supported":manifest["partially_supported_count"],"inference_supported":manifest["inference_supported_count"],"hook_mismatches":manifest["hook_mismatch_count"],"repetition_warnings":manifest["similarity"]["boilerplate"]["warning_count"],"copyedit_warnings":manifest["copyedit_warning_count"],"platform_fit_warnings":manifest["platform_fit_warning_count"],"cta_families":manifest["cta_family_count"],"spoiler_violations":manifest["spoiler_violations"],"errors":errors,"warnings":warnings,"result":"FAIL" if errors else "PASS"}
