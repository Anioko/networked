import bleach
from flask import Blueprint, render_template, abort, flash, redirect, request, jsonify
from flask_login import current_user, login_required
from sqlalchemy import desc, func
from .forms import *
from app.models import * 
import flask_profiler
from app import cache

post_blueprint = Blueprint('post', __name__)


@post_blueprint.errorhandler(Exception)
def page_not_found(error):
    print(error)
    return render_template('errors/404.html')


def clean(posts):
    for post in posts:
        post.text = bleach.clean(post.text)



@post_blueprint.route('/posts', methods=['GET', 'POST'])
@flask_profiler.profile()
#@cache.memoize(timeout=5)
@login_required
def post_create():
    form = PostForm()
    edit_form = PostForm()
    author = db.session.query(User).filter_by(id=current_user.id).first()
    if request.method == 'POST':
        if form.validate_on_submit():
            names_json, urls_json = "", ""
            if request.files['photo']:
                image_filenames = []
                image_urls = []
                for i, file in enumerate(request.files.getlist(form.photo.name)):
                    image_filename = images.save(file)
                    image_url = images.url(image_filename)
                    image_filenames.append({i: image_filename})
                    image_urls.append({i: image_url})
                names_json, urls_json = json.dumps(image_filenames), json.dumps(image_urls)
            
            posts = Post(
                image_filename=names_json,
                image_url=urls_json,
                text=form.text.data,
                post_privacy=form.post_privacy.data,
                user_id=current_user.id,
                author=author.full_name
            )
            list_of_posts = cache.get("p")
            if list_of_posts is None or not list_of_posts:
                list_of_posts = []
            #list_of_posts.append(posts) I disabled it because it showed "{ post_wid.post_wid(post, moment, current_user) } on the post page and some post timestamp issue"
            cache.set("p", list_of_posts)
            author.newscaster_points = author.newscaster_points + 1
            author.newscaster_badge = get_level(author.newscaster_points) + " Newscaster"
            db.session.add(posts)
            db.session.commit()
            flash("Posted.", 'success')

            return redirect(url_for('post.post_create'))
        else:
            flash('ERROR! Post was not created.', 'error')
    else:
        form.photo.flags.required = False
        form.process()
    follow_lists = db.session.query(User).filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = db.session.query(Job).filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(Job.pub_date.asc()).all()
    followed_ids = [f.id for f in current_user.followed.all()]
    posts = db.session.query(Post).order_by(Post.created_at.desc()).filter(or_(
        Post.user_id == current_user.id,
        and_(Post.user_id.in_(followed_ids), Post.post_privacy == 1),
        and_(Post.user_id != current_user.id, Post.post_privacy == 0))).limit(15).all()
    clean(posts)

    ''' this is where users will see their feeds'''
    data = cache.get("p")
    if not data or data is None:
        data = []
    data.reverse()
    #users = User.query.filter(Question.user_id == User.id).first()
    #questions = Question.query.filter(Question.user_id!=None).order_by(desc(Question.timestamp)).all()
    return render_template('posts/create_post.html', form=form,
                           follow_lists=follow_lists, jobs=jobs, 
                           author=author, edit_form=edit_form, data = data)#, #questions=questions, users=users)

@post_blueprint.route('/load_more/<count>')
@flask_profiler.profile()
#@cache.memoize(timeout=5)
def load_more(count):
    count = int(count)
    followed_ids = [f.id for f in current_user.followed.all()]
    posts = db.session.query(Post).order_by(Post.created_at.desc()).filter(or_(
        Post.user_id == current_user.id,
        and_(Post.user_id.in_(followed_ids), Post.post_privacy == 1),
        and_(Post.user_id != current_user.id, Post.post_privacy == 0))).all()
    if count == 0:
        posts = posts[0:15]
    elif count >= len(posts):
        return "<br><br><h2>No more Posts</h2>"
    else:
        posts = posts[count:count + 15]
    clean(posts)
    return render_template('posts/posts.html', posts=posts)


@post_blueprint.route('/post/<post_id>', methods=['GET'])
@flask_profiler.profile()
#@cache.memoize(timeout=5)
@login_required
def view_post(post_id):
    #post = Post.query.filter_by(id=post_id).first_or_404()
    post = db.session.query(Post).filter_by(id=post_id).first_or_404()
    author = db.session.query(User).filter_by(full_name = post.author).first()
    follow_lists = db.session.query(User).filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    edit_form = PostForm()
    return render_template('posts/view_post.html', post=post, follow_lists=follow_lists, 
                            edit_form=edit_form, author=author)


@post_blueprint.route('/post/<post_id>/edit', methods=["POST"])
def edit_post(post_id):
    form = PostForm()
    if form.validate_on_submit():
        post = db.session.query(Post).filter_by(user_id=current_user.id).filter_by(id=post_id).first_or_404()
        names_json, urls_json = "", ""
        if request.files['photo']:
            image_filenames = []
            image_urls = []
            for i, file in enumerate(request.files.getlist(form.photo.name)):
                image_filename = images.save(file)
                image_url = images.url(image_filename)
                image_filenames.append({i: image_filename})
                image_urls.append({i: image_url})
            names_json, urls_json = json.dumps(image_filenames), json.dumps(image_urls)
        author = db.session.query(User).filter_by(id=current_user.id).first()
        if names_json and urls_json:
            post.image_filename = names_json,
            post.image_url = urls_json,
        post.text = form.text.data,
        post.post_privacy = form.post_privacy.data,
        post.author = author.full_name
        db.session.add(post)
        db.session.commit()
        flash("Post Updated Successfully.", 'success')

        return redirect(url_for('post.post_create'))
    else:
        flash('ERROR! Post was not edited.', 'error')


@post_blueprint.route('/post/<post_id>/delete', methods=['POST'])
def delete_post(post_id):
    post = db.session.query(Post).filter_by(user_id=current_user.id).filter_by(id=post_id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    flash("Post Deleted Successfully.", 'success')
    return redirect(url_for('post.post_create'))


@post_blueprint.route('/like_post/<post_id>/<user_id>', methods=['POST'])
@flask_profiler.profile()
@login_required
def like_post(post_id, user_id):
    post_like = db.session.query(PostLike).filter_by(post_id=post_id).filter_by(user_id=user_id).first()
    if post_like:
        db.session.query(PostLike).filter_by(post_id=post_id).filter_by(user_id=user_id).delete()
    else:
        post_like = PostLike(
            post_id=post_id,
            user_id=user_id
        )
    db.session.add(post_like)
    db.session.commit()
    post_like = db.session.query(PostLike).filter_by(post_id=post_id).filter_by(user_id=user_id).first()
    if post_like:
        liked = 1
    else:
        liked = 0
    count = len(PostLike.query.filter_by(post_id=post_id).all())
    post = db.session.query(Post).get(post_id)
    post.creator.add_notification('post_likes', count, post_id)
    return json.dumps({
        'status': 'success',
        "count": count,
        "liked": liked
    })


@post_blueprint.route('/comment/<comment_id>/edit', methods=["POST"])
@flask_profiler.profile()
def edit_comment(comment_id):
    comment_text = request.form['comment_text']
    if not comment_text:
        abort(404)

    comment = db.session.query(Comment).get_or_404(int(comment_id))
    print(comment.post)
    if comment.author != current_user:
        abort(400)
    comment.text = comment_text
    db.session.add(comment)
    db.session.commit()
    flash("Comment Updated Successfully.", 'success')
    return redirect(url_for('post.post_create'))


@post_blueprint.route('/comment/<comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = db.session.query(Comment).get_or_404(int(comment_id))
    if comment.author != current_user:
        abort(400)
    db.session.delete(comment)
    db.session.commit()
    flash("Comment Deleted Successfully.", 'success')
    return redirect(url_for('post.post_create'))


##@post_blueprint.route('/interests')
##@login_required
##def view_interests():
##    interest = Interest.query.all()
##    return render_template('posts/all_interests.html', interest=interest)
##
##
##def meets_post_criteria(post):
##    if not post.title:
##        flash('You must include a title!', 'danger')
##        return False
##    if not post.text and not post.link:
##        flash('You must post either body text or a link!', 'danger')
##        return False
##
##    dup_link = post.query.filter_by(link=post.link).first()
##    if not post.text and dup_link:
##        flash('someone has already posted the same link as you!', 'danger')
##        return False
##
##    return True
##
##
##@post_blueprint.route('/<interest_name>/submit/', methods=['GET', 'POST'])
##def submit(interest_name=None):
##    """
##    """
##    if current_user is None:
##        flash('You must be logged in to submit posts!', 'danger')
##        return redirect(url_for('account.login', next=request.path))
##    user_id = current_user.user.id
##
##    interest = Interest.query.filter_by(name=interest_name).first()
##    if not interest:
##        abort(404)
##
##    form = SubmitForm(request.form)
##    if form.validate_on_submit():
##        title = form.title.data.strip()
##        link = form.link.data.strip()
##        text = form.text.data.strip()
##        post = Post(title=title, link=link, text=text,
##                    user_id=user_id, interest_id=interest.id)
##
##        if not meets_post_criteria(post):
##            return render_template('posts/submit.html', form=form, user=current_user.user,
##                                   cur_interest=interest.name)
##
##        db.session.add(post)
##        db.session.commit()
##        post.set_hotness()
##
##        flash('thanks for submitting!', 'success')
##        return redirect(url_for('post.view_interests', interest_name=interest.name))
##    return render_template('posts/submit.html', form=form, user=current_user.user,
##                           cur_interest=interest, interests=user.get_interests())


@post_blueprint.route('/comments/submit/', methods=['POST'])
@flask_profiler.profile()
@login_required
def submit_comment():
    post_id = int(request.form['post_id'])
    comment_text = request.form['comment_text']
    comment_parent_id = request.form['parent_id']  # empty means none

    if not comment_text:
        abort(404)

    post = db.session.query(Post).get_or_404(int(post_id))
    post.add_comment(comment_text, comment_parent_id, current_user.id)
    post.creator.add_notification('post_replies', len(post.comments.all()), post_id)

    return redirect(url_for('post.post_create'))


@post_blueprint.route('/posts/vote/', methods=['POST'])
@flask_profiler.profile()
@login_required
def vote_post():
    post_id = int(request.form['post_id'])
    user_id = current_user.user.id

    if not post_id:
        abort(404)

    post = db.session.query(Post).get_or_404(int(post_id))
    vote_status = post.vote(user_id=user_id)
    return jsonify(new_votes=post.votes, vote_status=vote_status)


@post_blueprint.route('/comments/vote/', methods=['POST'])
@flask_profiler.profile()
@login_required
def vote_comment():
    comment_id = int(request.form['comment_id'])
    user_id = current_user.user.id

    if not comment_id:
        abort(404)

    comment = db.session.query(Comment).get_or_404(int(comment_id))
    comment.vote(user_id=user_id)
    return jsonify(new_votes=comment.get_votes())


def meets_interest_criteria(interest):
    return True

##
##@post_blueprint.route('/interests/submit/', methods=['GET', 'POST'])
##@login_required
##def interest_submit():
##    """
##    """
##    if current_user is None:
##        flash('You must be logged in to submit interests!', 'danger')
##        return redirect(url_for('account.login', next=request.path))
##
##    form = SubmitForm(request.form)
##    user_id = current_user.id
##
##    if form.validate_on_submit():
##        name = form.name.data.strip()
##        desc = form.desc.data.strip()
##        interest = Interest.query.filter_by(name=name).first()
##        if interest:
##            flash('interest already exists!', 'danger')
##            return render_template('posts/submit.html', form=form, user=current_user,
##                                   interest=interest)
##        new_interest = Interest(name=name, desc=desc, creator_id=user_id)
##
##        if not meets_interest_criteria(interest):
##            return render_template('posts/submit.html', form=form, user=current_user,
##                                   interest=interest)
##
##        db.session.add(new_interest)
##        db.session.commit()
##
##        flash('Thanks for starting a community! Begin adding posts to your community\
##                by clicking the red button to the right.', 'success')
##        return redirect(url_for('post.view_interests', interest_name=new_interest.name))
##    return render_template('posts/submit.html', form=form)
