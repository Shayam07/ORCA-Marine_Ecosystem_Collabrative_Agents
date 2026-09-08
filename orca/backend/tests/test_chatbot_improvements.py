"""Tests for ORCA Chatbot Conversational Behavior, Location Context, and Response Formatting Upgrades."""

import pytest
from fastapi.testclient import TestClient
from main import app
from llm.service import get_llm_service


@pytest.fixture
def client():
    return TestClient(app)


def test_chatbot_clean_llm_output_strips_internal_instructions_and_asterisks():
    """Verify _clean_llm_output removes internal instructions, thinking tags, and raw asterisks."""
    service = get_llm_service()
    
    raw_output = (
        "<think>\nAnalyze user question: Where to fish?\nDraft the response.\n</think>\n"
        "Draft the response:\n"
        "Based on the instructions, **Chennai** has **favorable** conditions.\n\n"
        "• **Conditions:** SST is `28.5°C` and chlorophyll is `1.2 mg/m³`.\n"
        "• **Safety:** Waves are `1.4 m`.\n\n"
        "This is a potential recommendation and does not guarantee catch."
    )
    
    cleaned = service._clean_llm_output(raw_output)
    
    # Verify no thinking tags
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    
    # Verify no internal instructions
    assert "draft the response" not in cleaned.lower()
    assert "based on the instructions" not in cleaned.lower()
    
    # Verify no raw ** asterisks
    assert "**" not in cleaned
    
    # Verify code backticks removed
    assert "`28.5°C`" not in cleaned
    assert "28.5°C" in cleaned
    
    # Verify content preserved
    assert "Chennai has favorable conditions" in cleaned
    assert "Conditions: SST is 28.5°C" in cleaned


def test_clean_llm_output_strips_numbered_reasoning_transcript_keeping_last_draft():
    """Qwen3-style visible 'thinking' transcripts keep only the user-facing draft."""
    service = get_llm_service()
    raw = (
        '- User asks: "Where can I fish near Chennai?"\n'
        '   - Location: Chennai (13.08, 80.27)\n'
        '   - Intent: FISHING_LOCATION_RECOMMENDATION\n\n'
        '2.  Check Context & Constraints:\n'
        '   - Marine context provided: SST 28.2°C, wind 11.5 m/s.\n\n'
        '3.  Draft Construction (Mental Refinement):\n'
        '   Based on current marine conditions near Chennai, head to the area 14 km offshore.\n\n'
        '   • Key Conditions: SST is 28.2°C with productive thermal fronts.\n'
        '   • Safety: Waves are 1.5 m.\n\n'
        '4.  Check Against Rules:\n'
        '   - Direct answer first? Yes.\n'
        '   - All good.\n\n'
        '   Proceed.\n'
    )
    cleaned = service._clean_llm_output(raw)
    assert cleaned.startswith('Based on current marine conditions')
    assert '14 km offshore' in cleaned
    assert 'Check Against Rules' not in cleaned
    assert 'User asks' not in cleaned
    assert 'Direct answer first' not in cleaned
    assert 'Proceed' not in cleaned


def test_clean_llm_output_keeps_final_draft_marker_copy_not_earlier_one():
    """When the transcript repeats the draft after a standalone 'Draft:', keep the last copy."""
    service = get_llm_service()
    raw = (
        '2.  Check Context & Constraints:\n'
        '   - PFZs detected: 3 zones.\n\n'
        '3.  Draft Construction (Mental Refinement):\n'
        '   First draft paragraph that should NOT survive.\n\n'
        '4.  Check Against Rules:\n'
        '   - Direct answer? Yes.\n\n'
        '   Draft:\n'
        '   Based on current marine conditions near Chennai, I have identified three PFZ zones offshore.\n\n'
        '   • PFZ-SECTOR-01: 14 km offshore. High suitability.\n\n'
        '   All constraints met. I will generate the response now.\n'
        '   Output matches the refined draft.✅\n'
    )
    cleaned = service._clean_llm_output(raw)
    assert cleaned.startswith('Based on current marine conditions near Chennai, I have identified three PFZ zones')
    assert 'PFZ-SECTOR-01' in cleaned
    assert 'First draft paragraph' not in cleaned
    assert 'All constraints met' not in cleaned
    assert 'I will generate' not in cleaned


def test_clean_llm_output_strips_self_correction_meta_line_and_quote_wraps():
    """A leading *(Self-Correction/Refinement...)* meta line and quote wrapping are removed."""
    service = get_llm_service()
    raw = (
        '*(Self-Correction/Refinement during drafting)*: I will make sure the structure exactly '
        'matches the preferred format without extra fluff.\n'
        '   "Based on current marine conditions near Chennai, I have identified three active '
        'Potential Fishing Zones (PFZ) offshore."\n'
    )
    cleaned = service._clean_llm_output(raw)
    assert cleaned.startswith('Based on current marine conditions near Chennai, I have identified three active')
    assert 'Self-Correction' not in cleaned
    assert 'Refinement' not in cleaned
    assert not cleaned.startswith('"')


def test_clean_llm_output_leaves_clean_answer_untouched():
    """A normal, already-clean ORCA answer must pass through without being mangled."""
    service = get_llm_service()
    raw = (
        'Based on your location near Chennai, I have identified two high-potential fishing zones '
        'that are currently safe and have low fleet crowding.\n\n'
        '• PFZ-SECTOR-01: Located 14 km offshore. Conditions: SST 28.2°C.\n'
        '• Safety: Wind 11.5 m/s, waves 1.5 m.\n\n'
        'This is a potential recommendation and does not guarantee catch.'
    )
    cleaned = service._clean_llm_output(raw)
    assert cleaned.startswith('Based on your location near Chennai')
    assert 'PFZ-SECTOR-01' in cleaned
    assert 'does not guarantee catch' in cleaned


def test_chatbot_where_can_i_fish_today(client):
    """Verify 'Where can I fish today?' gives a direct, concise answer with no ** and probabilistic disclaimer."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish today?",
        "conversation_id": "test_fish_today_conv",
        "location": {"name": "Chennai", "lat": 13.08, "lon": 80.28, "environment": "COASTAL"},
    })
    assert resp.status_code == 200
    data = resp.json()
    content = data["content"]
    
    # No raw markdown ** artifacts
    assert "**" not in content
    
    # No internal instructions
    assert "draft the response" not in content.lower()
    assert "generate response" not in content.lower()
    
    # Must answer with conditions, safety, pressure, and probabilistic disclaimer
    assert "potential" in content.lower()
    assert "does not guarantee" in content.lower()
    assert "conditions:" in content.lower()
    assert "safety:" in content.lower()
    assert "fishing pressure:" in content.lower()


def test_chatbot_is_it_safe_tomorrow(client):
    """Verify 'Is it safe to go fishing tomorrow?' gives direct forecast advice without unnecessary questions."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Is it safe to go fishing tomorrow?",
        "conversation_id": "test_safe_tomorrow_conv",
        "location": {"name": "Chennai", "lat": 13.08, "lon": 80.28, "environment": "COASTAL"},
    })
    assert resp.status_code == 200
    data = resp.json()
    content = data["content"]
    
    assert "**" not in content
    assert "draft" not in content.lower()
    assert "safe" in content.lower()
    assert "wind" in content.lower()
    assert ("wave" in content.lower() or "sea" in content.lower())


def test_chatbot_nearest_pfz_query(client):
    """Verify 'Give me the nearest PFZ.' answers concisely with suitability, crowding, and safety."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Give me the nearest PFZ.",
        "conversation_id": "test_nearest_pfz_conv",
        "location": {"name": "Kochi", "lat": 9.93, "lon": 76.26, "environment": "COASTAL"},
    })
    assert resp.status_code == 200
    data = resp.json()
    content = data["content"]
    
    assert "**" not in content
    assert ("nearest" in content.lower() or "pfz" in content.lower())
    assert ("suitability" in content.lower() or "conditions" in content.lower() or "sst" in content.lower())
    assert ("crowding" in content.lower() or "pressure" in content.lower() or "traffic" in content.lower() or "fleet" in content.lower())


def test_chatbot_can_i_cross_this_border(client):
    """Verify 'Can I cross this border?' returns a clear 'No' and explains boundary policy."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Can I cross this border?",
        "conversation_id": "test_border_conv",
        "location": {"name": "Rameswaram", "lat": 9.28, "lon": 79.31, "environment": "COASTAL"},
    })
    assert resp.status_code == 200
    data = resp.json()
    content = data["content"]
    
    assert "**" not in content
    assert content.strip().startswith("No.")
    assert "restricted" in content.lower() or "international maritime" in content.lower()
    assert "safe" in content.lower()


def test_inland_user_with_selected_landing_centre_uses_landing_centre(client):
    """If user location is inland, but has selected a coastal landing center, ORCA uses that landing center."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish today?",
        "conversation_id": "test_inland_landing_conv",
        "location": {"name": "Bengaluru", "lat": 12.97, "lon": 77.59, "environment": "INLAND"},
        "landing_centre": {"name": "Mangalore Fishing Harbour", "lat": 12.87, "lon": 74.84, "state": "Karnataka"},
    })
    assert resp.status_code == 200
    data = resp.json()
    
    # Must NOT reject as inland because a coastal landing centre is selected
    assert data["response_type"] != "inland_notice"
    assert data["location"]["name"] == "Mangalore Fishing Harbour"
    assert data["location"]["environment"] == "COASTAL"
    assert "**" not in data["content"]


def test_context_retention_does_not_repeatedly_ask_for_location(client):
    """When a location is established, follow-up queries must inherit it without asking 'Which coastal area...'."""
    conv_id = "test_no_repeat_ask_conv"
    
    # Turn 1: Set location to Chennai
    r1 = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish near Chennai?",
        "conversation_id": conv_id,
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert "chennai" in d1["location"]["name"].lower()
    
    # Turn 2: Follow-up asking for nearest PFZ without repeating "Chennai"
    r2 = client.post("/api/v1/chat/message", json={
        "message": "Give me the nearest PFZ.",
        "conversation_id": conv_id,
    })
    assert r2.status_code == 200
    d2 = r2.json()
    # Must NOT ask for location again
    assert d2["response_type"] != "followup_location"
    assert "which location would you like" not in d2["content"].lower()
    assert "which coastal area" not in d2["content"].lower()
    assert ("nearest" in d2["content"].lower() or "pfz" in d2["content"].lower() or "zone" in d2["content"].lower())
    assert "**" not in d2["content"]
