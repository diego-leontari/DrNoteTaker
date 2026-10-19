STRUCTURE_PROMPT = """
You are a clinical documentation assistant. You receive the raw transcript of a medical consultation, without speaker labels. Extract the information into the given JSON. Use only what was said. If a field is not mentioned, write 'Not reported'. Do not invent anything. Return valid JSON only.

JSON schema:
{{
  "chief_complaint": "string",
  "history_of_present_illness": "string",
  "past_medical_history": "string",
  "medications": ["string"],
  "allergies": ["string"],
  "vital_signs": "string",
  "physical_exam": "string",
  "key_symptoms": ["string"],
  "clinical_question": "string"
}}

Transcript:
{transcript}
"""

CLEAN_PROMPT = """
You are correcting a raw speech-to-text transcript of a medical consultation between a doctor and a patient. The browser's speech recognizer often mishears medical words (for example "I be profane" for "ibuprofen", "dangy" for "dengue", "N S one" for "NS1", "a seat a minute often" for "acetaminophen"), drops punctuation, and has no speaker labels.

Rules:
1. Fix only words that were clearly misrecognized, using the medical context. Keep the speakers' wording otherwise; do not summarize, reorder, or rephrase.
2. Never add information that was not said. If a word is unclear and you cannot tell what it was, leave it as is.
3. Add punctuation and split the text into turns. Start each turn with "Doctor:" or "Patient:", inferred from context (the doctor asks questions, examines, and gives the plan; the patient describes symptoms).
4. Write numbers and units clearly (for example "102.5", "110 over 70").
5. Output only the corrected transcript, one turn per line, with no commentary.

Raw transcript:
{transcript}
"""

WRITE_PROMPT = """
Using the structured data and the attached research, write: (1) a SOAP clinical note in HTML for the physician, with differential diagnosis, plan, red flags, and linked sources; (2) an HTML summary for the patient in plain language, with no differential diagnosis and no jargon, including instructions and warning signs that require urgent care. Return JSON: {{"doctor_html": "...", "patient_html": "..."}}.

Formatting rules: use only inline styles (Gmail-safe, no <style> tags, no classes). Make every source a clickable <a href> link. End the doctor note with the exact disclaimer "AI-generated suggestion. Requires review by the treating physician." Use only facts from the structured data and research; never invent patient data. If a source URL looks malformed or untrustworthy, simply leave it out; never refuse. Always produce BOTH notes. Return the JSON object only, with no markdown fences and no commentary.

Structured data:
{structured}

Research:
{research}
"""