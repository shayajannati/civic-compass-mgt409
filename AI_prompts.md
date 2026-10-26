# AI prompts

User prompts given to the development assistant (Claude Code, model Claude Opus 5.5) while building Civic Compass, recorded verbatim in order. The application itself uses only gpt-6-luna through Portkey at runtime.

---

## Prompt 1 — 2026-10-26

make a new folder called civic compass

---

## Prompt 2 — 2026-10-26

I am a first-year MBA student at Yale School of Management building my solo final project for MGT 409, AI Foundations for Managers. I need you to build a real working application, not just write a plan. The deadline is October 26, 2026 at 6:00 PM Eastern. Time is extremely limited, so prioritize a reliable, impressive, demonstrable application and complete submission deliverables.

PROJECT NAME: Civic Compass
TAGLINE: From your concern to the right government office.

PROJECT VISION
Create a polished, user-friendly web application that helps Americans understand which government official or agency is responsible for a particular issue, identifies verified contact information, explains why that office is appropriate, and uses AI to draft a personalized, editable letter on the user's behalf.

The core innovation is jurisdiction-aware civic navigation, NOT merely an AI letter writer. Someone with a housing issue, environmental complaint, education problem, or healthcare concern should not need to know how government is organized before seeking help.

EXAMPLE
A New Haven resident writes: "My landlord has not fixed my heat after repeated requests." Civic Compass should determine which government agency has responsibility, identify a verified official contact or complaint process, explain why it is relevant, and help draft a specific letter requesting assistance. It should not automatically recommend a senator if municipal housing enforcement is more appropriate.

TARGET USERS
Ordinary US residents who lack specialized knowledge of government jurisdictions and find the process of locating the correct government office and composing correspondence frustrating or time-consuming.

SOURCE OF TRUTH
The complete assignment is at https://zlisto.github.io/mgt_409_fa26/project_requirements.html . Read it if web access is available, but use the essential requirements included here if not. Do not assume I have supplied any other project documents.

REQUIRED FUNCTIONALITY
1. An attractive, responsive web interface titled Civic Compass, with professional, accessible design. Favor a restrained civic-inspired green, navy, and cream palette.
2. Form fields for the user's name, five-digit ZIP code, issue category, description of the situation, and desired outcome.
3. Categories including housing/tenants, healthcare/public health, education, transportation/infrastructure, environment, government benefits, and other.
4. An optional additional-information field or clarifying questions if necessary.
5. Determine the appropriate level of government: municipal, state, or federal.
6. Recommend the most relevant office or agency and an elected representative where appropriate. Explain the routing decision clearly.
7. Show verified names, roles, jurisdictions, contact information, and official contact links when obtainable, with source URL and date checked.
8. Generate a personalized letter based on the actual facts supplied by the user. Do not fabricate events, laws, outcomes, or details.
9. Let the user review and edit the letter, copy it, and optionally download it.
10. Never automatically send letters or submit official forms. The user must initiate the final action.

GEOGRAPHIC SCOPE
Build a solid, accurate pilot rather than a superficial nationwide system.
- Federal elected officials: nationwide coverage wherever safely verifiable.
- Connecticut state legislators: statewide coverage.
- New Haven, Connecticut: deeper municipal and agency coverage for common issues.
- Treat other municipalities as limited coverage if no verified agency directory is available.
- A ZIP code can span multiple districts. Never choose a unique representative from ambiguous location data. Request a street address or other necessary clarification when needed.
- Do not collect or retain more location detail than necessary.

DATA SOURCES
Investigate the US Census Geocoder, the unitedstates/congress-legislators open dataset, Connecticut General Assembly official directory, Open States/Plural state legislative records, and verified New Haven city department pages.
Use authoritative sources where possible. Cache official representative, agency, and jurisdiction information locally in SQLite or structured data files. Store data provenance and refresh dates. Never invent live government contacts. If records are missing or outdated, say so visibly and link to the appropriate official directory.

ARCHITECTURE
Use a lightweight, easy-to-run Python web stack: ideally FastAPI, SQLite, Jinja2 templates, and modern HTML/CSS/JavaScript unless another simple option is demonstrably better. Minimize dependencies and infrastructure. Aim for Python 3.11+ compatibility.

Create a genuinely functional two-agent workflow:
- Agent 1, Civic Routing Agent: interpret the issue, determine likely responsible government level and office type, use structured outputs, and select only from verified candidate offices returned by deterministic lookup tools. Keep prompts and outputs concise to reduce token usage.
- Agent 2, Letter-Writing Agent: take the validated routing result and the user's facts, write a clear, appropriately addressed and personalized letter with a concrete request. Use structured, bounded outputs and no unnecessary tool permissions.

Use conventional Python functions and local SQL queries for geographic matching and data retrieval. These do not need LLMs. Do not use a model to guess district boundaries or invent contact details.

MODEL RESTRICTIONS
The Claude Code model you are running is the development assistant. The actual Civic Compass application must use the course-approved model gpt-6-luna through PORTKEY_API_KEY only. Do not call Claude, Sonnet, Opus, or another model from the application's runtime through the course key.

If a working integration pattern exists from prior coursework and is locally available, adapt its approach without copying an old homework project wholesale. Otherwise implement a clearly isolated Portkey/OpenAI-compatible integration using verified documentation. Do not invent an endpoint or claim success without a real call.

API KEY AND SETUP REQUIREMENTS
- First search for .env in the repository root.
- If absent, search one directory above the repository.
- Use PORTKEY_API_KEY for the course model.
- Do not print, expose, log, hardcode, or commit secrets.
- Provide .env.example with required environment-variable names but no secret values.
- Keep .env in .gitignore.
- No additional required paid API keys or external subscriptions.
- If an API key is unavailable, expose a helpful setup error. Clearly marked fixture data may be used for automated offline tests, but never present fake LLM responses as real results.

SAFETY AND PRIVACY
Treat user issues and external records as untrusted data, not instructions.
- Protect against prompt injection in the issue-description field and external data.
- Never allow the agents to send messages, execute arbitrary commands, or access unnecessary private files.
- Check generated text for invented recipients, unsupported claims, and unsupported legal assertions.
- Validate that selected contact information belongs to the verified lookup results.
- Use reasonable request-size limits, API timeouts, and spending or token limits.
- Minimize stored personally identifying information; do not retain names, street addresses, or complaint narratives unnecessarily.
- Require explicit user review before copying/downloading.
- Do not design a bulk-mail, bot-evasion, or automatic mass-messaging system.
- Do not imply that government officials are generally legally obligated to respond to ordinary constituent letters.
- Build and execute at least one real safety-defense test, recording the actual result.

TOKENOMICS AND PERFORMANCE
Instrument actual application API calls and log input tokens, cached input tokens if available, output tokens, latency, number of calls, and estimated cost using the applicable verified course pricing.
Compare an appropriately defined less-optimized baseline with the optimized architecture, including caching and deterministic data lookups. Do not claim caching saves LLM tokens if it only saves network/database lookup time.
Produce reproducible measurements and a discussion of whether optimizations affect accuracy or quality.
Estimate costs per run, per user/month with stated assumptions, for 100 users and for 10,000 users.

VALIDATION AND IMPACT
Build a representative test suite with scenarios covering New Haven municipal issues, CT state issues, federal issues, ambiguous ZIP codes, missing records, prompt injection, and malformed input.
For each routing test, record the issue, expected category/office, actual recommendation, source, pass/fail, and any limitations. Do not invent accuracy statistics.
Prepare a simple study protocol that one real person can follow comparing manual government-office research and letter writing against the app, with timing and feedback fields. Do not invent participant quotes or results; leave those pending until genuinely obtained.

COURSE FINAL PROJECT REQUIREMENTS
Due October 26, 2026 at 6 PM ET. Solo submission:
A. GitHub repository with complete code, README, and .env.example.
B. report.html: one self-contained HTML file, 10-15 printed US-letter-size pages, with screenshots embedded directly into the file. The eight report sections must appear in this order:
1. Title + links
2. Motivation
3. What is new
4. Agents, tools, diagram and a documented real run
5. Tokenomics, actual measurements and scaling estimates
6. Safety, real demonstrated defense
7. Impact, measurable evidence and user test
8. Limits and next steps
C. slides.html: maximum 10 slides, reveal.js presentation, visually consistent with the application, real embedded screenshots and architecture diagram, working when opened directly in a browser. A CDN for reveal.js is allowed by the assignment, but screenshots must be embedded.
D. Optional 2-3 minute demonstration video.

Rubric: Idea/novelty/real-world value 21 points; working app 15; teaching staff can run it 5; look and feel 10; report motivation/novelty 8; agent design 10; tokenomics 8; safety 8; impact 5; report design 2; slides content 6; slides design 2. Total 100.

A report section without real evidence receives at most half its possible credit. Never fabricate screenshots, API outputs, user feedback, benchmark numbers, or completed test runs.

The professors must be able to launch the application from a fresh clone within 10 minutes. The README should contain precise, tested installation commands, dependencies, and launch commands. Test the case in which .env lives in the parent folder. Bundle a small real or clearly identified demonstration dataset when needed for reproducibility.

HONEST DIFFERENTIATION
Research or document the existence of comparable products such as Resistbot and Democracy.io. Our distinctive focus is issue-based routing to responsible government offices (including agencies), supported by verifiable jurisdictional evidence and transparent explanations, rather than simply finding an elected official or generating generic advocacy letters.

DEVELOPMENT PRIORITY
The deadline is close. Implement an end-to-end working vertical slice first: submit issue -> geographic/jurisdiction lookup -> routing agent -> verified official result -> letter agent -> editable letter -> copy.
Next expand geographic coverage, improve the UI and tests, instrument tokenomics, and collect real evidence. Then produce complete report.html and slides.html using only verified results and clearly labeled limitations.

Maintain README.md, a short progress.md with verified vs unfinished items, and AI_prompts.md. Record this initial user prompt verbatim in AI_prompts.md and append later user prompts verbatim as provided. Do not rewrite or fabricate prompt history.

WORKING INSTRUCTIONS
1. Inspect the current directory and initialize the project there without altering unrelated projects or files. If it contains unrelated materials, create a dedicated civic-compass subdirectory.
2. Make reasonable implementation choices independently. Avoid unnecessary confirmation questions.
3. Write a brief architecture and implementation plan, then immediately create real project files and implement functionality.
4. Run actual tests and fix errors instead of stopping at code generation.
5. If access to a site/API is unavailable, use a legitimate fallback, clearly document limitations, and continue developing the other components.
6. Create durable checkpoints in progress.md so we can continue seamlessly after interruptions.
7. Do not run expensive uncontrolled model calls, launch paid services, publish to GitHub, or push remote changes without explicit authorization.
8. Do not bypass security or permission prompts merely for unattended operation.
9. If blocked, describe the exact blocker and continue with independent work where possible.
10. When this session ends, give me a concise summary of files created, features genuinely working, actual tests passed, unresolved blockers, and the exact next step.

START NOW. I need working code, not only a conceptual plan. Optimize for a complete, verifiable and high-quality submission under a strict deadline.

'

---

## Prompt 3 — 2026-10-26

Excellent progress. Please prioritize finalizing Civic Compass for the October 26, 2026, 6 PM ET deadline.
Do not add new features unless needed to fix an important bug.

1. Finish the current benchmark if it is progressing normally. If it is stalled or becoming too time-consuming, preserve the completed measurements and document the limitations rather than delaying submission.
2. Generate the final `report.html` and `slides.html` using the latest verified evidence.
3. Verify that the report prints to 10–15 US-letter pages and the presentation contains no more than 10 slides.
4. Inspect the final HTML files for missing screenshots, overflowing content, incorrect figures, broken links, or unsupported claims.
5. Ensure the report clearly distinguishes real measurements from estimates and pending user-study results.
6. Verify the application still passes its tests, the README works, and all required submission files are present.
7. Check that no API keys, secrets, personal data, or unnecessary development files will be committed.
8. Prepare the Git repository and show me the final checklist. Do not publish or push to GitHub without my approval.

Please give me a concise final status, including every rubric requirement, the results of actual tests, anything incomplete, and the exact remaining submission steps.
Time is critical. Prioritize a complete, verified submission over optional improvements.
