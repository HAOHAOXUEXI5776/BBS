# -*- coding: utf-8 -*
from flask import render_template, abort, redirect, url_for, flash, \
    request, current_app, make_response
from flask_login import login_required, current_user
from . import main
from ..models import User, Role, Permission, Post, Comment, Board, comments_likes, boards_collections, posts_collections
from .forms import EditProfileAdminForm, EditProfileForm, PostForm, ResponseForm, EditBoardProfileForm ,CompareForm , SearchUserForm
from .. import db
from ..decorators import admin_required, permission_required
from sqlalchemy import func, desc, or_ , and_


################################################################ 首页（START） ################################################################

@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE) and form.validate_on_submit():
        post = Post(body = form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    show_all=bool(request.cookies.get('show_all', ''))
    most_viewed=bool(request.cookies.get('most_viewed', ''))
    most_comment=bool(request.cookies.get('most_comment', ''))
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))

    if show_followed:
        pagination = current_user.followed_posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )
    elif most_viewed:
        pagination = Post.query.order_by(Post.view_count.desc()).limit(10).from_self().paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )
    elif most_comment:
        q = Post.query.order_by(Post.comment_count.desc())
        pagination = q.limit(10).from_self().paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )
    else:
        show_all = True
        pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )

    posts = pagination.items
    print(show_all,show_followed,most_viewed,most_comment)
    return render_template('index.html', form=form, posts=posts,
                           pagination=pagination, show_all=show_all, show_followed=show_followed,
                           most_viewed=most_viewed, most_comment=most_comment)

@main.route('/all')
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_all', '1', max_age=30*24*60*60)
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    resp.set_cookie('most_viewed', '', max_age=30*24*60*60)
    resp.set_cookie('most_comment', '', max_age=30*24*60*60)
    return resp

@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_all', '', max_age=30*24*60*60)
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    resp.set_cookie('most_viewed', '', max_age=30*24*60*60)
    resp.set_cookie('most_comment', '', max_age=30*24*60*60)
    return resp

@main.route('/mostviewed')
def most_viewed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_all', '', max_age=30*24*60*60)
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    resp.set_cookie('most_viewed', '1', max_age=30*24*60*60)
    resp.set_cookie('most_comment', '', max_age=30*24*60*60)
    return resp

@main.route('/mostcomment')
def most_comment():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_all', '', max_age=30*24*60*60)
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    resp.set_cookie('most_viewed', '', max_age=30*24*60*60)
    resp.set_cookie('most_comment', '1', max_age=30*24*60*60)
    return resp

################################################################ 首页（END） ################################################################

################################################################ 比较（START） ################################################################
@main.route('/compare',methods=['GET','POST'])
def compare():
    form=CompareForm()
    if form.validate_on_submit():
        board1=form.board1.data
        board2=form.board2.data
        return redirect(url_for('.compare_result',board1=board1 ,board2=board2))
    return render_template('compare.html', form=form)

@main.route('/compare-result/<board1>/<board2>',methods=['GET','POST'])
def compare_result(board1,board2):
    board_1 = Board.query.get_or_404(board1)
    board_2 = Board.query.get_or_404(board2)
    count1 = db.session.query(Post.author_id,func.count(Post.id).label("count")).group_by(Post.author_id).filter(Post.board_id==board1).subquery()
    count2 = db.session.query(Post.author_id,func.count(Post.id).label("count")).group_by(Post.author_id).filter(Post.board_id==board2).subquery()
    tmp = db.session.query(User,count1.c.count,count2.c.count).outerjoin((count1,User.id==count1.c.author_id)).outerjoin((count2,User.id==count2.c.author_id)).filter(or_(count1.c.count > count2.c.count,and_(count1.c.count>0,count2.c.count==None)))
    form=CompareForm()
    if form.validate_on_submit():
        board1=form.board1.data
        board2=form.board2.data
        return redirect(url_for('.compare_result',board1=board1 ,board2=board2))
    form.board1.data=board_1.id
    form.board2.data=board_2.id
    page = request.args.get('page', 1, type=int)
    pagination = tmp.paginate(
        page, per_page=current_app.config['BBS_FOLLOWERS_PER_PAGE'],
        error_out=False)
    users = pagination.items
    return render_template('compare_result.html',form=form,users=users,board1=board_1,board2=board_2)

################################################################ 比较（END） ################################################################

################################################################ 关注（START） ################################################################

@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户不存在')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('你已经关注了该用户')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('关注了 %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户不存在')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('你未关注该用户')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('取消关注 %s ' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户不存在')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['BBS_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title='关注%s的人'%username,
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed_by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户不存在')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['BBS_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title='%s关注的人'%username,
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)

@main.route('/all_users')
@admin_required
def all_users():
    page = request.args.get('page', 1, type=int)
    pagination = User.query.paginate(
        page, per_page=current_app.config['BBS_FOLLOWERS_PER_PAGE'],
        error_out=False)
    users = pagination.items
    return render_template('all_users.html', users=users, endpoint='.all_users', pagination=pagination)


################################################################ 关注（END） ################################################################


################################################################ 用户页面（START） ################################################################

@main.route('/user/<username>', methods=['GET','POST'])
def user(username):
    print(username)
    user = User.query.filter_by(username=username).first_or_404()
    if user.disabled and not current_user.is_administrator():
        return render_template('403.html', user_disabled=True)
    page = request.args.get('page', 1, type=int)

    show_user_posts = bool(request.cookies.get('show_user_posts', ''))
    show_user_comments = bool(request.cookies.get('show_user_comments', ''))
    show_user_collected_posts = bool(request.cookies.get('show_user_collected_posts', ''))
    show_user_collected_boards = bool(request.cookies.get('show_user_collected_boards', ''))
    show_user_liked_comments = bool(request.cookies.get('show_user_liked_comments', ''))

    if show_user_comments:
        pagination = user.comments.order_by(Comment.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_COMMENTS_PER_PAGE'],
            error_out=False
        )
    elif show_user_collected_posts:
        pagination = user.collected_posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )
    elif show_user_collected_boards:
        pagination = user.collected_boards.order_by(Board.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_COMMENTS_PER_PAGE'],
            error_out=False
        )
    elif show_user_liked_comments:
        pagination = user.liked_comments.order_by(Comment.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_COMMENTS_PER_PAGE'],
            error_out=False
        )
    else:
        show_user_posts = True
        pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_COMMENTS_PER_PAGE'],
            error_out=False
        )

    posts = pagination.items
    comments = pagination.items
    boards = pagination.items
    return render_template('user.html', user=user, posts=posts, pagination=pagination, comments=comments,
                            boards = boards, show_user_posts=show_user_posts, show_user_comments=show_user_comments,
                           show_user_collected_posts=show_user_collected_posts, show_user_collected_boards=show_user_collected_boards,
                           show_user_liked_comments=show_user_liked_comments)

@main.route('/show_user_posts/<username>')
def show_user_posts(username):
    resp = make_response(redirect(url_for('.user', username=username)))
    resp.set_cookie('show_user_posts', '1', max_age=30*24*60*60)
    resp.set_cookie('show_user_comments', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_boards', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_liked_comments', '', max_age=30*24*60*60)
    return resp

@main.route('/show_user_comments/<username>')
def show_user_comments(username):
    resp = make_response(redirect(url_for('.user', username=username)))
    resp.set_cookie('show_user_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_comments', '1', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_boards', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_liked_comments', '', max_age=30*24*60*60)
    return resp

@main.route('/show_user_collected_posts/<username>')
def show_user_collected_posts(username):
    resp = make_response(redirect(url_for('.user', username=username)))
    resp.set_cookie('show_user_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_comments', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_posts', '1', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_boards', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_liked_comments', '', max_age=30*24*60*60)
    return resp

@main.route('/show_user_collected_boards/<username>')
def show_user_collected_boards(username):
    resp = make_response(redirect(url_for('.user', username=username)))
    resp.set_cookie('show_user_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_comments', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_boards', '1', max_age=30*24*60*60)
    resp.set_cookie('show_user_liked_comments', '', max_age=30*24*60*60)
    return resp

@main.route('/show_user_liked_comments/<username>')
def show_user_liked_comments(username):
    resp = make_response(redirect(url_for('.user', username=username)))
    resp.set_cookie('show_user_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_comments', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_posts', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_collected_boards', '', max_age=30*24*60*60)
    resp.set_cookie('show_user_liked_comments', '1', max_age=30*24*60*60)
    return resp



#编辑自己的资料
@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        current_user.is_male = form.sex.data
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('你的资料被更新了')
        return redirect(url_for('.user', username=current_user.username))
    form.nickname.data = current_user.nickname
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    form.sex.data = current_user.is_male
    return render_template('edit_profile.html', form=form)


# 管理员编辑用户的资料
@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.is_male = form.sex.data
        user.nickname = form.nickname.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        user.disabled = form.disabled.data
        db.session.add(user)
        db.session.commit()
        flash('资料已被更新')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.sex.data = user.is_male
    form.nickname.data = user.nickname
    form.location.data = user.location
    form.about_me.data = user.about_me
    form.disabled.data = user.disabled
    return render_template('edit_profile.html', form=form, user=user)


################################################################ 用户页面（END） ################################################################



################################################################ 帖子（START） ################################################################

# 第id个帖子
@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    post.view_count += 1
    db.session.add(post)
    db.session.commit()
    if post.disabled is True and not current_user.is_administrator() \
            and not current_user.is_moderate(post.board):
        return render_template('404.html', deleted_post=True)
    form = ResponseForm()
    if current_user.can(Permission.COMMENT) and form.validate_on_submit():
        refloor = 0
        Post.new_comment(form.body.data, current_user._get_current_object(),post, refloor)
        flash('评论提交成功')
        return redirect(url_for('.post', id=post.id, page=-1))
    form.re.data = 'Re 标题: ' + post.title
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) // \
               current_app.config['BBS_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.floor.asc()).paginate(
        page, per_page=current_app.config['BBS_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', post=post, form=form, board=post.board, page=page,
                           comments=comments, pagination=pagination)

# 回复第id个评论
@main.route('/response_comment/<int:postid>/<int:floor>', methods=['GET', 'POST'])
@login_required
def response_comment(postid, floor):
    post = Post.query.get_or_404(postid)
    if post.disabled is True and not current_user.is_administrator() \
            and not current_user.is_moderate(post.board):
        return render_template('404.html', deleted_post=True)
    comment = post.comments.filter_by(floor=floor).first()
    form = ResponseForm()
    if current_user.can(Permission.COMMENT) and form.validate_on_submit():
        refloor = floor
        Post.new_comment(form.body.data, current_user._get_current_object(), post, refloor)
        flash('评论提交成功')
        return redirect(url_for('.post', id=post.id, page=-1))

    form.re.data = 'Re ' + str(floor) + '层: ' + comment.body
    page = request.args.get('page', 1, type=int)
    return render_template('response_comment.html', form=form, page=page, board=post.board,
                        post=post, floor=floor)



# 编辑帖子（用户编辑自己的帖子或管理员/版务编辑帖子）
@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMIN) and \
            not current_user.is_moderate(post.board):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        first_comment = post.comments.first()
        first_comment.body = form.body.data
        db.session.add(post)
        db.session.add(first_comment)
        db.session.commit()
        flash('帖子更新成功')
        return redirect(url_for('.post', id=post.id))
    form.title.data = post.title
    form.body.data = post.body
    return render_template('edit_post.html', form=form)

# 删除帖子（管理员/版务删除帖子）
@main.route('/delete_post/<int:id>')
@login_required
def delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMIN) \
        and not current_user.moderate(post.board):
        abort(403)
    post.disabled = True
    db.session.add(post)
    db.session.commit()
    return redirect(request.referrer)


# 恢复帖子（管理员/版务恢复帖子）
@main.route('/recover_post/<int:id>')
@login_required
def recover_post(id):
    post = Post.query.get_or_404(id)
    if not current_user.can(Permission.ADMIN) and not current_user.moderate(post.board):
        abort(403)
    post.disabled = False
    db.session.add(post)
    db.session.commit()
    return redirect(request.referrer)


# 收藏帖子
@main.route('/collect_post/<int:id>')
@login_required
def collect_post(id):
    post = Post.query.get_or_404(id)
    if not current_user.is_collect_post(post):
        post.collectors.append(current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
    return redirect(request.referrer)


# 取消收藏帖子
@main.route('/not_collect_post/<int:id>')
@login_required
def not_collect_post(id):
    post = Post.query.get_or_404(id)
    if current_user.is_collect_post(post):
        post.collectors.remove(current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
    return redirect(request.referrer)


################################################################ 帖子（END） ################################################################



################################################################ 回帖（START） ################################################################

# 对回帖点赞
@main.route('/like_comment/<int:id>')
@login_required
def like_comment(id):
    comment = Comment.query.get_or_404(id)
    if not current_user.is_like_comment(comment):
        comment.likers.append(current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
    return redirect(request.referrer)


# 取消对回帖点赞
@main.route('/dislike_comment/<int:id>')
@login_required
def dislike_comment(id):
    comment = Comment.query.get_or_404(id)
    if current_user.is_like_comment(comment):
        comment.likers.remove(current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
    return redirect(request.referrer)


# 恢复回帖
@main.route('/recover_comment/<int:id>')
@login_required
def recover_comment(id):
    comment = Comment.query.get_or_404(id)
    if not current_user.is_administrator() and not current_user.moderator(comment.post.board):
        abort(403)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(request.referrer)


# 删除回帖
@main.route('/delete_comment/<int:id>')
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if not current_user.is_administrator() and not current_user.moderator(comment.post.board):
        abort(403)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(request.referrer)


################################################################ 回帖（END） ################################################################



################################################################ 版块目录（START） ################################################################

# 版块目录
@main.route('/boards', methods=['GET', 'POST'])
def boards():
    form = PostForm()
    if current_user.can(Permission.WRITE) and form.validate_on_submit():
        post = Post(body = form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.boards'))
    page = request.args.get('page', 1, type=int)
    pagination = Board.query.order_by(Board.timestamp.desc()).paginate(
        page, per_page=current_app.config['BBS_BOARDS_PER_PAGE'],
        error_out=False
    )
    boards = pagination.items
    return render_template('boards.html',boards=boards,pagination=pagination, form=form)

################################################################ 版块目录（END） ################################################################



################################################################ 版块（START） ################################################################

@main.route('/board/<boardname>', methods=['GET', 'POST'])
def board(boardname):
    form=PostForm()
    board = Board.query.filter_by(name=boardname).first_or_404()
    print('board')
    if current_user.can(Permission.WRITE) and form.validate_on_submit():
        post = Post.new_post(form.title.data, form.body.data, current_user._get_current_object(), board)
        return redirect(url_for('.post', id=post.id))

    board_show_all=bool(request.cookies.get('board_show_all', ''))
    board_popular=bool(request.cookies.get('board_popular', ''))
    board_click_above_avg=bool(request.cookies.get('board_click_above_avg', ''))
    board_comment_above_avg=bool(request.cookies.get('board_comment_above_avg', ''))
    board_user_comment=bool(request.cookies.get('board_user_comment', ''))
    board_user_post=bool(request.cookies.get('board_user_post', ''))

    page = request.args.get('page', 1, type=int)

    pagination = None
    avg = None
    most_popular_post=None
    if board_popular:
        query = board.posts
        most_popular_post = query.order_by(Post.duration.desc()).limit(1).first()
        comments = Comment.query.join(Post, Comment.post_id == Post.id).filter(Post.id == most_popular_post.id).subquery().c
        tmp = db.session.query(User, comments.author_id).filter(User.id==comments.author_id)
        pagination = tmp.paginate(
            page, per_page=current_app.config['BBS_USERS_PER_PAGE'],
            error_out=False
        )
        users = pagination.items


    elif board_click_above_avg:
        avg_click = board.post_mean_view()
        print('平均阅读', avg_click)
        query = board.posts.filter(Post.view_count > avg_click)
        pagination = query.order_by(Post.view_count.desc()).paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )

    elif board_comment_above_avg:
        # 在该版块的所有回帖
        comments = Comment.query.join(Post, Comment.post_id == Post.id).filter(Post.board_id == board.id).subquery().c
        comment_cnt = db.session.query(comments.id).count()
        author_cnt = db.session.query(comments.author_id).group_by(comments.author_id).count()
        avg = comment_cnt/author_cnt
        # 按在该版块发帖数降序排列的所有用户
        counts = func.count('comments.id').label('cnt')
        tmp = db.session.query(User, comments.author_id, counts).\
            group_by(comments.author_id).filter(User.id==comments.author_id).order_by(counts.desc()).\
            having(counts > avg)
        pagination = tmp.paginate(
            page, per_page=current_app.config['BBS_USERS_PER_PAGE'],
            error_out=False
        )

    elif board_user_comment:
        # 在该版块的所有回帖
        comments = Comment.query.join(Post, Comment.post_id == Post.id).filter(Post.board_id == board.id).subquery().c
        # 按在该版块发帖数降序排列的所有用户
        tmp = db.session.query(User, comments.author_id, func.count(comments.id).label('cnt')).\
            group_by(comments.author_id).filter(User.id==comments.author_id).order_by(desc('cnt'))

        pagination = tmp.paginate(
            page, per_page=current_app.config['BBS_USERS_PER_PAGE'],
            error_out=False
        )

    elif board_user_post:
        # 在该版块的所有post
        posts = Post.query.filter(Post.board_id == board.id).subquery().c
        # 按在该版块发帖数降序排列的所有用户
        tmp = db.session.query(User, posts.author_id, func.count(posts.id).label('cnt')).\
            group_by(posts.author_id).filter(User.id==posts.author_id).order_by(desc('cnt'))
        pagination = tmp.paginate(
            page, per_page=current_app.config['BBS_USERS_PER_PAGE'],
            error_out=False
        )

    else:
        board_show_all = True
        pagination = board.posts.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['BBS_POSTS_PER_PAGE'],
            error_out=False
        )

    posts = pagination.items
    users = pagination.items


    print(len(posts), len(users))
    print(board_show_all, board_popular, board_click_above_avg, board_comment_above_avg,
          board_user_comment)

    return render_template('board.html', form=form, board=board, posts=posts, users=users, pagination=pagination,
                           board_show_all = board_show_all, board_popular=board_popular,
                           board_click_above_avg=board_click_above_avg, board_comment_above_avg=board_comment_above_avg,
                           board_user_comment=board_user_comment,board_user_post=board_user_post, avg_comment = avg, post=most_popular_post)


@main.route('/board_show_all/<boardname>')
def board_show_all(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '1', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','',max_age=30*24*60*60)
    return resp

@main.route('/board_user_comment/<boardname>')
def board_user_comment(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','1',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','',max_age=30*24*60*60)
    return resp

@main.route('/board_user_post/<boardname>')
def board_user_post(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','1',max_age=30*24*60*60)
    return resp

@main.route('/board_popular/<boardname>')
def board_popular(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '1', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','',max_age=30*24*60*60)
    return resp

@main.route('/board_click_above_avg/<boardname>')
def board_click_above_avg(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '1', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','',max_age=30*24*60*60)
    return resp

@main.route('/board_comment_above_avg/<boardname>')
def board_comment_above_avg(boardname):
    resp = make_response(redirect(url_for('.board',boardname=boardname)))
    resp.set_cookie('board_show_all', '', max_age=30*24*60*60)
    resp.set_cookie('board_popular', '', max_age=30*24*60*60)
    resp.set_cookie('board_click_above_avg', '', max_age=30*24*60*60)
    resp.set_cookie('board_comment_above_avg', '1', max_age=30*24*60*60)
    resp.set_cookie('board_user_comment','',max_age=30*24*60*60)
    resp.set_cookie('board_user_post','',max_age=30*24*60*60)
    return resp


# 收藏版块
@main.route('/collect_board/<boardname>')
@login_required
def collect_board(boardname):
    board = Board.query.filter_by(name=boardname).first_or_404()
    if not current_user.is_collect_board(board):
        board.collectors.append(current_user._get_current_object())
        db.session.add(board)
        db.session.commit()
    return redirect(url_for('.board', boardname=boardname))

# 取消收藏版块
@main.route('/not_collect_board/<boardname>')
@login_required
def not_collect_board(boardname):
    board = Board.query.filter_by(name=boardname).first_or_404()
    if current_user.is_collect_board(board):
        board.collectors.remove(current_user._get_current_object())
        db.session.add(board)
        db.session.commit()
    return redirect(url_for('.board', boardname=boardname))

# 编辑版块资料
@main.route('/edit-board-profile/<boardname>', methods=['GET', 'POST'])
@login_required
def edit_board_profile(boardname):
    board = Board.query.filter_by(name=boardname).first_or_404()
    if not current_user.is_moderate(board) and not current_user.is_administrator():
        abort(403)
    form = EditBoardProfileForm(board=board)
    if form.validate_on_submit():
        board.name = form.name.data
        board.intoduction = form.introduction.data
        db.session.add(board)
        db.session.commit()
        flash('版块资料被更新了')
        return redirect(url_for('.board', boardname=board.name))
    form.name.data = board.name
    form.introduction.data = board.intoduction
    return render_template('edit_board_profile.html', form=form)

################################################################ 版块（END） ################################################################

################################################################ 搜索用户（START） ################################################################

@main.route('/search-user', methods=['GET', 'POST'])
def search_user():
    form=SearchUserForm()
    if form.validate_on_submit():
        username=form.username.data
        return redirect(url_for('.user',username=username))
    return render_template('search_user.html', form=form)

################################################################ 搜索用户（END） ################################################################