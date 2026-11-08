---
name: melbourne-job-search
description: Search real, current job ads in Melbourne on SEEK, LinkedIn and Victorian Government Careers with one script, remove cleaning jobs, and mark jobs already shown as "seen". Use it for every new job search and whenever the user asks for more or different jobs.
---

# Melbourne job search

One script does the search: `scripts/search.py` in this skill's folder. It uses only the Python
standard library. It prints compact JSON.

## Search

Run all keyword sets and all sources in one command. One command costs less than many.

```bash
python3 <this skill folder>/scripts/search.py search \
  -k "admin assistant" -k "receptionist" -k "customer service" \
  --type fulltime \
  --seen <memory store mount>/seen.json
```

- `-k`: one keyword set per flag. Use two or three sets in English that match the request and the
  profile (experience, certifications). Use job titles employers write, for example
  "warehouse assistant", "customer service officer", "admin assistant", "retail assistant",
  "receptionist", "barista", "aged care", "kitchen hand".
- `--type`: `fulltime` (default), `parttime`, `contract`, `casual`, or `any`.
- `--sources`: default `seek,linkedin,vic`. Use `--sources vic` for government jobs only.
- `--seen`: the `seen.json` path in the memory store mount (for example
  `/mnt/memory/job-finder-memory/seen.json`). If no memory store is mounted, leave the flag out.
- `--limit`: default 40.

The output has:

- `source_status`: `ok` or `failed: <reason>` for each source. Tell the user which sources failed.
- `jobs`: each job has `title`, `company`, `location`, `work_type`, `salary`, `posted`, `summary`,
  `url`, `source`, `status` (`new` or `seen`).
- `excluded_cleaning`: how many cleaning jobs the script removed.

The script removes cleaning jobs by title. It does not remove anything else; you choose.

## Remember the jobs you showed

After you choose the jobs for your answer, save their URLs in one command:

```bash
python3 <this skill folder>/scripts/search.py remember \
  --seen <memory store mount>/seen.json URL1 URL2 URL3
```

The file keeps only URLs and dates, never profile data. It keeps the newest 1,000 URLs.

## Job details

The search gives a short summary only. If the user asks about one job (requirements, hours,
how to apply), fetch the job URL with the web fetch tool. SEEK pages are at `www.seek.com.au`,
LinkedIn pages at `www.linkedin.com`, government jobs at `www.careers.vic.gov.au`.
If a page does not load, say so and give the link.

## Pay rates

For a question about minimum pay, fetch the pay guide from `www.fairwork.gov.au`. Say that the
award rate depends on the award and the classification, and give the link.

## Limits

- LinkedIn's list does not show the work type. The script writes `fulltime (search filter)`:
  the job matched the filter, but the ad can say otherwise.
- Victorian Government Careers does not show the location or the date in its list.
- Indeed blocks automated requests. Do not try it.
