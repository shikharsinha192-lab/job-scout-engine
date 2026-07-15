import glob
import re

for f in glob.glob('c:/Users/91639/Documents/antigravity/job-scout-engine/scripts/extractors/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # 1. Fix run_actor to execute_run
    content = content.replace('self.run_actor(', 'self.execute_run(')
    content = content.replace('self.execute_run(ACTOR_ID', 'self.execute_run(self.ACTOR_ID')

    # 2. Fix job_boards.py run_input inline dict to be a variable
    content = re.sub(r'self\.execute_run\(self\.ACTOR_ID,\s*(\{[^}]+\})\)', r'run_input = \1\n        raw_data = self.execute_run(self.ACTOR_ID, run_input)', content)

    # 3. Add maxItems and maxPages to run_input
    # Find the run_input dictionary assignment
    def add_limits(match):
        dict_content = match.group(1)
        # remove existing maxItems/maxPages if any
        dict_content = re.sub(r',\s*"maxItems":\s*\d+', '', dict_content)
        dict_content = re.sub(r',\s*"maxPages":\s*\d+', '', dict_content)
        
        # Ensure it's properly formatted. It might end with } or have newlines.
        if dict_content.endswith('\n        }'):
            return "run_input = {" + dict_content[:-10] + ',\n            "maxItems": 80,\n            "maxPages": 3\n        }'
        elif dict_content.endswith('}'):
            return "run_input = {" + dict_content[:-1] + ', "maxItems": 80, "maxPages": 3}'
        else:
            return match.group(0)

    content = re.sub(r'run_input\s*=\s*\{([^}]+)\}', add_limits, content)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f"Updated {f}")
