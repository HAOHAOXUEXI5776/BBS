# -*- coding: utf-8 -*
from flask import Flask
# 用于设计关系对象数据库
from flask_sqlalchemy import SQLAlchemy
# 登陆管理
from flask_login import LoginManager
# 邮箱：用于注册、修改密码、修改邮箱时的验证
from flask_mail import Mail
# 使用bootstrap模板渲染网页
from flask_bootstrap import Bootstrap
# 用于分页显示
from flask_pagedown import PageDown
# 有关时间的配置
from flask_moment import Moment
from config import config

db = SQLAlchemy()
mail = Mail()
bootstrap = Bootstrap()
pagedown = PageDown()
moment = Moment()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'


def create_app(config_name):
    app = Flask(__name__)
    # 配置app
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    pagedown.init_app(app)
    moment.init_app(app)
    login_manager.init_app(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    return app
