# Doctor Note Taker

> You talk to the patient. The chart writes itself.

Doctor Note Taker listens to a medical consultation, transcribes it live, and turns it into a **SOAP clinical note** for the doctor and a **plain-language visit summary** for the patient. Before the note is written, it runs **live web research** for a differential diagnosis and next steps, with cited sources. The doctor reviews and edits both documents, then sends them by email in one click.

Built in a 3-hour hackathon with **Cline**, **Parallel** and **Composio**, plus **Claude** (Anthropic API) for the language work.

> ⚠️ **Demo with fictional patient data only.** This is a decision-support prototype. It does not replace clinical judgment, and every note is marked as an AI-generated suggestion that the treating physician must review.

---

## Features

### 1. Live consultation transcription
- **Soniox** real-time speech-to-text (model `stt-rt-v5`) when `SONIOX_API_KEY` is set:
  - **Speaker diarization:** turns are labelled **Doctor:** / **Patient:** from the actual voices. The first person to speak is treated as the doctor.
  - **Medical context:** the engine is told it's a medical consultation and given a list of medical terms (ibuprofen, dengue, NS1, petechiae and more), so it gets them right.
  - **One continuous session:** it doesn't stop after silence, and it reconnects automatically if the network drops.
  - Your Soniox key stays on the server. The browser only receives a temporary key valid for 5 minutes.
- **Automatic fallback** to Chrome's built-in **Web Speech API** (`en-US`) if no Soniox key is set or Soniox fails, so recording always works. The waveform shows which engine is in use ("listening · Soniox" or "listening · Chrome").
- **Live waveform** of your actual microphone signal while recording, with a timer and word/line counters.
- The transcript appears **line by line as a script**, and clinical terms (symptoms, vitals, medications, travel, tests) are **highlighted** as they're spoken.
- When lines start with `Doctor:` / `Patient:` they get **DR / PT badges**.
- **Better recognition:** the microphone is opened with noise suppression, echo cancellation and automatic gain. On newer Chrome builds that support it, the recognizer is also given a list of medical terms to listen for (vocabulary boosting).
- **No lost words:** Chrome stops listening after silence or about 60 seconds. The app restarts it automatically and keeps any words that hadn't been finalized yet.
- **✦ AI fix:** when you press **End**, Claude corrects misheard medical words (for example "I be profane" → *ibuprofen*, "dangy" → *dengue*, "N S one" → *NS1*), adds punctuation, and labels each turn **Doctor:** or **Patient:**. It never adds anything that wasn't said, and if the result looks rewritten rather than corrected, the original is kept. **Undo AI fix** restores the raw text, and the **✦ AI fix** button runs it again on demand.
- **Edit the transcript** by hand before generating the note.
- **Load demo**: a built-in fictional consultation (fever after travel, possible dengue) that types itself in, for demos without a microphone.

### 2. Automatic clinical note (one click: "Write the chart")
The backend runs a three-step pipeline:

| Step | What happens | Powered by |
|---|---|---|
| **Structure** | Extracts chief complaint, history of present illness, past history, medications, allergies, vitals, exam, key symptoms, and a clinical question. The transcript has no speaker labels; the model infers doctor vs. patient from context. Anything not said is recorded as *"Not reported"*, never invented. | Claude |
| **Research** | Searches the live web for a differential diagnosis (high / medium / low likelihood, with rationale), suggested tests, management, and red flags. It prefers CDC, WHO, NIH, PubMed and clinical guidelines, and returns real source links. | Parallel |
| **Write** | Produces a **SOAP note** (HTML) for the doctor, with differential, plan, red flags, linked sources and the required disclaimer, and a **patient summary** (HTML) in plain language with instructions and ER warning signs, but no differential and no jargon. Both use inline styles, so they display correctly in Gmail. | Claude |

The UI shows **live progress** for each step while you wait (usually about 35–45 seconds).

### 3. Review before anything is sent
Three tabs:
- **SOAP note**: fully editable in place. What you see is exactly what gets emailed.
- **Differential**: each diagnosis has a 5-bar likelihood meter and its rationale, plus red flags, suggested tests and management, and numbered clickable **sources**.
- **For the patient**: the editable plain-language summary.

### 4. Approve & send
- One click sends **two emails** through Gmail via **Composio**:
  - Doctor: `Clinical note – {patient name} – {date}`
  - Patient: `Your visit summary – {date}`
- The result for each email is shown separately, and a "*Sent*" stamp appears when both succeed.

### 5. Built to keep working during a live demo
- **Research fallback:** if Parallel's fast Responses API fails, it falls back to Parallel's Task API (`lite` processor) within a 120-second budget. If research is unavailable entirely, the note is still written and a warning is shown.
- **Bad links are dropped:** malformed or suspicious source URLs are filtered out before they reach the note.
- **No infinite waiting:** every Claude call has a 60-second timeout and one automatic retry if the model doesn't return valid JSON. The browser gives up after 150 seconds and shows an error instead of spinning forever.
- **Mailer stub:** if the `mailer/` package is missing, emails are printed to the server console instead, so the app still runs.
- **Mock mode:** open `http://localhost:8000/?mock` to try the whole UI with fake responses and no API calls.

---

## How it works

```
Browser (Web Speech API, en-US) ──► live transcript (editable)
        │
        ▼  POST /api/note
   1. Claude ─────► structured JSON + clinical question
   2. Parallel ───► differential, tests, management, red flags, sources
   3. Claude ─────► doctor SOAP note (HTML) + patient summary (HTML)
        │
        ▼  doctor reviews and edits in the UI
   "Approve & send" ──► POST /api/send ──► Composio Gmail × 2
```

### Tech stack
- **Backend:** Python, FastAPI, Uvicorn
- **AI:** Claude via the Anthropic API (default model `claude-haiku-5-5`, thinking off, for speed)
- **Speech-to-text:** Soniox real-time (`@soniox/client` Web SDK, loaded from a CDN), with Chrome's Web Speech API as fallback
- **Web research:** Parallel (Responses API first, Task API as fallback), via the `parallel-web` package and `httpx`
- **Email:** Composio, Gmail toolkit (`GMAIL_SEND_EMAIL`)
- **Frontend:** a single `static/index.html` with plain HTML, CSS and JavaScript (no build step). Typography and colors follow the Leontari design system: Instrument Sans, Instrument Serif, JetBrains Mono and Bricolage Grotesque, with a violet `#6d28d9` accent.
- No database, no auth, no Docker: the whole app runs as a single process.

---

## Getting started

### Prerequisites
- **Python 3.10+**
- **Google Chrome**, for live transcription. Other browsers can still use the demo and edit the transcript by hand.
- API keys for:
  - **Anthropic** (Claude): <https://console.anthropic.com>
  - **Parallel**: <https://platform.parallel.ai>
  - **Composio**, with a Gmail account connected to the Gmail toolkit: <https://app.composio.dev>
  - **Soniox** (recommended, for accurate transcription): <https://console.soniox.com>

### 1. Install

```bash
cd luca-live
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> If you install without a virtual environment on a Homebrew Python and get an `externally-managed-environment` error, either use the venv above or add `--break-system-packages`.

### 2. Configure

```bash
cp .env.example .env
```

Then fill in `.env`:

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude: structures the transcript and writes the notes |
| `PARALLEL_API_KEY` | Yes | Parallel: live web research |
| `COMPOSIO_API_KEY` | For sending | Composio API key |
| `COMPOSIO_USER_ID` | For sending | The Composio user that has Gmail connected |
| `SONIOX_API_KEY` | Recommended | Soniox real-time speech-to-text. If empty, Chrome's built-in recognition is used |
| `ANTHROPIC_MODEL` | No | Overrides the Claude model (default `claude-haiku-5-5`) |
| `PARALLEL_EFFORT` | No | Research depth: `low` (~5–10 s), `medium` (default, ~15–20 s), `high` (~30–60 s) |

`.env` is listed in `.gitignore`. Never commit real keys.

### 3. Run

```bash
uvicorn main:app --reload --port 8000
```

Open **<http://localhost:8000>** in Chrome.

### 4. Use it
1. In **Intake**, enter the patient name, patient email and doctor email.
2. Press the **record button** and allow microphone access, then hold the consultation. Or click **Load demo**.
3. Press **End**. Optionally click **Edit transcript** to fix anything.
4. Click **Write the chart →** and watch the three steps complete.
5. Review the **SOAP note**, the **Differential** and the **For the patient** tabs. Edit anything you like.
6. Click **Approve & send**. The doctor and the patient each receive their email.

---

## API

The frontend talks to these JSON endpoints. You can call them directly too.

### `GET /health`
```json
{"status": "ok"}
```

### `GET /api/demo`
Returns the fictional demo consultation.
```json
{"transcript": "Doctor: Good afternoon, what brings you in today?\n..."}
```

### `GET /api/stt-config` and `POST /api/soniox-key`
The page asks `/api/stt-config` which speech engine to use (`{"provider": "soniox"}` or `"browser"`). When Soniox is on, `/api/soniox-key` creates a short-lived (5-minute) Soniox key for the browser, so your real `SONIOX_API_KEY` never leaves the server.

### `POST /api/clean`
Fixes misheard medical words in a raw microphone transcript and adds `Doctor:` / `Patient:` labels. The UI calls this automatically when recording ends.

Request:
```json
{"transcript": "i took i be profane twice ... an N S one test for dangy"}
```
Response:
```json
{"transcript": "Patient: I took ibuprofen twice. ...\nDoctor: ... an NS1 test for dengue.", "changed": true}
```

### `POST /api/note`
Runs structure → research → write.

Request:
```json
{"transcript": "text", "patient_name": "John Smith", "patient_email": "x@x.com", "doctor_email": "y@y.com"}
```
Response:
```json
{
  "doctor_html": "<SOAP note html>",
  "patient_html": "<patient summary html>",
  "research": {
    "differential_diagnosis": [{"diagnosis": "", "likelihood": "high|medium|low", "rationale": ""}],
    "suggested_tests": [], "suggested_management": [], "red_flags": [],
    "sources": [{"title": "", "url": ""}]
  },
  "warnings": []
}
```

Example:
```bash
python3 -c "import json;print(json.dumps({'transcript':open('demo_transcript.txt').read(),'patient_name':'John Smith','patient_email':'patient@example.com','doctor_email':'doctor@example.com'}))" > test.json
curl -X POST localhost:8000/api/note -H "Content-Type: application/json" -d @test.json
```

### `POST /api/send`
Request:
```json
{"patient_name": "", "patient_email": "", "doctor_email": "", "doctor_html": "", "patient_html": ""}
```
Response:
```json
{"ok": true, "doctor": {"ok": true, "error": null}, "patient": {"ok": true, "error": null}}
```

Interactive API docs are available at **<http://localhost:8000/docs>**.

---

## Project structure

```
luca-live/
├── main.py               # FastAPI app: routes, CORS, static frontend, mailer fallback stub
├── core/
│   ├── llm.py            # Claude: structure() and write_notes()
│   ├── research.py       # Parallel: research(), with Responses API, Task API fallback, source cleaning
│   └── prompts.py        # STRUCTURE_PROMPT and WRITE_PROMPT
├── mailer/
│   ├── send.py           # send_email(to, subject, html) via Composio Gmail
│   ├── test_send.py      # test script to send one email
│   └── .env.example
├── static/
│   └── index.html        # the entire frontend (HTML, CSS and JS)
├── demo_transcript.txt   # fictional demo consultation
├── requirements.txt
├── .env.example          # template for .env
└── .gitignore
```

---

## Testing

- **UI without any API calls:** <http://localhost:8000/?mock>
- **Server is up:** `curl localhost:8000/health`
- **Full pipeline:** the `curl` example under [`POST /api/note`](#post-apinote)
- **Email only** (sends one real test email):
  ```bash
  python -m mailer.test_send you@example.com
  ```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **"Write the chart" takes a long time** | About 35–45 s is normal, and live research takes most of it. For faster demos, set `PARALLEL_EFFORT=low` in `.env`. Requests time out after 150 s with an error. |
| **The note is very short and says data "were not available"** | Claude failed. Check the server console for lines starting with `[llm]`, and confirm `ANTHROPIC_API_KEY` is valid and your account has access to the model in `ANTHROPIC_MODEL`. |
| **"Web research unavailable" warning** | Parallel failed. Check the console for `[research]` lines and confirm `PARALLEL_API_KEY` is set. The note is still written, without research. |
| **The record button is disabled, or "needs Google Chrome"** | Use Chrome and allow microphone access. Use `http://localhost`, because Chrome blocks the mic on plain-HTTP non-localhost addresses. |
| **Emails fail** | Run `python -m mailer.test_send you@example.com` to see the Composio error. Confirm `COMPOSIO_API_KEY` and `COMPOSIO_USER_ID`, and that Gmail is connected for that user in Composio. |
| **The console shows `[STUB] email to ...`** | The `mailer/` package or `composio` isn't installed, so emails are only printed. Run `pip install -r requirements.txt`. |
| **Transcription misses or mishears words** | Make sure `SONIOX_API_KEY` is set (the waveform should say "listening · Soniox"). Speak about an arm's length from the mic, one person at a time, with little background noise. A headset or external mic helps a lot. Chrome's recognizer runs on Google's servers, so a stable connection matters. After **End**, the **✦ AI fix** corrects most misheard medical terms, and you can always **Edit transcript** by hand. |
| **"Soniox unavailable", or the waveform says "listening · Chrome"** | Check the server console for `[soniox]` lines. Usually the key is wrong or the account is out of credit. Restart uvicorn after editing `.env`. |
| **You still see the old design** | Hard-refresh the browser (Cmd+Shift+R / Ctrl+Shift+R). |

---

## Hackathon sponsor tools
- **Cline**: wrote and debugged the code.
- **Parallel**: live web research for the differential diagnosis and next steps, with citations.
- **Composio**: sends the doctor and patient emails through the Gmail toolkit.

## Disclaimer
Doctor Note Taker is a hackathon prototype for **demonstration with fictional data only**. It is not a medical device, is not HIPAA-compliant, and must not be used with real patient information. All AI output is a suggestion that requires review by the treating physician.