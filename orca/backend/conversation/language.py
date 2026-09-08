"""ORCA Multi-Language Support.

Detects the user's language and provides translation facilities.
Supports: English, Tamil, Hindi, Telugu, Malayalam, Kannada, Bengali, Marathi, Gujarati.

Uses keyword-based and script-range detection for reliability without external API dependencies.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("orca.language")

# Language detection patterns
LANGUAGE_PATTERNS = {
    "ta": {
        "name": "Tamil",
        "script_range": (0x0B80, 0x0BFF),  # Tamil Unicode block
        "keywords": [
            "எங்கு", "மீன்", "பிடி", "கடல்", "பாதுகாப்பு", "காற்று",
            "நாளை", "இன்று", "நேற்று", "காலை", "மாலை", "இரவு",
            "வெப்பநிலை", "மழை", "சூறாவளி", "அலை", "மீன்பிடி",
            "பகுதி", "பரிந்துரை", "சிறந்த", "எப்போது",
            "ஏன்", "எப்படி", "கடலுக்கு", "போக", "வேண்டுமா",
        ],
    },
    "hi": {
        "name": "Hindi",
        "script_range": (0x0900, 0x097F),  # Devanagari Unicode block
        "keywords": [
            "मछली", "कहाँ", "कहां", "सुरक्षित", "क्या", "है",
            "कल", "आज", "सुबह", "शाम", "रात",
            "तापमान", "हवा", "बारिश", "तूफान", "चक्रवात", "लहर",
            "मौसम", "समुद्र", "जल", "तट", "बंदरगाह",
            "सबसे अच्छा", "बेहतर", "कृपया", "दिखाओ", "बताओ",
        ],
    },
    "te": {
        "name": "Telugu",
        "script_range": (0x0C00, 0x0C7F),  # Telugu Unicode block
        "keywords": [
            "చేప", "ఎక్కడ", "సురక్షిత", "ఏమి", "ఉంది",
            "రేపు", "ఈరోజు", "నిన్న", "ఉదయం", "సాయంత్రం",
            "ఉష్ణోగ్రత", "గాలి", "వర్షం", "తుఫాను", "అలలు",
            "సముద్రం", "తీరం", "మత్స్య", "ప్రాంతం",
        ],
    },
    "ml": {
        "name": "Malayalam",
        "script_range": (0x0D00, 0x0D7F),  # Malayalam Unicode block
        "keywords": [
            "മത്സ്യം", "എവിടെ", "സുരക്ഷിതം", "എന്ത്", "ഉണ്ട്",
            "നാളെ", "ഇന്ന്", "ഇന്നലെ", "രാവിലെ", "വൈകുന്നേരം",
            "താപനില", "കാറ്റ്", "മഴ", "കൊടുങ്കാറ്റ്", "തിര",
            "കടൽ", "തീരം", "മീൻപിടിത്തം",
        ],
    },
    "kn": {
        "name": "Kannada",
        "script_range": (0x0C80, 0x0CFF),  # Kannada Unicode block
        "keywords": [
            "ಮೀನು", "ಎಲ್ಲಿ", "ಸುರಕ್ಷಿತ", "ಏನು", "ಇದೆ",
            "ನಾಳೆ", "ಇಂದು", "ನಿನ್ನೆ", "ಬೆಳಿಗೆ", "ಸಂಜೆ",
            "ಉಷ್ಣತೆ", "ಗಾಳಿ", "ಮಳೆ", "ಬಿರುಗಾಳಿ", "ಅಲೆ",
            "ಸಮುದ್ರ", "ದಡ", "ಮೀನುಗಾರಿಕೆ",
        ],
    },
    "bn": {
        "name": "Bengali",
        "script_range": (0x0980, 0x09FF),  # Bengali Unicode block
        "keywords": [
            "মাছ", "কোথায়", "নিরাপদ", "কী", "আছে",
            "আগামীকাল", "আজ", "গতকাল", "সকাল", "সন্ধ্যা",
            "তাপমাত্রা", "বাতাস", "বৃষ্টি", "ঝড়", "তরঙ্গ",
            "সমুদ্র", "উপকূল", "মৎস্য",
        ],
    },
    "gu": {
        "name": "Gujarati",
        "script_range": (0x0A80, 0x0AFF),  # Gujarati Unicode block
        "keywords": [
            "માછલી", "ક્યાં", "દરિયો", "સુરક્ષિત", "હવામાન", "વાવાઝોડું",
            "આજે", "કાલે", "સવાર", "સાંજ", "તાપમાન", "પવન", "મોજું",
            "દરિયાકિનારો", "મત્સ્ય", "વિસ્તાર", "રસ્તો",
        ],
    },
    "mr": {
        "name": "Marathi",
        "script_range": (0x0900, 0x097F),  # Devanagari (shared with Hindi)
        "keywords": [
            "मासे", "कुठे", "सुरक्षित", "काय", "आहे",
            "उद्या", "आज", "काल", "सकाळ", "संध्याकाळ",
            "तापमान", "वारा", "पाऊस", "वादळ", "लाट",
            "समुद्र", "किनारा", "मत्स्य",
        ],
    },
}


def detect_language(text: str) -> str:
    """Detect the language of a text string.

    Returns ISO 639-1 language code (e.g. 'en', 'ta', 'hi', 'te', 'ml', 'gu', 'bn', 'mr', 'kn').
    """
    if not text or not text.strip():
        return "en"

    # Check for non-Latin scripts first (most reliable)
    for lang_code, info in LANGUAGE_PATTERNS.items():
        script_start, script_end = info["script_range"]
        for char in text:
            if script_start <= ord(char) <= script_end:
                return lang_code

    # Check for keyword matches (for Latin-script transliterations)
    text_lower = text.lower()
    lang_scores = {}

    for lang_code, info in LANGUAGE_PATTERNS.items():
        score = 0
        for keyword in info["keywords"]:
            if keyword.lower() in text_lower:
                score += len(keyword)  # Longer matches score higher
        if score > 0:
            lang_scores[lang_code] = score

    if lang_scores:
        return max(lang_scores, key=lang_scores.get)

    return "en"


def get_language_name(code: str) -> str:
    """Get the full name of a language from its ISO code."""
    names = {
        "en": "English",
        "ta": "Tamil (தமிழ்)",
        "hi": "Hindi (हिन्दी)",
        "te": "Telugu (తెలుగు)",
        "ml": "Malayalam (മലയാളം)",
        "kn": "Kannada (ಕನ್ನಡ)",
        "bn": "Bengali (বাংলা)",
        "mr": "Marathi (मराठी)",
        "gu": "Gujarati (ગુજરાતી)",
    }
    return names.get(code, "English")


# Common ORCA response templates in different languages
RESPONSE_TEMPLATES = {
    "en": {
        "ask_location": "I can help with that. Where would you like me to check? You can share a city name, coastal town, or select a location on the map.",
        "ask_time": "Got it. What time period are you interested in? For example: today, tomorrow, this week, or a specific date.",
        "processing": "Let me check the latest marine data for your area.",
        "no_data": "I couldn't find sufficient data for that location and time. Let me try with nearby data sources.",
        "safety_caution": "Based on current conditions, exercise caution at sea.",
        "safety_danger": "⚠️ Hazardous sea conditions detected. Postponing sea activity is strongly recommended.",
        "safety_safe": "Current sea conditions are favorable for marine operations.",
        "pfz_found": "Found Potential Fishing Zones (PFZ) near {loc}.",
        "geofence_warning": "⚠️ Boundary Advisory: Approaching maritime boundary or protected area.",
    },
    "ta": {
        "ask_location": "நான் உதவ முடியும். எங்கு சரிபார்க்க விரும்புகிறீர்கள்? நகரம், கடலோர நகரம் அல்லது வரைபடத்தில் இடத்தைத் தேர்ந்தெடுக்கலாம்.",
        "ask_time": "புரிந்தது. எந்த நேரத்தை ஆராய விரும்புகிறீர்கள்? இன்று, நாளை, இந்த வாரம் போன்றவை.",
        "processing": "உங்கள் பகுதிக்கான சமீபத்திய கடல் தரவை சரிபார்க்கிறேன்.",
        "safety_caution": "தற்போதைய நிலைமைகளின் அடிப்படையில், கடலில் எச்சரிக்கையாக இருங்கள்.",
        "safety_danger": "⚠️ அபாயகரமான கடல் நிலைமைகள். கடலுக்குச் செல்வதைத் தவிர்க்கவும்.",
        "safety_safe": "தற்போதைய கடல் நிலைமைகள் மீன்பிடிக்க சாதகமாக உள்ளன.",
        "pfz_found": "{loc} அருகில் சாத்தியமான மீன்பிடி மண்டலங்கள் (PFZ) கண்டறியப்பட்டன.",
        "geofence_warning": "⚠️ எல்லை எச்சரிக்கை: சர்வதேச கடல் எல்லை அல்லது பாதுகாக்கப்பட்ட பகுதியை அணுகுகிறீர்கள்.",
    },
    "hi": {
        "ask_location": "मैं मदद कर सकता हूँ। आप कहाँ जांच करवाना चाहेंगे? शहर, तटीय नगर, या मानचित्र पर स्थान चुनें।",
        "ask_time": "समझ गया। आप किस समय की जानकारी चाहेंगे? आज, कल, इस सप्ताह, या कोई विशेष तिथि।",
        "processing": "आपके क्षेत्र के लिए नवीनतम समुद्री डेटा जांच रहा हूँ।",
        "safety_caution": "वर्तमान स्थितियों के आधार पर, समुद्र में सावधानी बरतें।",
        "safety_danger": "⚠️ खतरनाक समुद्री स्थितियां! समुद्र में जाने से बचें।",
        "safety_safe": "वर्तमान समुद्री स्थितियां अनुकूल हैं।",
        "pfz_found": "{loc} के पास संभावित मत्स्य पालन क्षेत्र (PFZ) पाए गए।",
        "geofence_warning": "⚠️ सीमा चेतावनी: अंतर्राष्ट्रीय समुद्री सीमा या संरक्षित क्षेत्र के समीप।",
    },
    "te": {
        "ask_location": "నేను సహాయం చేయగలను. మీరు ఎక్కడ తనిఖీ చేయాలనుకుంటున్నారు? నగరం, తీర నగరం, లేదా మ్యాప్‌లో స్థానాన్ని ఎంచుకోండి.",
        "ask_time": "అర్థమైంది. మీరు ఏ కాలం గురించి ఆసక్తి కలిగి ఉన్నారు? ఈరోజు, రేపు, ఈ వారం.",
        "processing": "మీ ప్రాంతం కోసం తాజా సముద్ర డేటాను తనిఖీ చేస్తోంది.",
        "safety_caution": "ప్రస్తుత పరిస్థితుల ఆధారంగా, సముద్రంలో జాగ్రత్త వహించండి.",
        "safety_danger": "⚠️ ప్రమాదకరమైన సముద్ర పరిస్థితులు! సముద్రంలోకి వెళ్లడం వాయిదా వేయండి.",
        "safety_safe": "ప్రస్తుత సముద్ర పరిస్థితులు అనుకూలంగా ఉన్నాయి.",
        "pfz_found": "{loc} సమీపంలో పొటెన్షియల్ ఫిషింగ్ జోన్లు (PFZ) కనుగొనబడ్డాయి.",
        "geofence_warning": "⚠️ సరిహద్దు హెచ్చరిక: అంతర్జాతీయ సముద్ర సరిహద్దు లేదా రక్షిత ప్రాంతం సమీపిస్తోంది.",
    },
    "ml": {
        "ask_location": "ഞാൻ സഹായിക്കാം. എവിടെ പരിശോധിക്കണം? നഗരം, തീരദേശ നഗരം, അല്ലെങ്കിൽ മാപ്പിൽ സ്ഥലം തിരഞ്ഞെടുക്കുക.",
        "ask_time": "മനസ്സിലായി. ഏത് സമയം? ഇന്ന്, നാളെ, ഈ ആഴ്ച.",
        "processing": "നിങ്ങളുടെ പ്രദേശത്തെ ഏറ്റവും പുതിയ സമുദ്ര ഡാറ്റ പരിശോധിക്കുന്നു.",
        "safety_caution": "നിലവിലെ സാഹചര്യങ്ങൾ കണക്കിലെടുത്ത് കടലിൽ ജാഗ്രത പാലിക്കുക.",
        "safety_danger": "⚠️ അപകടകരമായ കടൽ സാഹചര്യങ്ങൾ! കടലിൽ പോകുന്നത് ഒഴിവാക്കുക.",
        "safety_safe": "നിലവിലെ കടൽ സാഹചര്യങ്ങൾ അനുകൂലമാണ്.",
        "pfz_found": "{loc} ന് സമീപം സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖലകൾ (PFZ) കണ്ടെത്തി.",
        "geofence_warning": "⚠️ അതിർത്തി മുന്നറിയിപ്പ്: അന്താരാഷ്ട്ര സമുദ്ര അതിർത്തിയോ സംരക്ഷിത മേഖലയോ സമീപിക്കുന്നു.",
    },
    "kn": {
        "ask_location": "ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಎಲ್ಲಿ ಪರಿಶೀಲಿಸಬೇಕು? ನಗರ, ಕರಾವಳಿ ನಗರ, ಅಥವಾ ನಕ್ಷೆಯಲ್ಲಿ ಸ್ಥಳ ಆಯ್ಕೆಮಾಡಿ.",
        "ask_time": "ಅರ್ಥವಾಯಿತು. ಯಾವ ಸಮಯ? ಇಂದು, ನಾಳೆ, ಈ ವಾರ.",
        "processing": "ನಿಮ್ಮ ಪ್ರದೇಶಕ್ಕೆ ಇತ್ತೀಚಿನ ಸಮುದ್ರ ಡೇಟಾವನ್ನು ಪರಿಶೀಲಿಸುತ್ತಿದೆ.",
        "safety_caution": "ಪ್ರಸ್ತುತ ಪರಿಸ್ಥಿತಿಗಳ ಆಧಾರದ ಮೇಲೆ, ಸಮುದ್ರದಲ್ಲಿ ಜಾಗರೂಕರಾಗಿರಿ.",
        "safety_danger": "⚠️ ಅಪಾಯಕಾರಿ ಸಮುದ್ರ ಪರಿಸ್ಥಿತಿಗಳು! ಸಮುದ್ರಕ್ಕೆ ಹೋಗುವುದನ್ನು ತಡೆಯಿರಿ.",
        "safety_safe": "ಪ್ರಸ್ತುತ ಸಮುದ್ರ ಪರಿಸ್ಥಿತಿಗಳು ಅನುಕೂಲಕರವಾಗಿವೆ.",
        "pfz_found": "{loc} ಹತ್ತಿರ ಸಂಭಾವ್ಯ ಮೀನುಗಾರಿಕೆ ವಲಯಗಳು (PFZ) ಪತ್ತೆಯಾಗಿವೆ.",
        "geofence_warning": "⚠️ ಗಡಿ ಎಚ್ಚರಿಕೆ: ಆಂತರಿಕ ಅಥವಾ ಸಂರಕ್ಷಿತ ಸಮುದ್ರ ಗಡಿಯನ್ನು ತಲುಪುತ್ತಿದ್ದೀರಿ.",
    },
    "bn": {
        "ask_location": "আমি সাহায্য করতে পারি। কোথায় যাচাই করতে চান? শহর, উপকূলীয় নগর, অথবা মানচিত্রে অবস্থান নির্বাচন করুন।",
        "ask_time": "বুঝেছি। কোন সময়? আজ, আগামীকাল, এই সপ্তাহ।",
        "processing": "আপনার এলাকার জন্য সর্বশেষ সামুদ্রিক তথ্য যাচাই করছি।",
        "safety_caution": "বর্তমান পরিস্থিতির ওপর ভিত্তি করে সমুদ্রে সতর্ক থাকুন।",
        "safety_danger": "⚠️ বিপজ্জনক সামুদ্রিক অবস্থা! সমুদ্রে যাওয়া এড়িয়ে চলুন।",
        "safety_safe": "বর্তমান সামুদ্রিক অবস্থা অনুকূল।",
        "pfz_found": "{loc}-এর কাছে সম্ভাব্য মৎস্য এলাকা (PFZ) পাওয়া গেছে।",
        "geofence_warning": "⚠️ সীমানা সতর্কবার্তা: আন্তর্জাতিক সামুদ্রিক সীমানা বা সংরক্ষিত এলাকা নিকটবর্তী।",
    },
    "mr": {
        "ask_location": "मी मदत करू शकतो. कुठे तपासायचे? शहर, किनारपट्टी शहर, किंवा नकाशावर स्थान निवडा.",
        "ask_time": "समजले. कोणता वेळ? आज, उद्या, या आठवड्यात.",
        "processing": "तुमच्या भागासाठी नवीनतम समुद्री माहिती तपासत आहे.",
        "safety_caution": "सध्याच्या परिस्थितीनुसार समुद्रात काळजी घ्या.",
        "safety_danger": "⚠️ धोकादायक सागरी परिस्थिती! समुद्रात जाणे टाळा.",
        "safety_safe": "सध्याची सागरी परिस्थिती अनुकूल आहे.",
        "pfz_found": "{loc} जवळ संभाव्य मासेमारी क्षेत्रे (PFZ) आढळली.",
        "geofence_warning": "⚠️ सीमा सूचना: आंतरराष्ट्रीय सागरी सीमा किंवा संरक्षित क्षेत्राजवळ आहात.",
    },
    "gu": {
        "ask_location": "હું મદદ કરી શકું છું. તમે ક્યાં તપાસ કરવા માંગો છો? શહેર, દરિયાકાંઠાનું નગર, અથવા નકશા પર સ્થળ પસંદ કરો.",
        "ask_time": "સમજાઈ ગયું. કયો સમયગાળો? આજે, કાલે, આ અઠવાડિયે.",
        "processing": "તમારા વિસ્તાર માટે તાજેતરના દરિયાઈ ડેટા તપાસી રહ્યો છું.",
        "safety_caution": "વર્તમાન પરિસ્થિતિઓના આધારે દરિયામાં સાવચેતી રાખો.",
        "safety_danger": "⚠️ જોખમી દરિયાઈ સ્થિતિ! દરિયામાં જવાનું ટાળો.",
        "safety_safe": "વર્તમાન દરિયાઈ સ્થિતિ અનુકૂળ છે.",
        "pfz_found": "{loc} નજીક સંભવિત મત્સ્યપાલન વિસ્તારો (PFZ) મળ્યા.",
        "geofence_warning": "⚠️ સીમા ચેતવણી: આંતરરાષ્ટ્રીય દરિયાઈ સીમા અથવા સંરક્ષિત વિસ્તાર નજીક છો.",
    },
}


def get_response_text(key: str, language: str = "en", **kwargs) -> str:
    """Get a localized response text.

    Falls back to English if the language is not supported.
    """
    templates = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
    text = templates.get(key, RESPONSE_TEMPLATES["en"].get(key, key))

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return text
