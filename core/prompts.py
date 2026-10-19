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

WRITE_PROMPT = """
Using the structured data and the attached research, write: (1) a SOAP clinical note in HTML for the physician, with differential diagnosis, plan, red flags, and linked sources; (2) an HTML summary for the patient in plain language, with no differential diagnosis and no jargon, including instructions and warning signs that require urgent care. Return JSON: {{"doctor_html": "...", "patient_html": "..."}}.

Formatting rules: use only inline styles (Gmail-safe, no <style> tags, no classes). Make every source a clickable <a href> link. End the doctor note with the exact disclaimer "AI-generated suggestion. Requires review by the treating physician." Use only facts from the structured data and research; never invent patient data. If a source URL looks malformed or untrustworthy, simply leave it out; never refuse. Always produce BOTH notes. Return the JSON object only, with no markdown fences and no commentary.

Structured data:
{structured}

Research:
{research}
"""