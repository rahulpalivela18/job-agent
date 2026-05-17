import json
import os

FILE = "jobs.json"


def load_jobs():
    if not os.path.exists(FILE):
        return []

    try:
        with open(FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_job(job_data):
    jobs = load_jobs()
    for j in jobs:
        if j["url"] == job_data["url"]:
            j.update(job_data)
            break
    else:
        jobs.append(job_data)

    with open(FILE, "w") as f:
        json.dump(jobs, f, indent=2)

    print("Saved!!")


def is_already_applied(url):
    jobs = load_jobs()
    # return boolean along with company name
    for j in jobs:
        if j["url"] == url and j["status"] == "applied":
            return True, j["company"]
    return False, ""
