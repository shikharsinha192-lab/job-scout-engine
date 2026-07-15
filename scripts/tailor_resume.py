import os
import json
import sys
import argparse
from dotenv import load_dotenv
from scripts.gemini_client import generate_content_with_fallback, trim_prompt

# Load .env file if present
load_dotenv()

def tailor_resume(base_json_path, jd_text, output_json_path, api_key=None):
    # Ensure directories exist (guard: dirname may be empty for bare filenames)
    output_dir = os.path.dirname(output_json_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Read base resume
    if not os.path.exists(base_json_path):
        raise FileNotFoundError(f"tailor_resume: Base resume not found at {base_json_path}")
        
    with open(base_json_path, 'r', encoding='utf-8') as f:
        base_data = json.load(f)
    
    # Compact JSON removes indentation whitespace — reduces tokens by ~30%
    compact_resume = json.dumps(base_data, separators=(',', ':'))
    # Trim JD to 800 chars max — anything beyond is boilerplate the model ignores anyway
    jd_trimmed = jd_text[:800].strip()

    prompt = f"""ATS resume optimizer. Customise the candidate's resume JSON for the JD below.
RULES (strict):
1. ZERO HALLUCINATION: Add nothing not in the base resume. No invented skills, tasks, metrics.
2. Numbers are sacred: Do not alter any figures.
3. No new bullet points. Reorder existing ones. Rephrase using JD keywords only.
4. NO markdown (**/*/##) anywhere in JSON values. Plain text only.
5. Consulting clients: Preserve consulting client names as in the base resume.
6. Return ONLY the raw JSON object. No code fences, no explanation.

JD (trimmed):
{jd_trimmed}

BASE RESUME JSON:
{compact_resume}

Tailored JSON:"""

    try:
        # Use the central fallback router to protect against quota limits
        prompt = trim_prompt(prompt, max_tokens=5000)
        result = generate_content_with_fallback(prompt)
        raw_text = result.get("text", "").strip() if result.get("success") else ""
        print(f"  [AI Router] Model used: {result.get('model')} | Confidence: {result.get('confidence')}")
        
        if not raw_text:
            raise Exception("AI router returned empty string (both keys likely failed).")
        
        # Clean response text if wrapped in markdown code blocks
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        # Parse and save tailored resume
        tailored_data = json.loads(raw_text)
        
        # Simple schema preservation check
        required_keys = ["personal_info", "summary", "work_experience", "education", "skills"]
        for rk in required_keys:
            if rk not in tailored_data:
                # Fall back to base key if missing
                tailored_data[rk] = base_data[rk]
                
        # Trim bullet points to keep resume concise (max 5 per experience)
        for exp in tailored_data.get('work_experience', []):
            if isinstance(exp.get('bullets'), list) and len(exp['bullets']) > 5:
                exp['bullets'] = exp['bullets'][:5]
        # Write trimmed resume to file
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(tailored_data, f, indent=2)
            
        print(f"Successfully tailored resume JSON saved at: {output_json_path}")
        
    except Exception as e:
        print(f"Error calling Gemini API: {str(e)}")
        print("Falling back to base resume JSON.")
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tailor a master resume to a specific job description.")
    parser.add_argument("--base", default="data/resume_base.json", help="Path to base resume JSON")
    parser.add_argument("--jd", required=True, help="Path to text file containing target JD")
    parser.add_argument("--out", required=True, help="Path to save tailored resume JSON")
    parser.add_argument("--key", default=None, help="Gemini API Key")
    
    args = parser.parse_args()
    
    # Read JD file
    if not os.path.exists(args.jd):
        print(f"Error: Job description file not found at {args.jd}")
        sys.exit(1)
        
    with open(args.jd, 'r', encoding='utf-8') as f:
        jd_content = f.read()
        
    tailor_resume(args.base, jd_content, args.out, args.key)
