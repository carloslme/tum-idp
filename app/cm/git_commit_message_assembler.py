import requests
import csv

# GitHub repo info
OWNER = "Significant-Gravitas"  
REPO = "AutoGPT"   
TOKEN = "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" 

# GitHub API setting
BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# only for construct dataset
ALLOWED_PREFIXES = ("feat(", "fix(", "build(", "chore(", "docs(", "style(", "refactor(", "test(")
OUTPUT_CSV = "filtered_commits.csv"

MAX_COMMITS = 10

def fetch_commits() -> list[dict]:
    """
    Get commit SHA from Github via API.
    This function can be used for multiple commit message modification.
    :return: A list of commit message SHA in list of json.
    """
    # get all commits
    commits = []
    page = 1
    # GitHub API maximal 100 per page
    per_page = 100

    while len(commits) < MAX_COMMITS:
        url = f"{BASE_URL}/commits?page={page}&per_page={per_page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch commits: {response.status_code}")
            break

        data = response.json()
        if not data:
            break

        commits.extend(data)
        if len(commits) >= MAX_COMMITS:
            commits = commits[:MAX_COMMITS]

        page += 1

    return commits

def fetch_commit_details(commit_sha) -> dict[str]:
    """
    Get commit messages from Github via API.
    This function can be used for multiple commit message modification.
    :param commit_sha: SHA of commit message.
    :return: A list of commit message SHA in list of json.
    """
    url = f"{BASE_URL}/commits/{commit_sha}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch commit details for {commit_sha}: {response.status_code}")
        return None
    return response.json()

def save_to_csv(filtered_commits):
    """
    ***Not useful for the repo, only for test***
    Convert CM to a csv to construct a dataset for calculating classification accuracy.
    """
    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Commit Message", "Code Changes"])

        for commit in filtered_commits:
            writer.writerow([commit["message"], commit["code_changes"]])

    print(f"Filtered commits saved to {OUTPUT_CSV}")

def filter():
    """
    ***Not useful for the repo, only for test***
    Filter CM with large commit message & incorrect prefix.
    Only to construct a dataset. 
    """
    print("Fetching commits...")
    commits = fetch_commits()

    print(f"Total commits fetched: {len(commits)}")
    filtered_commits = []
    count = 0

    # multithreading is better but I haven't implemented it yet :)
    for commit in commits:
        print(count)
        count += 1
        sha = commit["sha"]
        commit_details = fetch_commit_details(sha)

        if not commit_details:
            continue

        # filter commit message
        commit_message = commit_details["commit"]["message"]
        if not commit_message.startswith(ALLOWED_PREFIXES):
            continue

        files = commit_details.get("files", [])
        total_changes = sum(file["changes"] for file in files if "changes" in file)

        # commit message diff should < 100
        if total_changes > 100:
            continue

        # assemble code diff
        code_changes = ""
        for file in files:
            patch = file.get("patch", "No patch available")
            code_changes += f"\n--- {file['filename']} ---\n{patch}\n"

        # save filtered commit message
        filtered_commits.append({
            "message": commit_message,
            "code_changes": code_changes.strip()
        })

    save_to_csv(filtered_commits)

if __name__ == "__main__":
    filter()