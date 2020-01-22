from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
from bs4 import BeautifulSoup
import json
import requests
from app.models import *

crawlers = Blueprint('crawlers', __name__)




# url = 'https://jooble.org/jobs-healthcare/Arizona?p=1'

jobs_ids = []
jobs_desc = []

# 50 pages is maximum returned by this server so p <= 50
# for testing purpose this is limited to 5
# you can change it however you want

for p in range(5):
    url = f'https://jooble.org/jobs-healthcare/Arizona?p={p+1}'
    print(f'Going for page {p+1}')
    list_page = requests.get(url)
    soup = BeautifulSoup(list_page.text, 'html.parser')
    jobs = soup.findAll(
        'div',
        {'class': 'vacancy_wrapper'}
    )
    for job in jobs:
        try:
            job_id = job.get('id')
            jobs_ids.append(job_id)
        except Exception as e:
            print(e)

# Get the job page
for job_id in jobs_ids:
    job = {}
    print(f'Going for id: {job_id}')
    job['id'] = job_id

    url = f'https://jooble.org/desc/{job_id}'
    job_page = requests.get(url)
    soup = BeautifulSoup(job_page.text, 'html.parser')

    # Job title.
    title = soup.find(
        'h1',
        {'class': 'desc_info-header'}
    )
    job['title'] = title.text.strip()

    # Job Apply link
    job_apply = soup.find(
        'a',
        {'class': 'respond-vacancy_button'}
    )
    if job_apply is not None:
        job['link'] = job_apply.get('href')
    else:
        job['link'] = url

    # Job info
    job_info_title = soup.findAll(
        'td',
        {'class': 'title-column'}
    )

    job_info_value = soup.findAll(
        'td',
        {'class': 'value-column'}
    )
    for t, v in zip(job_info_title, job_info_value):
        # Company
        if t.text.strip() == 'Company:':
            job['company'] = v.text.strip()
        # Location
        elif t.text.strip() == 'Location:':
            job['location'] = v.text.strip()
        # Job Type
        elif t.text.strip() == 'Job Type:':
            job['jobType'] = v.text.strip()
        # Salary
        elif t.text.strip() == 'Salary:':
            job['salary'] = v.text.strip()
        # Log this and manually handlle it
        else:
            print('Log This')
    job_desc_text = soup.find(
        'div',
        {'class': 'desc_text_paragraph'}
    )
    job['description'] = str(job_desc_text)
    jobs_desc.append(job)

with open('jobs.json', 'w') as f:
    # json.dump(jobs_desc, f)
    f.write(json.dumps(jobs_desc, indent=4))
