# -*- coding: utf-8 -*
import os
from datetime import timedelta
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    # 发送邮件邮箱
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in \
        ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'mail_to_send_notification')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'mail_password')
    BBS_MAIL_SUBJECT_PREFIX = '[BBS]'
    BBS_MAIL_SENDER = '1309025479@qq.com'
    # 数据库管理员的邮箱，如果新添加的用户的邮箱在此之内，则将其角色置为数据库管理员
    BBS_ADMIN = ["1309025479@qq.com", "1500012848@pku.edu.cn"]

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=1) #设置静态文件（如css，js）文件的最大缓存时间

    BBS_POSTS_PER_PAGE = 20
    BBS_FOLLOWERS_PER_PAGE = 50
    BBS_USERS_PER_PAGE = 30
    BBS_COMMENTS_PER_PAGE = 10
    BBS_BOARDS_PER_PAGE = 10

    @staticmethod
    def init_app(app):
        pass


# 用于开发时的配置
class DevelopmentConfig(Config):
    DEBUG = True
    # 数据库的位置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


# 发布时的配置
class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data.sqlite')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


