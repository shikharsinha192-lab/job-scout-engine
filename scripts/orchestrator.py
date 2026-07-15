import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Master Intelligence Orchestrator with Optimized Platform Queries")

    # Platform-specific highly relevant queries for Freelance/Paid Marketing roles
    queries = {
        "linkedin.py": '"paid marketing manager" OR "paid ads manager" OR "senior growth marketer" OR "freelance marketing"',
        "reddit.py": '("hiring" OR "looking for") AND ("paid ads" OR "growth marketer" OR "freelance marketing")',
        "x.py": '("hiring" OR "looking for") ("growth marketer" OR "paid ads" OR "freelance marketing") -is:retweet',
        "meta.py": '#hiringmarketer OR #freelancemarketing OR #growthmarketing'
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    extractors_dir = os.path.join(base_dir, "extractors")
    reports_dir = os.path.abspath(os.path.join(base_dir, "..", "data", "reports"))

    os.makedirs(reports_dir, exist_ok=True)
    master_report_path = os.path.join(reports_dir, "master_report.md")
    
    with open(master_report_path, "w", encoding="utf-8") as f:
        f.write("# Master Intelligence Report\n")
        f.write("**Mode:** Platform-Specific Optimized Queries\n\n")

    for script_name, specific_query in queries.items():
        script_path = os.path.join(extractors_dir, script_name)
        if not os.path.exists(script_path):
            logger.warning(f"Extractor {script_name} not found. Skipping.")
            continue

        logger.info(f"Triggering {script_name} with optimized query: '{specific_query}'")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.dirname(base_dir)

            result = subprocess.run(
                [sys.executable, script_path, specific_query],
                capture_output=True,
                text=True,
                check=True,
                env=env
            )
            
            with open(master_report_path, "a", encoding="utf-8") as f:
                f.write(f"## Report from {script_name}\n")
                f.write(f"**Query Used:** `{specific_query}`\n\n")
                f.write(result.stdout)
                f.write("\n---\n\n")
                
            logger.info(f"Successfully finished {script_name}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Extractor {script_name} failed with exit code {e.returncode}")
            logger.error(f"Error output: {e.stderr}")

    logger.info(f"Orchestration complete. Master report saved to {master_report_path}")

if __name__ == "__main__":
    main()
