# coding: utf-8
# 不在数据库存储密码明文，而是存储其哈希值
from werkzeug.security import generate_password_hash, check_password_hash
# 管理登陆的用户和未登录的游客
from flask_login import UserMixin, AnonymousUserMixin
# 用于生成验证身份、修改邮箱等的链接
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
# 用于markdown式的编辑
from markdown import markdown
import bleach
from flask import current_app, url_for
from app.exceptions import ValidationError
from . import db
from . import login_manager
import datetime
import hashlib
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy import func
from .email import send_email


def fake_date(fake, end_datetime):
    str_time = fake.date(end_datetime=end_datetime)
    str_time = str_time.split('-')
    int_time = [int(_) for _ in str_time]
    return datetime.date(int_time[0], int_time[1], int_time[2])

class Permission:
    FOLLOW = 0x01  # 能否关注别人
    WRITE = 0x02  # 能否发帖
    COMMENT = 0x04 # 能否回帖
    ADMIN = 0x80  # 数据库管理员


class Role(db.Model):
    """
    实体：角色
    """
    __tablename__ = 'roles'
    # id会自动被赋值
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    # 默认角色为普通用户，故普通用户的该属性为True
    default = db.Column(db.Boolean, default=False, index=True)
    permission = db.Column(db.Integer)
    # user不是roles的属性，只是为了方便用从Role到users的引用
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __init__(self, **kwargs):
        super(Role, self).__init__(**kwargs)
        if self.permission is None:
            self.permission = 0

    # 静态方法，向roles中插入元素，用于初始化
    @staticmethod
    def insert_roles():
        print("插入角色...")
        roles = {
            'User': [Permission.FOLLOW, Permission.WRITE, Permission.COMMENT],
            'Administrator': [Permission.FOLLOW, Permission.WRITE, Permission.COMMENT, Permission.ADMIN]
        }
        default_role = 'User'
        for r in roles:
            # 在roles中查找第一个名为r的元素
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = (role.name == default_role)
            db.session.add(role)
        db.session.commit()

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permission += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permission -= perm

    def reset_permission(self):
        self.permission = 0

    def has_permission(self, perm):
        return self.permission & perm == perm

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return '<%d Follow %d>' % (self.follower_id, self.followed_id)


# 版务：User与Board之间的多对多联系
moderators = db.Table('moderators',
                      db.Column('moderator_id', db.Integer, db.ForeignKey('users.id')),
                      db.Column('board_id', db.Integer, db.ForeignKey('boards.id')),
                      db.Column('timestamp', db.DateTime, default=datetime.datetime.utcnow)
                      )

# 点赞回帖：User与Comment之间的多对多关系
comments_likes = db.Table('comments_likes',
                db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                db.Column('comment_id', db.Integer, db.ForeignKey('comments.id')),
                db.Column('timestamp', db.DateTime, default=datetime.datetime.utcnow)
                )

# 收藏版块：User与Board的多对多关系
boards_collections = db.Table('board_collections',
                              db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                              db.Column('board_id', db.Integer, db.ForeignKey('boards.id')),
                              db.Column('timestamp', db.DateTime, default=datetime.datetime.utcnow)
                              )


# 收藏帖子：User与Post之间的多对多关系
posts_collections = db.Table('posts_collections',
                             db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                             db.Column('post_id', db.Integer, db.ForeignKey('posts.id')),
                             db.Column('timestamp', db.DateTime, default=datetime.datetime.utcnow)
                             )


# flask_login.current_user用于管理当前服务的用户，它有一个认证的属性，如果是游客，该属性为False
# 如果是认证用户，则其为真。该属性用于根据是否是登陆用户还是游客来显示不同的网页。
# User继承UserMixin可以让登陆用户具有为真的认证属性。该属性不会记录在数据库中。
class User(UserMixin, db.Model):
    """
    实体：用户
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    nickname = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    location = db.Column(db.String(64))
    # 性别
    is_male = db.Column(db.Boolean)
    birthday = db.Column(db.Date(), default=datetime.date(2000, 10, 10))
    # 注册日期
    member_since = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    # 头像对应的哈希值，在用户注册完成后生成
    avatar_hash = db.Column(db.String(32))
    # 存储密码对应的哈希值
    password_hash = db.Column(db.String(128))
    # 用户注册后还需要在邮箱中确认
    confirmed = db.Column(db.Boolean, default=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    disabled = db.Column(db.Boolean, default=False) # 删除用户
    board = None    # 辅助变量：在计算用户在某版块下的回复量前，初始化该变量

    posts = db.relationship('Post', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')


    # 充当版务的版块
    moderated_boards = db.relationship('Board',
                             secondary = moderators,
                             backref=db.backref('moderators', lazy='dynamic'),
                             lazy='dynamic')
    # 点赞回帖
    liked_comments = db.relationship('Comment',
                                      secondary = comments_likes,
                                      backref=db.backref('likers', lazy='dynamic'),
                                      lazy='dynamic')

    # 收藏版块
    collected_boards = db.relationship('Board',
                                     secondary = boards_collections,
                                     backref = db.backref('collectors', lazy='dynamic'),
                                     lazy='dynamic')

    # 收藏帖子
    collected_posts = db.relationship('Post',
                                      secondary = posts_collections,
                                      backref = db.backref('collectors', lazy='dynamic'),
                                      lazy='dynamic',
                                      )

    followed = db.relationship('Follow',
                               foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    followers = db.relationship('Follow',
                                foreign_keys=[Follow.followed_id],
                                backref=db.backref('followed', lazy='joined'),
                                lazy='dynamic',
                                cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # 初始化用户角色，如果用户的邮箱在管理员邮箱之内，则用户角色为数据库管理员
        if self.role is None:
            if self.email in current_app.config['BBS_ADMIN']:
                self.role = Role.query.filter_by(name='Administrator').first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        # 根据用户邮箱计算初头像对应的哈希值
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = self.gravatar_hash()
        self.follow(self)

    def ping(self):
        self.last_seen = datetime.datetime.utcnow()
        db.session.add(self)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 用户注册后，需要进行邮箱验证
    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id}).decode('utf-8')

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id}).decode('utf-8')

    @staticmethod
    def reset_password(token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            print('except in reset_password')
            return False
        user = User.query.get(data.get('reset'))
        if user is None:
            return False
        user.password = new_password
        db.session.add(user)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps(
            {'change_email': self.id, 'new_email': new_email}
        ).decode('utf-8')

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = self.gravatar_hash()
        db.session.add(self)
        return True

    def can(self, permission):
        return self.role is not None and \
               (self.role.permission & permission) == permission

    def is_administrator(self):
        return self.can(Permission.ADMIN)

    def gravatar_hash(self):
        # 获取邮箱对应的头像哈希值
        return hashlib.md5(self.email.lower().encode('utf-8')).hexdigest()

    def gravatar(self, size=100, default='identicon', rating='g'):
        # 获取头像图片（大小为size*size）对应的url
        url = 'https://secure.gravatar.com/avatar'
        hash = self.avatar_hash or self.gravatar_hash()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating
        )

    def unfollow(self, user):
        # 取消关注user（user为User类型）
        f = self.followed.filter_by(followed_id = user.id).first()
        if f:
            db.session.delete(f)
            db.session.commit()

    def is_following(self, user):
        if user.id is None:
            return False
        return self.followed.filter_by(
            followed_id = user.id).first() is not None

    def follow(self, user):
        # 关注user
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)
            db.session.commit()

    def is_followed_by(self, user):
        if user.id is None:
            return False
        return self.followers.filter_by(
            follower_id=user.id).first() is not None

    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id}).decode('utf-8')

    def is_moderate(self, board):
        return board in self.moderated_boards

    def is_like_comment(self, comment):
        return self in comment.likers.all()

    def is_collect_post(self, post):
        return self in post.collectors.all()

    def is_collect_board(self, board):
        return self in board.collectors.all()

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id)\
                .filter(Follow.follower_id == self.id)

    @hybrid_property
    def cum(self):
        return self.comments

    @hybrid_method
    def i(self, comments):
        cs = db.session.query(func.count(db.session.query(comments.author_id).filter(comments.author_id == self.id)))
        return cs

    @staticmethod
    def generate_fake(count = 100):
        print("生成虚拟用户...")
        from faker import Faker
        from random import seed, randint
        from datetime import timedelta
        from sqlalchemy.exc import IntegrityError
        fake = Faker(locale='zh_CN')
        seed()
        min_birthday = datetime.date(2005, 12, 12)

        u = User(email='1309025479@qq.com',
                 nickname='bob',
                 password='123',
                 confirmed=True,
                 username='qinwentao',
                 location='北京',
                 about_me='爱拼才会赢',
                 is_male = 1,
                 birthday = fake_date(fake, min_birthday),
                 member_since=fake.past_datetime()-timedelta(10))
        db.session.add(u)
        db.session.commit()

        u = User(email='1500012848@pku.edu.cn',
                 nickname='zsh',
                 password='123',
                 confirmed=True,
                 username='zhushihao',
                 location='北京',
                 about_me='爱拼才会赢',
                 is_male = 1,
                 birthday = fake_date(fake, min_birthday),
                 member_since=fake.past_datetime()-timedelta(10))
        db.session.add(u)
        db.session.commit()

        i = 2
        while i < count:
            u = User(email=fake.email(),
                     nickname=fake.user_name(),
                     password='123',
                     confirmed=True,
                     username=fake.name(),
                     location=fake.city(),
                     about_me=fake.text(),
                     is_male=randint(0, 1),
                     birthday=fake_date(fake, min_birthday),
                     member_since=fake.past_datetime()-timedelta(10))
            db.session.add(u)
            try:
                db.session.commit()
                if i% 10 == 0:
                    print(i)
                i += 1
            except IntegrityError:
                print('oops')
                db.session.rollback()
        print(count)

    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

    def is_moderate(self, board):
        return False

    def is_like_comment(self, comment):
        return False

    def is_collect_post(self, post):
        return False

    def is_collect_board(self, board):
        return False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Board(db.Model):
    __tablename__ = 'boards'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, index=True)
    intoduction = db.Column(db.Text())
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref='board', lazy='dynamic')

    def __init__(self, **kwargs):
        super(Board, self).__init__(**kwargs)
        fake_email = self.name + '@qq.com'
        self.avatar_hash = hashlib.md5(fake_email.lower().encode('utf-8')).hexdigest()

    def gravatar(self, size=100, default='identicon', rating='g'):
        # 获取头像图片（大小为size*size）对应的url
        url = 'https://secure.gravatar.com/avatar'
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=self.avatar_hash, size=size, default=default, rating=rating
        )

    def post_mean_view(self):
        total = 0
        n = 0
        for p in self.posts.all():
            total += p.view_count
            n += 1
        if n == 0:
            return 0
        return total/n

    @property
    def posts_num(self):
        return self.posts.count()

    @staticmethod
    def generate_fake(count=10):
        print("开始生成虚拟版块...")
        from faker import Faker
        from random import randint, seed
        from datetime import timedelta
        seed()
        fake = Faker(locale='zh_CN')
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            timestamp = u.member_since + timedelta(seconds=randint(300, 1800))
            name = fake.word()
            while Board.query.filter_by(name=name).first():
                name = fake.word()
            b = Board(name=name,
                      intoduction=fake.sentence() + fake.sentence(),
                      timestamp=timestamp,
                      )
            b.moderators.append(u)
            b.collectors.append(u)
            db.session.add(b)
            db.session.commit()
        print(count)


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    board_id = db.Column(db.Integer, db.ForeignKey('boards.id'))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.utcnow)
    title = db.Column(db.String(64))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    comment_count = db.Column(db.Integer, index=True, default=0)
    view_count = db.Column(db.Integer, default=0)
    disabled = db.Column(db.Boolean, default=False)
    recent_time = db.Column(db.DateTime)    # 最后回复的时间
    duration = db.Column(db.Integer, index=True)  # 帖子持续时间：最后回复时间-发帖时间


    @property
    def body(self):
        return self.comments.first().body

    @staticmethod
    def new_post(title, body, author, board, timestamp=None, view_count=0):

        # 用户前10分钟发表的帖子数大于10则通知管理员
        posts_count_in_ten = author.posts.filter(Post.timestamp > datetime.datetime.utcnow() - datetime.timedelta(minutes=10)).count()
        if posts_count_in_ten >= 10:
            for admin_mail in current_app.config["BBS_ADMIN"]:
                send_email(admin_mail, '有人水贴',
                           '/mail/water_posts_warning', user=author, times=posts_count_in_ten)

        if timestamp is None:
            timestamp = datetime.datetime.utcnow()
        p = Post(title=title,
                 timestamp=timestamp,
                 view_count = view_count,
                 author=author,
                 board=board)
        # p.collectors.append(author)
        db.session.add(p)
        db.session.commit()
        refloor = -1
        Post.new_comment(body, author, p, refloor, timestamp)
        return p

    @staticmethod
    def new_comment(body, author, post, refloor, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.utcnow()
        c = Comment(body=body, timestamp=timestamp, author=author,
                    post=post, floor=post.comment_count+1,
                    refloor=refloor)
        post.comment_count += 1
        post.recent_time = timestamp
        delta = post.recent_time - post.timestamp
        post.duration = delta.days * 86400 + delta.seconds
        # c.likers.append(author)
        db.session.add(post)
        db.session.add(c)
        db.session.commit()


    @staticmethod
    def generate_fake(count=100):
        print("生成虚拟帖子...")
        from faker import Faker
        from random import randint, seed
        from datetime import timedelta
        seed()
        fake = Faker(locale='zh_CN')
        user_count = User.query.count()
        board_count = Board.query.count()
        for i in range(count):
            if i%100 == 0:
                print(i)
            u = User.query.offset(randint(0, user_count - 1)).first()
            b = Board.query.offset(randint(0, board_count - 1)).first()
            #  确保发帖时间在用户账号和版块的创建之后
            t = max(u.member_since + timedelta(seconds=randint(300, 1800)), b.timestamp + timedelta(seconds=randint(300, 1800)))
            title = fake.sentence()
            body = fake.text()
            view_count = randint(1, 10000)
            Post.new_post(title, body, u, b, t, view_count)
        print(count)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.utcnow)
    body = db.Column(db.Text())
    floor = db.Column(db.Integer)
    refloor = db.Column(db.Integer)
    disabled = db.Column(db.Boolean, default=False)

    @staticmethod
    def generate_fake(count=800):
        print("生成虚拟回复...")
        from faker import Faker
        from random import randint, seed
        from datetime import timedelta
        seed()
        fake = Faker(locale='zh_CN')
        user_count = User.query.count()
        post_count = Post.query.count()
        for i in range(count):
            if i % 100:
                print(i)
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post.query.offset(randint(0, post_count - 1)).first()
            body = fake.text()
            # 确保回帖比帖子的最后一条回帖晚
            t = max(u.member_since + timedelta(seconds = randint(300, 1800)), p.recent_time + timedelta(seconds = randint(10, 1000)))
            refloor = randint(0, p.comment_count)
            Post.new_comment(body, u, p, refloor, t)
        print(count)


def generate_fake():
    # 13 minutes to finish
    print(datetime.datetime.utcnow())
    db.drop_all()
    db.create_all()
    Role.insert_roles()
    User.generate_fake(count=100)
    Board.generate_fake(count=15)
    Post.generate_fake(count=500)
    Comment.generate_fake(count=3000)
    print(datetime.datetime.utcnow())





