# -*- coding: utf-8 -*
from flask_wtf import FlaskForm # 表单基类
from wtforms import StringField, SubmitField, TextAreaField, BooleanField, \
    SelectField
from flask_pagedown.fields import PageDownField
from wtforms.validators import DataRequired, Length, Email, Regexp
from wtforms import ValidationError
from ..models import Role, User, Board


class NameForm(FlaskForm):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(FlaskForm):
    nickname = StringField('昵称', validators=[Length(0, 64)])
    location = StringField('位置', validators=[Length(0, 64)])
    about_me = TextAreaField('关于我')
    sex = SelectField('性别', coerce=int)

    submit = SubmitField('提交')

    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.sex.choices = [(0, '女'), (1, '男')]



class EditProfileAdminForm(FlaskForm):
    email = StringField('邮箱', validators=[DataRequired(), Length(1, 64),
                                             Email()])
    username = StringField('用户名', validators=[
        DataRequired(), Length(1, 64)])
    confirmed = BooleanField('身份是否确认')
    role = SelectField('身份', coerce=int)
    nickname = StringField('昵称', validators=[Length(0, 64)])
    location = StringField('位置', validators=[Length(0, 64)])
    sex = SelectField('性别', coerce=int)
    about_me = TextAreaField('关于我')
    disabled = BooleanField('是否删除该用户')
    submit = SubmitField('提交')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)
                             for role in Role.query.order_by(Role.name).all()]
        self.sex.choices = [(0, '女'), (1, '男')]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError('邮箱已存在')

    def validate_username(self, field):
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError('用户名已存在')

class EditBoardProfileForm(FlaskForm):
    name = StringField('板块名称', validators=[Length(0, 64)])
    introduction = TextAreaField('版块介绍（50字以内）', validators=[Length(0, 50)])
    submit = SubmitField('提交')

    def __init__(self, board, *args, **kwargs):
        super(EditBoardProfileForm, self).__init__(*args, **kwargs)
        self.board = board

    def validate_name(self, field):
        if field.data != self.board.name and \
            Board.query.filter_by(name=field.data).first():
            raise ValidationError('版块名称已存在')


class PostForm(FlaskForm):
    title = StringField("我要发帖—标题", validators=[DataRequired()])
    body = PageDownField("内容", validators=[DataRequired()])
    submit = SubmitField("发布")


class ResponseForm(FlaskForm):
    re = TextAreaField('Re')
    body = StringField('回帖', validators=[DataRequired()])
    submit = SubmitField('提交')

class CompareForm(FlaskForm):
    board1 = SelectField('版块A', coerce=int)
    board2 = SelectField('版块B', coerce=int)
    submit = SubmitField('提交')
    def __init__(self, *args, **kwargs):
        super(CompareForm, self).__init__(*args, **kwargs)
        self.board1.choices = [(board.id, board.name)
                             for board in Board.query.order_by(Board.name).all()]
        self.board2.choices = [(board.id, board.name)
                             for board in Board.query.order_by(Board.name).all()]

class SearchUserForm(FlaskForm):
    username = StringField('用户名')
    submit = SubmitField('搜索')