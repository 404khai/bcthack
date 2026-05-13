<role>
You are a Senior Python Engineer fixing a deprecated SDK dependency 
and updating project documentation.
</role>

<context>
Our project uses google.generativeai (deprecated) in shared/llm_client.py.
The terminal warning says:
"All support for the google.generativeai package has ended. 
Please switch to the google.genai package as soon as possible."

Migration reference: https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md

The new package is: google-genai
Install: pip install google-genai

Key API differences:
  OLD (google.generativeai):
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.text

  NEW (google.genai):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=0.7,
        )
    )
    text = response.text

Our current shared/llm_client.py structure:
C:\Users\DanielsFega\Hackathons\bcthack\shared\llm_client.py

Our current README.md:
C:\Users\DanielsFega\Hackathons\bcthack\README.md

Our current task_a/requirements.txt:
C:\Users\DanielsFega\Hackathons\bcthack\task_a\requirements.txt


Our current task_b/requirements.txt:
C:\Users\DanielsFega\Hackathons\bcthack\task_b\requirements.txt
</context>

<task>
Make the following changes completely:

1. shared/llm_client.py
   - Replace all google.generativeai imports with: from google import genai
   - Replace genai.configure() with: client = genai.Client(api_key=...)
   - Update generate call to use client.models.generate_content() with 
     types.GenerateContentConfig for system_instruction and max_output_tokens
   - Since the new SDK's generate_content is synchronous, wrap it with 
     asyncio.to_thread() to keep the async interface intact
   - Keep the same public interface: 
       async def complete(system: str, user: str, max_tokens: int = 1000) -> str
   - Keep retry logic and FREE_TIER_MODE delay (1 second between calls)
   - Keep the test_connection() function at the bottom
   - Remove any FutureWarning suppression code if present

2. task_a/requirements.txt
   - Remove: google-generativeai
   - Add: google-genai>=0.8.0

3. task_b/requirements.txt
   - Remove: google-generativeai  
   - Add: google-genai>=0.8.0

4. README.md — update these sections:

   a) Tech Stack section:
      Change: "Anthropic Claude via anthropic Python SDK"
      To: "Google Gemini 2.5 Flash via google-genai Python SDK (free tier)"

   b) Add a new "Environment Setup" section between Quick Start and 
      Architecture Overview:
      
      ## Environment Setup
      
      ### Python Virtual Environment
```bash
      # Create and activate virtual environment
      python -m venv venv
      
      # Windows (PowerShell)
      venv\Scripts\Activate.ps1
      
      # Windows (CMD)
      venv\Scripts\activate.bat
      
      # Mac/Linux
      source venv/bin/activate
      
      # Install all dependencies
      pip install -r task_a/requirements.txt
      pip install -r task_b/requirements.txt
```
      
      ### API Keys
      Get your free Gemini API key at: https://aistudio.google.com/apikey
      No billing required for the free tier (1,500 requests/day).
      Add it to your .env file: GEMINI_API_KEY=your_key_here

   c) Update .env.example references:
      Change ANTHROPIC_API_KEY to GEMINI_API_KEY everywhere in README

   d) Update the Dataset Setup → Ingest section to add this note:
      "Ensure your venv is activated before running any python commands"

5. .env.example
   - Remove: ANTHROPIC_API_KEY=
   - Add: GEMINI_API_KEY=your_gemini_api_key_here
   - Add comment above it: # Get free key at https://aistudio.google.com/apikey

<constraints>
- Do not change any other files
- Do not change the public interface of llm_client.py
- The async wrapper using asyncio.to_thread() is mandatory — 
  FastAPI endpoints depend on the async interface
- Output every file in full with its path as a comment header
- No truncation
</constraints>