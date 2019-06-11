# -*- coding: utf-8 -*
import os
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand
from app import create_app, db
from app.models import Role, User, Board, Post, Comment, Permission, Follow, generate_fake, comments_likes, posts_collections, boards_collections, moderators

app = create_app(os.getenv('BBS_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)


# 使用python manage.py shell可以进入命令行，直接对传入shell的参数进行操作
# 这可以用来检查数据库，初始化数据库等
def make_shell_context():
    return dict(app=app, db=db, Role=Role, User=User, Board=Board, Post=Post,
                Comment=Comment, Permission=Permission, Follow=Follow, Fake=generate_fake,
                comments_likes=comments_likes, posts_collections=posts_collections,
                boards_collections=boards_collections, moderators=moderators)


# 加入shell命令行参数
manager.add_command("shell", Shell(make_context=make_shell_context))


# 加入db参数。有三种操作：
# 从无到有建立数据库： python manage.py init
# 数据库模式有变化，
# 先进行准备工作：python manage.py migrate -m "<一些变动的说明>"
# 执行更新操作：python manage.py upgrade
# 另外，还有downgrade参数可以回到上一个数据库版本
manager.add_command('db', MigrateCommand)

# 若要运行app，使用命令：
# python manage.py runserver --host 127.0.0.1


if __name__ == "__main__":
    manager.run()
