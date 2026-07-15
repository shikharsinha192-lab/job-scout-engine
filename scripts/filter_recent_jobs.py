import datetime
import pathlib
import re

# Paths to the source markdown files containing job listings
SOURCE_FILES = [
    pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/job_listings_1_50.md"),
    pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/job_listings_51_150.md"),
]

# Destination file for the filtered list (jobs posted within the last 3 weeks)
DEST_FILE = pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/filtered_job_listings_1_150.md")

# Helper to extract a date string from a line if present. The markdown reports a global date like
# "> **Date:** May 23, 2026". Individual listings currently do not embed a separate posted date,
# so we fall back to the global date of the file.
DATE_PATTERN = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b")

def extract_global_date(lines: list[str]) -> datetime.datetime:
    for line in lines:
        if "> **Date:**" in line:
            m = DATE_PATTERN.search(line)
            if m:
                return datetime.datetime.strptime(m.group(0), "%B %d, %Y")
    # If not found, assume today (will keep the entry)
    return datetime.datetime.now()

def main():
    three_weeks_ago = datetime.datetime.now() - datetime.timedelta(weeks=3)
    filtered_lines = []

    for src in SOURCE_FILES:
        if not src.is_file():
            print(f"Source file not found: {src}")
            continue
        lines = src.read_text(encoding="utf-8").splitlines()
        file_date = extract_global_date(lines)
        # If the file's global date is newer than the cutoff, keep the whole file content.
        if file_date >= three_weeks_ago:
            filtered_lines.append("# Filtered Job Listings (source: " + src.name + ")\n")
            filtered_lines.extend(lines)
            filtered_lines.append("\n---\n")
        else:
            # The whole file is older – skip it entirely.
            print(f"Skipping outdated file: {src}")

    # Write the combined filtered listings.
    DEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEST_FILE.write_text("\n".join(filtered_lines), encoding="utf-8")
    print(f"Filtered job listings written to {DEST_FILE}")

if __name__ == "__main__":
    main()
