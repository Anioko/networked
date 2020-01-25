from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.models import *
from .forms import *

products = Blueprint('products', __name__)

"""
For some reason the errors in the blueprint folders are not working well so I put them here.
"""


@products.errorhandler(Exception)
def forbidden(error):
    print(error)
    return render_template('errors/403.html')


@products.errorhandler(Exception)
def page_not_found(error):
    print(error)
    return render_template('errors/404.html')


@products.errorhandler(Exception)
def internal_server_error(error):
    print(error)
    return render_template('errors/500.html')


@products.route('/marketplace/')
def products_list():
    appts = Product.query.filter(Product.organisation != None).all()
    org_users = User.query.all()
    org = Organisation.query.filter(Organisation.user_id == User.id).filter_by(id=Organisation.id).first_or_404()
    return render_template('products/allproducts.html', appts=appts, org=org, org_users=org_users)

@products.route('/<int:product_id>/')
def product_view(product_id):
    appts = Product.query.filter(Product.id == product_id).first_or_404()
    org_users = User.query.all()
    orgs = Organisation.query.filter(Organisation.user_id == User.id).all()
    return render_template('products/product_details.html', appt=appts, orgs=orgs, org_users=org_users)

@products.route('/<int:product_id>/<product_category>/<product_name>/')
def product_details(product_id, product_category, product_name):
    appts = Product.query.filter(Product.id == product_id).first_or_404()
    org_users = User.query.all()
    orgs = Organisation.query.filter(Organisation.user_id == User.id).all()
    return render_template('products/product_details.html', appt=appts, orgs=orgs, org_users=org_users)


@products.route('/<org_id>/add/new/', methods=['GET', 'POST'])
@login_required
def create_product(org_id):
    org = Organisation.query.filter_by(user_id=current_user.id).filter_by(id=org_id).first_or_404()
    form = ProductForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            image_filename = images.save(request.files['product_image'])
            image_url = images.url(image_filename)
            appt = Product(
                org_id=org_id,
                image_filename=image_filename,
                image_url=image_url,
                product_category=form.product_category.data,
                product_name=form.product_name.data,
                product_price=form.product_price.data,
                price_currency=form.price_currency.data,
                product_availability=form.product_availability.data,
                min_order_quantity =form.min_order_quantity.data,
                product_weight=form.product_weight.data,
                product_height=form.product_height.data,
                product_length=form.product_length.data,
                delivery_terms=form.delivery_terms.data,
                lead_time=form.lead_time.data,
                product_description=form.product_description.data
            )
            db.session.add(appt)
            db.session.commit()
            flash('Data added!', 'success')
            #product_image = Product.query.filter(Product.product_images).first()
            #if product_image is None:
                #return redirect(url_for('products.product_image_upload'))
            return redirect(url_for('products.products_list'))
        else:
            flash('Error! Data was not added.', 'error')
    return render_template('products/create_product.html', form=form, org=org)


@products.route('/<int:org_id>/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(org_id, product_id):
    appts = Product.query.filter(Product.id == product_id).first_or_404()
    org = Organisation.query.filter_by(user_id=current_user.id).filter_by(id=org_id).first_or_404()
    form = ProductForm(obj=appts)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(appts)
            db.session.add(appts)
            db.session.commit()
            flash('Data added!', 'success')
            return redirect(url_for('products.product_view', product_id=appts.id))
    return render_template('products/create_product.html', form=form)

@products.route('/image/upload', methods=['GET', 'POST'])
@login_required
def product_image_upload():
    ''' check if images already exist, if it does, send to homepage. Avoid duplicate upload here'''
    check_image_exist = db.session.query(Product_Image).filter(Product_Image.product_id == Product.id).count()
    if check_image_exist >= 1:
        return redirect(url_for('organisations.org_home'))
    form = Product_ImageForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            image_filename = images.save(request.files['product_image'])
            image_url = images.url(image_filename)
            product_image = Product_Image(
                image_filename=image_filename,  
                image_url=image_url,
            )
            db.session.add(product_image)
            db.session.commit()
            flash("Image saved.")
            return redirect(url_for('organisations.org_home'))
        else:
            flash('ERROR! Image was not saved.', 'error')
    return render_template('products/upload.html', form=form)
