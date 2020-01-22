import operator
from datetime import datetime, timedelta

from flask import Blueprint, render_template, url_for, make_response, current_app, request, send_from_directory

from app.models import Job, Question, User, Organisation, Service, Event, Promo, Product

sitemaps = Blueprint('sitemaps', __name__, static_folder="static")


@sitemaps.errorhandler(Exception)
def page_not_found(error):
    return render_template('errors/404.html')


###@sitemaps.route('/robots.txt')
@sitemaps.route('/sitemap_main.xml')
def static_from_root():
    return send_from_directory(sitemaps.static_folder, request.path[1:])


def return_xml(view, **kwargs):
    data = render_template(view, **kwargs)
    response = make_response(data)
    response.headers["Content-Type"] = "application/xml"
    return response


def routes():
    rules = []
    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0:
            methods = ','.join(sorted(rule.methods))
            rules.append((rule.endpoint, methods, str(rule)))

    sort_by_rule = operator.itemgetter(2)
    routes = []
    for endpoint, methods, rule in sorted(rules, key=sort_by_rule):
        if 'public.' in endpoint or 'seo' in endpoint:
            route = {'endpoint': endpoint, 'methods': methods, 'rule': rule}
            routes.append(route)
    return routes


def sitemap_date(val):
    return datetime.date(val)


@sitemaps.route('/sitemap.xml')
def index():
    sitemaps_list = [
        {'loc': url_for('sitemaps.main_xml', _external=True)},
        {'loc': url_for('sitemaps.jobs_xml', _external=True)},
        {'loc': url_for('sitemaps.companies_xml', _external=True)},
        {'loc': url_for('sitemaps.questions_xml', _external=True)},
        {'loc': url_for('sitemaps.profiles_xml', _external=True)},
        {'loc': url_for('sitemaps.events_xml', _external=True)},
        {'loc': url_for('sitemaps.services_xml', _external=True)},
        {'loc': url_for('sitemaps.services_xml', _external=True)},

    ]
    return return_xml('public/sitemapindex.html', sitemaps=sitemaps_list)


@sitemaps.route('/main.xml')
def main_xml():
    urlset = []
    ten_days_ago = datetime.now() - timedelta(days=10)
    for route in routes():
        urlset.append({'loc': url_for(route['endpoint'], _external=True),
                       'lastmod': '{}'.format(sitemap_date(ten_days_ago)),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)


@sitemaps.route('/jobs.xml')
def jobs_xml():
    urlset = []
    jobs = Job.query.all()
    for job in jobs:
        urlset.append({'loc': url_for('jobs.job_details', position_id=job.id, position_title=job.position_title,
                                      position_city=job.position_city, position_state=job.position_state,
                                      position_country=job.position_country, _external=True),
                       'lastmod': '{}'.format(sitemap_date(job.updated_at) if job.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)


@sitemaps.route('/companies.xml')
def companies_xml():
    urlset = []
    companies = Organisation.query.all()
    for company in companies:
        urlset.append({'loc': url_for('organisations.public_org', org_id=company.id, org_name=company.org_name, _external=True),
                       'lastmod': '{}'.format(sitemap_date(company.updated_at) if company.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)


@sitemaps.route('/questions.xml')
def questions_xml():
    urlset = []
    questions = Question.query.all()
    for question in questions:
        urlset.append({'loc': url_for('main.question_details', question_id=question.id, title=question.title, _external=True),
                       'lastmod': '{}'.format(sitemap_date(question.updated_at) if question.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)

@sitemaps.route('/services.xml')
def services_xml():
    urlset = []
    services = Service.query.all()
    for service in services:
        urlset.append({'loc': url_for('services.service_details', service_id=service.id, service_title=service.service_title, service_category=service.service_category, service_city=service.service_city, service_country=service.service_country, service_state=service.service_state,_external=True),
                       'lastmod': '{}'.format(sitemap_date(service.updated_at) if service.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)

@sitemaps.route('/products.xml')
def products_xml():
    urlset = []
    products = Product.query.all()
    for product in products:
        urlset.append({'loc': url_for('products.product_details', product_id=product.id,product_category=product.product_category,product_name=product.product_name,_external=True),
                       'lastmod': '{}'.format(sitemap_date(product.updated_at) if product.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)

@sitemaps.route('/events.xml')
def events_xml():
    urlset = []
    events = Event.query.all()
    for event in events:
        urlset.append({'loc': url_for('events.event_details', event_id=event.id, event_title=event.event_title,event_city=event.event_city, event_state=event.event_state, event_country=event.event_country, _external=True),
                       'lastmod': '{}'.format(sitemap_date(event.updated_at) if event.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)

@sitemaps.route('/promos.xml')
def promos_xml():
    urlset = []
    promos = Promo.query.all()
    for promo in promos:
        urlset.append({'loc': url_for('promos.promo_details', promo_id=promo.id, promo_title=promo.promo_title,
                                      promo_city=promo.promo_city, promo_state=promo.promo_state,
                                      promo_country=promo.promo_country, _external=True),
                       'lastmod': '{}'.format(sitemap_date(promo.updated_at) if promo.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)


@sitemaps.route('/public_profiles.xml')
def profiles_xml():
    urlset = []
    users = User.query.all()
    for user in users:
        urlset.append({'loc': url_for('main.public_profile', user_id=user.id, full_name=user.full_name, _external=True),
                       'lastmod': '{}'.format(sitemap_date(user.updated_at) if user.updated_at is not None else ''),
                       'changefreq': 'daily'})
    return return_xml('public/sitemap.html', urlset=urlset)
